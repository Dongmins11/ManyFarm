"""Evaluate delivered Teacher code without camera/detector recording.

Use an isolated, relocated copy of the delivery, not the active Student checkout.
The delivered eval_current_pair.py, CurrentPairEnv, StagedTeacher, checkpoints,
normalizers and low-level control are used unchanged. Only AppLauncher camera
enablement, RGB-D rig construction and the recording loop are replaced. This is
a physics/control diagnostic, not an end-to-end camera reproduction or training.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import runpy
import sys
import time
import types


def evaluate(env, wrapped, teacher, args, out, app, kin, world_from_robot):
    import torch

    records = []
    steps = 0
    started = time.monotonic()
    physics = dict(physics_dt_s=env.cfg.sim.dt, decimation=env.cfg.decimation,
                   policy_dt_s=env.step_dt, physics_hz=1/env.cfg.sim.dt,
                   policy_hz=1/env.step_dt, cameras_enabled=False,
                   control='delivered staged Teacher; no Student',
                   scope='camera/detector recording omitted; truth-assigned target')
    (out/'diagnostic_runtime.json').write_text(json.dumps(physics, indent=2))
    (out/'DO_NOT_TRAIN.json').write_text(json.dumps({'reason': physics['scope']}))
    with torch.inference_mode():
        for episode in range(args.episodes):
            if steps >= args.steps or not app.is_running():
                break
            env.layout_episode = episode
            env.reset()
            obs = env.assign_target(env.assignment_slot)
            teacher.reset()
            row = dict(episode=episode, seed=args.seed, layout=env.last_layout,
                       target_break_threshold_N=float(env.threshold[0, env.assignment_slot]),
                       initial_observation=obs['policy'][0].cpu().tolist())
            local = 0
            reached = set()
            with (out/f'trace_{episode:04d}.jsonl').open('x') as trace:
                while env.assignment_status == 'RUNNING' and steps < args.steps and app.is_running():
                    action = teacher(obs).clamp(-1, 1)
                    stage = int(env.expert_stage[0])
                    reached.add(stage)
                    q = env.robot.data.joint_pos[0, env.jids].cpu().tolist()
                    qd = env.robot.data.joint_vel[0, env.jids].cpu().tolist()
                    raw = obs['policy'].clone()
                    raw[:, 42] = (1-(teacher.stage_steps-1)/env.max_episode_length).clamp(0, 1)
                    expert = teacher.grasp_expert if stage == -1 else teacher.experts[stage]
                    normalizer = getattr(expert, 'actor_obs_normalizer', None)
                    normalized = normalizer(raw)[0].cpu().tolist() if normalizer else None
                    before = dict(step=local, sim_s=local*env.step_dt, stage=stage,
                                  observation=obs['policy'][0].cpu().tolist(),
                                  expert_observation=raw[0].cpu().tolist(),
                                  normalized_observation=normalized,
                                  executed_action=action[0].cpu().tolist(),
                                  joint_q_rad=q, joint_qd_rad_s=qd)
                    obs, _, _, _ = wrapped.step(action)
                    local += 1
                    steps += 1
                    before.update(targets_rad=env.targets[0].cpu().tolist(),
                                  diagnostics={k: float(v[0]) for k, v in env.last_diagnostics.items()},
                                  assignment_status=env.assignment_status)
                    trace.write(json.dumps(before)+'\n')
                if env.assignment_status == 'RUNNING':
                    env.cancel_target()
            row.update(status=env.assignment_status, steps=local, sim_s=local*env.step_dt,
                       grasp=bool(env.has_grasped[0]), detach=bool(env.valid_detach[0]),
                       retained=bool(env.has_retained[0]), stages=sorted(reached),
                       terminal_diagnostics={k: float(v[0]) for k, v in env.last_diagnostics.items()},
                       final_fruit_root_policy_m=env._target_fruit().data.root_link_pos_w[0].cpu().tolist())
            records.append(row)
            (out/'episodes.json').write_text(json.dumps(records, indent=2))
            counts = {s: sum(r['status'] == s for r in records)
                      for s in ('SUCCEEDED', 'FAILED', 'TIMED_OUT', 'CANCELLED')}
            counts.update(episodes=len(records), steps=steps, wall_s=time.monotonic()-started)
            (out/'metrics.json').write_text(json.dumps(counts, indent=2))
            print('DELIVERED_TEACHER_EPISODE', json.dumps({k: row[k] for k in
                  ('episode', 'status', 'steps', 'sim_s', 'grasp', 'detach', 'retained', 'stages')}), flush=True)
    if len(records) != args.episodes:
        raise RuntimeError('Incomplete diagnostic evaluation')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle-root', type=Path, required=True)
    parser.add_argument('--target', choices=('red', 'yellow'), required=True)
    parser.add_argument('--seed', type=int, required=True)
    parser.add_argument('--episodes', type=int, default=5)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    root = args.bundle_root.resolve()
    out = args.output.resolve()
    if out.exists() or args.episodes < 1:
        parser.error('Require a new output path and positive episode count')
    profile_path = root/'src/harvest_robot/config/teacher_ramp_20260930.json'
    profile = json.loads(profile_path.read_text())
    for item in profile['checkpoints'].values():
        checkpoint = root/item['path']
        for path, expected in [(checkpoint, item['sha256']),
                               (checkpoint.parent/'run.json', item['run_sha256'])]:
            if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
                raise ValueError(f'Delivered policy hash mismatch: {path}')
    os.chdir(root)
    sys.path.insert(0, str(root/'src/harvest_robot'))
    # Disable sensor rendering before booting Isaac. The robot camera bodies and
    # their physical geometry remain the delivered asset.
    import isaaclab.app as isaac_app
    original_launcher = isaac_app.AppLauncher

    class NoCameraLauncher(original_launcher):
        def __init__(self, options):
            options.enable_cameras = False
            super().__init__(options)

    isaac_app.AppLauncher = NoCameraLauncher
    rig_module = types.ModuleType('harvest_rl.d435_rig')

    class RecordingDisabledRig:
        def __init__(self, kin, config, frame):
            self.config = config

    rig_module.DualD435Rig = RecordingDisabledRig
    sys.modules[rig_module.__name__] = rig_module
    collector_module = types.ModuleType('harvest_runtime.student_collect')
    collector_module.evaluate = evaluate
    sys.modules[collector_module.__name__] = collector_module
    paths = {key: str(root/value['path']) for key, value in profile['checkpoints'].items()}
    argv = ['--collect-student', '--num-envs', '1', '--robot-source', 'current',
            '--checkpoint', paths['PULL_CKPT'], '--grasp-expert', paths['ENTRY_CKPT'],
            '--transport-expert', paths['TRANSPORT_CKPT'], '--place-expert', paths['PLACE_CKPT'],
            '--spring-grasp-grace', '--behavior-mode', 'strict', '--layout-domain', 'legacy-near',
            '--fruits', '2', '--min-spacing', '.18', '--contact-substeps', '2',
            '--detached-grip-hold', '--release-intent-mode', '--transport-adaptive-grip',
            '--transport-pose-stop', '--staged-release', 'fixed', '--eval-fruit-mass', '.009',
            '--transport-linear-pose-stop', '--headless', '--target', args.target,
            '--seed', str(args.seed), '--episodes', str(args.episodes), '--steps', '10000',
            '--output', str(out), '--student-detector',
            str(root/'external/models/model_yolo11_seg_ver1.2.pt'), '--student-vision-python', sys.executable,
            *profile['flags']]
    entry = root/'src/harvest_robot/eval_current_pair.py'
    provenance = dict(bundle_root=str(root), target=args.target, seed=args.seed,
                      profile=profile, entrypoint=str(entry),
                      entrypoint_sha256=hashlib.sha256(entry.read_bytes()).hexdigest(),
                      argv=argv, modified_delivery_sources=False,
                      recording_adapter=__file__, camera_recording=False, training=False)
    out.parent.mkdir(parents=True, exist_ok=True)
    (out.parent/(out.name+'_invocation.json')).write_text(json.dumps(provenance, indent=2))
    sys.argv = [str(entry), *argv]
    runpy.run_path(str(entry), run_name='__main__')
    if not (out/'metrics.json').is_file():
        raise RuntimeError('Delivered entrypoint did not produce completed metrics')
    metrics = json.loads((out/'metrics.json').read_text())
    if metrics['episodes'] != args.episodes:
        raise RuntimeError('Delivered entrypoint stopped early')


if __name__ == '__main__':
    main()
