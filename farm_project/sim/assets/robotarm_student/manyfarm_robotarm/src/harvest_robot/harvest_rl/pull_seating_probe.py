"""Separate bounded Cartesian alignment comparisons; frozen probes are untouched."""
from dataclasses import asdict
import json
import math
from types import MethodType, SimpleNamespace

import numpy as np
import torch

from .followup_60hz_probe import TRACE_KEYS
from .pull_seating_60hz import cartesian_action, center_correction, follow_orientation
from .kinematics import ArmKinematics
from .pull_speed_comparison import ContactPause
from .settings import CACHE


def quaternion_rotation_deg(current, reference):
    a = current / current.norm(dim=-1, keepdim=True).clamp_min(1e-9)
    b = reference / reference.norm(dim=-1, keepdim=True).clamp_min(1e-9)
    return 2 * torch.acos((a * b).sum(-1).abs().clamp(0, 1)) * (180 / math.pi)


def capture_diagnostics(env, fruit_reference, tcp_reference):
    """Read existing sensors only. Net arm force does not identify the other body."""
    fruit = env._target_fruit().data
    _, tcp_quat = env._tcp()
    fixed = env._target_contact(env.fixed_contact)
    moving = env._target_contact(env.moving_contact)
    arm = env.arm_contact.data.net_forces_w
    peak, body = arm.norm(dim=-1).max(-1)
    extra = dict(fruit_rotation_deg=quaternion_rotation_deg(fruit.root_link_quat_w, fruit_reference),
                 tcp_rotation_deg=quaternion_rotation_deg(tcp_quat, tcp_reference),
                 contact_opposition_cos=(fixed * moving).sum(-1) /
                    (fixed.norm(dim=-1) * moving.norm(dim=-1)).clamp_min(1e-9),
                 arm_contact_peak_N=peak, arm_contact_peak_body_index=body.float())
    for prefix, vector in [('fixed_force', fixed), ('moving_force', moving),
            ('fruit_position', fruit.root_link_pos_w - env.scene.env_origins),
            ('fruit_linear_velocity', fruit.root_com_lin_vel_w),
            ('fruit_angular_velocity', fruit.root_com_ang_vel_w)]:
        unit = {'fixed_force': 'N', 'moving_force': 'N', 'fruit_position': 'm',
                'fruit_linear_velocity': 'm_s', 'fruit_angular_velocity': 'rad_s'}[prefix]
        for j, axis in enumerate('xyz'):
            extra[f'{prefix}_{axis}_{unit}'] = vector[:, j].clone()
    for prefix, quat in [('fruit_quaternion', fruit.root_link_quat_w), ('tcp_quaternion', tcp_quat)]:
        for j, axis in enumerate('wxyz'):
            extra[f'{prefix}_{axis}'] = quat[:, j].clone()
    for j in range(arm.shape[1]):
        for k, axis in enumerate('xyz'):
            extra[f'arm_body_{j}_force_{axis}_N'] = arm[:, j, k].clone()
    return extra


