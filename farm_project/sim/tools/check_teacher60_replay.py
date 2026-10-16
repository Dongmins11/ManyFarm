"""독립 원본의 실제 측정 궤적을 농장 어댑터에 주어 명령/단계 동등성을 검사한다.

검증용 계측만 원본 실행기에 삽입한다. 어댑터 출력은 물리에 적용하지 않는다.
"""
import argparse
import json
from pathlib import Path
import sys

PROJECT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT/'sim/ros_ws/src/farm_sim_devices'))


def install(env: object, actors: dict, bundle: Path, output: Path) -> None:
    import numpy as np
    import torch
    from farm_sim_devices.teacher_policy import TeacherController
    from farm_sim_devices.teacher_state import SOURCE_HOME, SOURCE_LOWER, SOURCE_UPPER
    from farm_sim_devices._teacher_vendor.quaternion import quat_apply

    index = 17  # 전달 test7042에서 파지부터 실제 적재까지 통과한 표본
    profile = json.loads((PROJECT/'sim/ros_ws/src/farm_sim_config/config/teacher_policy.json').read_text())
    profile['joint_limits'] = dict(lower=SOURCE_LOWER, upper=SOURCE_UPPER, home=SOURCE_HOME)
    controller = TeacherController(profile, project_root=PROJECT)
    original_pre, original_apply = env._pre_physics_step, env._apply_action
    events, rows = [], []
    maximum = {}
    active = False
    finished = False

    def sample() -> dict:
        fruit = env._target_fruit().data
        slot = int(env.target_index[index])
        origin = env.scene.env_origins[index]
        tcp, quat = env._tcp()
        def value(tensor: torch.Tensor) -> np.ndarray:
            return tensor[index].detach().cpu().numpy().copy()
        return dict(time_s=len(rows)*.05, q=value(env.robot.data.joint_pos[:, env.jids]),
            qd=value(env.robot.data.joint_vel[:, env.jids]),
            tcp_position=value(tcp-env.scene.env_origins), tcp_quaternion=value(quat),
            fruit_position=value(fruit.root_link_pos_w-env.scene.env_origins),
            fruit_quaternion=value(fruit.root_link_quat_w),
            fruit_com_position=value(fruit.root_com_pos_w-env.scene.env_origins),
            fruit_linear_velocity=value(fruit.root_com_lin_vel_w),
            fruit_angular_velocity=value(fruit.root_com_ang_vel_w),
            fixed_force=value(env._target_contact(env.fixed_contact)),
            moving_force=value(env._target_contact(env.moving_contact)),
            fixed_net_force=value(env.fixed_contact.data.net_forces_w[:, 0]),
            moving_net_force=value(env.moving_contact.data.net_forces_w[:, 0]),
            arm_forces=value(env.arm_contact.data.net_forces_w),
            attached=bool(env.attached[index, slot]), other_detached=False,
            anchor=(env.anchors[index, slot]-origin).cpu().numpy(),
            load_N=float(env.load[index, slot]), break_timer_s=float(env.break_timer[index, slot]),
            break_threshold_N=float(env.threshold[index, slot]),
            attachment_local=env.fruit_tips[slot].cpu().numpy(),
            collision_vertices=env.fruit_collision_hulls[slot].cpu().numpy(), detach_events=list(events))

    def pre(proposed: torch.Tensor) -> None:
        nonlocal active, finished
        if any(row['env_id'] == index for row in env.chain_episode_records):
            finished = True
        if finished:
            original_pre(proposed)
            return
        current = sample()
        if not active:
            controller.start_target('original_test17', current)
            controller.state.targets[:] = env.targets[index:index+1].cpu()
            active = True
        step = controller.tick(current)
        events.clear()
        original_pre(proposed)
        comparisons = dict(targets=(step.joint_targets, env.targets[index].cpu().numpy()),
            actions=(step.diagnostics['action'], env.actions[index].cpu().numpy()),
            gain=(step.diagnostics['actuator']['stiffness'], env.robot.data.joint_stiffness[index, env.jids].cpu().numpy()),
            limits=(step.diagnostics['actuator']['velocity_limits'], env.robot.data.joint_vel_limits[index, env.jids].cpu().numpy()))
        for key, (actual, expected) in comparisons.items():
            error = float(np.max(np.abs(np.asarray(actual)-np.asarray(expected))))
            maximum[key] = max(maximum.get(key, 0.), error)
        for name in ('bridge_started', 'pull_active', 'transport_active', 'deposit_active', 'valid_detach', 'has_retained'):
            if bool(getattr(controller.state, name)[0]) != bool(getattr(env, name)[index]):
                raise AssertionError(f'phase mismatch {name}, tick={len(rows)}')
        rows.append(dict(tick=len(rows), stage=step.stage, maximum=dict(maximum)))
        output.write_text(json.dumps(dict(ticks=len(rows), maximum=maximum, rows=rows), indent=2)+'\n')
        if max(maximum.values()) > 2e-4:
            raise AssertionError(f'command mismatch at tick {len(rows)}: {maximum}')

    def apply() -> None:
        before = sample() if active and not finished else None
        original_apply()
        slot = int(env.target_index[index])
        if before is not None and before['attached'] and not bool(env.attached[index, slot]):
            event = {key: before[key] for key in ('time_s', 'fruit_position', 'fruit_quaternion',
                'tcp_position', 'tcp_quaternion', 'fixed_force', 'moving_force')}
            event['tip_displacement'] = (before['fruit_position']+quat_apply(
                torch.tensor(before['fruit_quaternion']), torch.tensor(before['attachment_local'])).numpy()-before['anchor'])
            event['load_N'] = float(env.break_load[index, slot])
            event['break_timer_s'] = float(env.break_duration[index, slot])
            events.append(event)

    env._pre_physics_step, env._apply_action = pre, apply


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('bundle', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    script = args.bundle/'scripts/sim_team/run_teacher60_exported.py'
    code = script.read_text().replace('wrapper=RslRlVecEnvWrapper(env,clip_actions=None)',
        'install(env, actors, ROOT, replay_output)\n        wrapper=RslRlVecEnvWrapper(env,clip_actions=None)')
    sys.argv = [str(script), '--headless', '--split', 'test', '--output', str(args.output)]
    exec(compile(code, str(script), 'exec'), dict(__name__='__main__', __file__=str(script),
        install=install, replay_output=args.output.parent/(args.output.name+'_comparison.json')))