@torch.inference_mode()
def probe(env, wrapped, mode, duration, out, metadata, seed, *, experiment, alignment):
    if mode not in ('hold','pull-probe') or (mode == 'pull-probe' and abs(duration - experiment.duration_s) > 1e-9):
        raise ValueError('This separate path is only an equal-distance pull experiment')
    kin = ArmKinematics(CACHE / 'harvest_training.urdf')
    wrapped.reset()
    cfg = SimpleNamespace(**env.settings.as_dict(), step_dt=env.step_dt)
    if duration >= cfg.episode_s - env.step_dt:
        raise ValueError('Equal-distance probe must finish before the unchanged episode timeout')
    q = env.robot.data.joint_pos[:, env.jids].cpu().numpy()
    origin = [kin.grasp_fk(row, cfg.diameter) for row in q]
    tcp = (env._tcp()[0] - env.scene.env_origins).cpu().numpy()
    initial = dict(bank_state_indices=env.handoff_indices.cpu().tolist(), joint_q_rad=q.tolist(),
        joint_velocity_rad_s=env.robot.data.joint_vel[:, env.jids].cpu().tolist(),
        joint_targets_rad=env.targets.cpu().tolist(), tcp_m=tcp.tolist(),
        fruit_states_local=[torch.cat((f.data.root_state_w[:, :3] - env.scene.env_origins,
                                      f.data.root_state_w[:, 3:]), -1).cpu().tolist() for f in env.fruits],
        meaning='Unmodified restored measured grasp, before the first physical step.')
    (out / 'initial_state.json').write_text(json.dumps(initial, indent=2) + '\n')
    fk_error = np.linalg.norm(tcp - np.array([o[:3, 3] for o in origin]), axis=-1)
    if np.max(fk_error) > .005:
        raise ValueError('Actual TCP differs from cached FK by over5mm')
    arm_names = list(env.arm_contact.body_names)
    (out / 'sensor_metadata.json').write_text(json.dumps(dict(
        trace_rate_hz=20, vector_frame='policy simulation world, SI', quaternion_order='wxyz',
        force_semantics='Existing ContactSensor normal contact force; not calibrated motor torque.',
        arm_body_names=arm_names, arm_body_pair_available=False,
        collision_partner='Not available from existing unfiltered net-force sensor; do not infer a partner.',
        pause_semantics='Zero arm action keeps stored loaded targets; no measured-angle rebase or fruit correction.'), indent=2) + '\n')
    fruit_reference = env._target_fruit().data.root_link_quat_w.clone()
    tcp_reference = env._tcp()[1].clone()
    old_rewards = env._get_rewards

    def instrumented(current):
        reward = old_rewards()
        extra = capture_diagnostics(current, fruit_reference, tcp_reference)
        current.followup_snapshot['diagnostics'].update(extra)
        current.followup_snapshot['pull_diagnostic_keys'] = list(extra)
        current.followup_snapshot['probe_timeout'] = current._target_elapsed_steps() >= current.max_episode_length - 1
        return reward

    env._get_rewards = MethodType(instrumented, env)
    guard = ContactPause(env.num_envs, experiment)
    completed, traces = {}, {i: [] for i in range(env.num_envs)}
    continuous = torch.zeros(env.num_envs, device=env.device)
    ever_bad = torch.zeros(env.num_envs, device=env.device, dtype=torch.bool)
    first_bad = [None] * env.num_envs
    reasons = [set() for _ in range(env.num_envs)]
    first_collision = [None] * env.num_envs
    commanded_positions = np.stack([o[:3, 3] for o in origin])
    try:
        with (out / 'trace.jsonl').open('x') as stream:
            for step in range(round(duration / env.step_dt)):
                active_mask = np.array([i not in completed for i in range(env.num_envs)])
                active = np.flatnonzero(active_mask).tolist()
                actions = torch.zeros((env.num_envs, 6), device=env.device)
                pulling = mode == 'pull-probe' and step * env.step_dt >= experiment.initial_hold_s - 1e-9
                command_paused = guard.paused.copy()
                retreat = experiment.retreat(guard.elapsed) if pulling else np.zeros(env.num_envs)
                target_positions = np.stack([o[:3, 3] for o in origin]); target_positions[:, 0] -= retreat
                if pulling or alignment.center_gain > 0 or alignment.seat_depth_m > 0:
                    measured = env.robot.data.joint_pos[:, env.jids].cpu().numpy()
                    targets = env.targets.cpu().numpy()
                    attached = env._t(env.attached).cpu().numpy()
                    for i in active:
                        if not attached[i] or command_paused[i] or guard.halted[i]:
                            continue
                        center = (env._grasp_center(env._target_fruit()) - env.scene.env_origins)[i].cpu().numpy()
                        actual = kin.grasp_fk(measured[i], cfg.diameter)[:3,3]
                        correction = center_correction(center-actual, alignment, (step+1)*env.step_dt)
                        target_positions[i] += correction
                        target_positions[i] += origin[i][:3,2]*alignment.seat_depth_m*min(1.,(step+1)*env.step_dt/experiment.initial_hold_s)
                        commanded_positions[i] = target_positions[i]
                        reference_pose = follow_orientation(origin[i], fruit_reference[i].cpu().numpy(),
                            env._target_fruit().data.root_link_quat_w[i].cpu().numpy(), alignment)
                        actions[i] = torch.tensor(cartesian_action(kin, measured[i], target_positions[i],
                            reference_pose, targets[i], cfg, alignment), device=env.device)
                wrapped.step(actions)
                snap = env.followup_snapshot
                stable = snap['qualified'] & (snap['slip'] < cfg.max_slip)
                if mode == 'hold': stable &= snap['attached']
                ever_bad |= ~stable
                continuous = torch.where(stable, continuous + env.step_dt, torch.zeros_like(continuous))
                guard.after_step(stable.cpu().numpy(), active_mask, pulling, command_paused)
                d = snap['diagnostics']
                actual_tcp = torch.stack([d[f'tcp_{axis}_m'] for axis in 'xyz'], -1)
                d.update(command_retreat_m=torch.as_tensor(
                        np.array([o[0, 3] for o in origin]) - commanded_positions[:, 0], device=env.device),
                    command_tcp_error_m=(actual_tcp - torch.tensor(commanded_positions, device=env.device)).norm(dim=-1),
                    command_paused=torch.as_tensor(command_paused, device=env.device),
                    guard_halted=torch.as_tensor(guard.halted, device=env.device),
                    environment_timeout=snap['probe_timeout'].clone(),
                    total_pause_s=torch.as_tensor(guard.total_pause, device=env.device))
                columns = TRACE_KEYS + snap['pull_diagnostic_keys'] + [
                    'command_retreat_m', 'command_tcp_error_m', 'command_paused', 'guard_halted', 'environment_timeout', 'total_pause_s']
                # Keep all original failure flags, so events remain auditable.
                columns += [k for k in d if k.startswith('failure_')]
                values = torch.stack([d[k].float() for k in columns], -1).cpu().tolist()
                stream.write(json.dumps(dict(step=step, time_s=(step + 1) * env.step_dt,
                    env_ids=active, columns=columns, rows=[values[i] for i in active])) + '\n')
                for i in active:
                    row = dict(zip(columns, values[i])); traces[i].append(row)
                    if not bool(stable[i]):
                        if first_bad[i] is None:
                            first_bad[i] = (step + 1) * env.step_dt
                        if not row['bilateral_contact']: reasons[i].add('contact_lost')
                        if row['distance_m'] > cfg.grasp_center_tolerance: reasons[i].add('offcenter')
                        if row['slip_m'] >= cfg.max_slip: reasons[i].add('slip')
                    if row['arm_contact_peak_N'] > 12 and first_collision[i] is None:
                        index = int(row['arm_contact_peak_body_index'])
                        first_collision[i] = dict(time_s=(step + 1) * env.step_dt, body_index=index,
                            body_name=arm_names[index], net_contact_N=row['arm_contact_peak_N'], partner=None)
                    if snap['failure'][i] or snap['success'][i] or guard.halted[i] or snap['probe_timeout'][i] or step == round(duration / env.step_dt) - 1:
                        completed[i] = dict(env_id=i, bank_state_index=int(snap['bank_indices'][i]),
                            passed=((not bool(ever_bad[i]) and bool(snap['attached'][i]) and not bool(snap['failure'][i])) if mode=='hold' else bool(snap['success'][i]) and bool(snap['valid_detach'][i]) and bool(snap['retained'][i]) and not bool(snap['attached'][i]) and not bool(snap['failure'][i]) and not bool(guard.halted[i]) and not bool(snap['probe_timeout'][i])),
                            failure=bool(snap['failure'][i]), valid_detach=bool(snap['valid_detach'][i]),
                            retained=bool(snap['retained'][i]), attached=bool(snap['attached'][i]),
                            first_unstable_s=first_bad[i], qualification_failures=sorted(reasons[i]),
                            last_continuous_contact_s=float(continuous[i]),
                            peak_stem_load_N=max(r['stem_load_N'] for r in traces[i]),
                            reasons=[k for k in d if k.startswith('failure_') and bool(d[k][i])],
                            guard_halted=bool(guard.halted[i]), pause_events=int(guard.pause_events[i]),
                            timed_out=bool(snap['probe_timeout'][i]),
                            first_arm_collision=first_collision[i])
                if step % 5 == 0 or len(completed) == env.num_envs:
                    stream.flush()
                    print('PULL_SPEED_PROGRESS', experiment.speed_m_s * 1000, 'mm/s', experiment.loss_response,
                          'sim_s', round((step + 1) * env.step_dt, 2), 'completed', len(completed),
                          'passed', sum(r['passed'] for r in completed.values()), flush=True)
                if len(completed) == env.num_envs:
                    break
    finally:
        env._get_rewards = old_rewards
    report = dict(mode=mode, learning=False, comparison_only=True, training_gate_eligible=False,
        physics_hz=60, policy_hz=20, experiment=asdict(experiment), alignment=asdict(alignment), duration_s=duration, seed=seed,
        **{k: metadata[k] for k in ['split', 'probe_bank_sha256', 'domain_stage',
                                  'followup_contract_sha256', 'maintenance', 'bank_assignment_sha256', 'physical_signature']},
        source_grasp_sha256=metadata['source_checkpoint_sha256'],
        source_grasp_contract_sha256=metadata['source_contract_sha256'],
        episodes=[completed[i] for i in range(env.num_envs)],
        unique_bank_states_tested=len(set(initial['bank_state_indices'])), fk_error_m=fk_error.tolist(),
        meaning='Equal planned retreat distance; position-only preload. Probe guard stop is not an environment failure.')
    (out / 'probe.json').write_text(json.dumps(report, indent=2) + '\n')
    print('PULL_SPEED_COMPLETE', sum(r['passed'] for r in completed.values()), 'of', env.num_envs, flush=True)
    return report
