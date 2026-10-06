"""농장 전체 과실/오른팔 물리 smoke. Isaac Python에서 실행하며 원본 USD는 저장하지 않습니다.

기본 2초 동안 매 physics tick 줄기 외력을 갱신하고 모든 과실의 정지 결합을
확인합니다. --pull은 지정 과실 COM에 작은 외력을 유지한 뒤 회복시키고,
큰 외력을 적용해 이탈 후 중력 낙하를 검사합니다.
관절 HOME 초기화 이외에 pose를 바꾸거나 결합/성공 상태를 강제로 지정하지 않습니다.
"""
import argparse
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import sys
import traceback

import numpy as np


def digest(path: Path) -> str:
    """원본 USD 보존을 확인하는 SHA256."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def persist_report(report: dict) -> None:
    """Kit 종료 전 결과를 flush/fsync하고 원자적으로 교체합니다."""
    output = Path(report['result_file'])
    temporary = output.with_suffix(output.suffix+'.tmp')
    with temporary.open('w') as stream:
        stream.write(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False)+'\n')
        stream.flush()
        os.fsync(stream.fileno())
    temporary.replace(output)


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project-root', type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument('--config', type=Path, default=Path('sim/ros_ws/src/farm_sim_config/config/robotarm_physics.json'))
    parser.add_argument('--device-config', type=Path, default=Path('sim/ros_ws/src/farm_sim_config/config/harvest.json'))
    parser.add_argument('--scene', type=Path)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--seconds', type=float, default=2.)
    parser.add_argument('--expected-fruits', type=int)
    parser.add_argument('--max-rest-drift-m', type=float, default=.03)
    parser.add_argument('--max-base-drift-m', type=float, default=.05)
    parser.add_argument('--max-wheel-drift-rad', type=float, default=.2)
    parser.add_argument('--pull', action='store_true')
    parser.add_argument('--fruit-index', type=int, default=0)
    parser.add_argument('--hold-force-n', type=float, default=.1)
    parser.add_argument('--hold-seconds', type=float, default=1.)
    parser.add_argument('--pull-force-n', type=float, default=3.)
    parser.add_argument('--pull-seconds', type=float, default=1.)
    parser.add_argument('--fall-seconds', type=float, default=.6)
    parser.add_argument('--minimum-fall-m', type=float, default=.003)
    parser.add_argument('--gui', action='store_true')
    args = parser.parse_args()
    for key in ('seconds', 'max_rest_drift_m', 'max_base_drift_m', 'max_wheel_drift_rad',
                'hold_force_n', 'hold_seconds', 'pull_force_n', 'pull_seconds',
                'fall_seconds', 'minimum_fall_m'):
        value = getattr(args, key)
        if not math.isfinite(value) or value <= 0:
            parser.error(key+' 값은 유한한 양수여야 합니다.')
    if args.seconds < 2.:
        parser.error('정지 결합 검사는 최소 2초여야 합니다.')
    if args.fruit_index < 0 or (args.expected_fruits is not None and args.expected_fruits <= 0):
        parser.error('과실 index/count 범위를 확인하세요.')
    return args


def wheel_properties(stage: object, robot: object) -> dict:
    """바퀴/캐스터 subtree의 저작값. 실행 중 상태와 구분하여 물성 변경을 검사합니다."""
    from pxr import Usd
    result = {}
    for prim in Usd.PrimRange(robot, Usd.TraverseInstanceProxies()):
        if not any(key in str(prim.GetPath()).lower() for key in ('wheel', 'caster')):
            continue
        result[str(prim.GetPath())] = dict(
            attributes={str(attr.GetName()): str(attr.Get()) for attr in prim.GetAttributes()},
            relationships={str(rel.GetName()): [str(p) for p in rel.GetTargets()] for rel in prim.GetRelationships()})
    if not result:
        raise ValueError('수확 로봇에서 바퀴/캐스터 저작값을 찾지 못했습니다.')
    return result


def execute(args: argparse.Namespace, report: dict) -> None:
    """Isaac 앱 한 개와 full-farm scene에서 검사하고 수치 결과를 report에 저장합니다."""
    root = args.project_root.expanduser().resolve()
    for package in ('farm_sim_runtime', 'farm_sim_devices'):
        sys.path.insert(0, str(root/'sim/ros_ws/src'/package))
    config_path = (root/args.config).resolve()
    device_path = (root/args.device_config).resolve()
    config = json.loads(config_path.read_text())
    device = json.loads(device_path.read_text())
    if not config.get('enabled', False):
        raise ValueError('오른팔 물리 프로파일이 비활성입니다.')
    survey = json.loads((root/config['survey_config']).read_text())
    scene = (root/args.scene).resolve() if args.scene else root/'sim/assets'/device['scene']
    scene_hash = digest(scene)
    report.update(config=str(config_path), scene=str(scene), scene_sha256_before=scene_hash,
                  policy_loaded=False, scope='full_farm_physics_only', checks={})
    hz, render_hz = float(config['physics_hz']), float(config['render_hz'])
    if hz <= 0 or render_hz <= 0 or not np.isfinite([hz, render_hz]).all():
        raise ValueError('물리/렌더 주기는 유한한 양수여야 합니다.')
    render_every = round(hz/render_hz)
    if render_every < 1 or not math.isclose(hz/render_hz, render_every):
        raise ValueError('physics_hz/render_hz는 양의 정수비여야 합니다.')
    dt = 1/hz
    report.update(physics_hz=hz, render_hz=render_hz, dt_s=dt)
    from isaacsim import SimulationApp
    sys.argv = [sys.argv[0]]
    # 기본 fast_shutdown=True는 close()에서 프로세스를 즉시 종료하여 예외/종료코드를
    # 잃을 수 있습니다. SDK의 명시적 graceful 종료와 종료 전 결과 저장을 함께 사용합니다.
    app = SimulationApp({'headless': not args.gui, 'renderer': 'RayTracedLighting', 'fast_shutdown': False})
    world = None
    try:
        import omni.usd
        from pxr import Gf, Usd, UsdGeom, UsdPhysics
        from isaacsim.core.api import World
        from isaacsim.core.prims import SingleArticulation
        from isaacsim.core.utils.stage import open_stage
        from isaacsim.core.utils.types import ArticulationAction
        from farm_sim_runtime.fruit_asset_setup import configure_farm_fruits
        from farm_sim_runtime.robotarm_asset_setup import configure_harvest_arm
        from farm_sim_runtime.bed_collisions import ensure_bed_collisions
        from farm_sim_devices.fruit_attachment import FruitAttachments

        if not open_stage(str(scene)):
            raise RuntimeError('농장 scene을 열지 못했습니다.')
        stage = omni.usd.get_context().get_stage()
        stage.SetEditTarget(stage.GetSessionLayer())
        if UsdGeom.GetStageUpAxis(stage) != 'Z' or not math.isclose(UsdGeom.GetStageMetersPerUnit(stage), 1., abs_tol=1e-9):
            raise ValueError('농장 scene은 m/Z-up이어야 합니다.')
        report['bed_collisions'] = ensure_bed_collisions(stage)
        binding = device['scene_binding']
        candidates = binding.get('robot_prim_candidates', [binding['robot_prim']])
        robot_path = next((p for p in candidates if stage.GetPrimAtPath(p).IsValid()), binding['robot_prim'])
        robot_prim = stage.GetPrimAtPath(robot_path)
        if not robot_prim.IsValid():
            asset = root/'sim/assets'/binding['asset_file']
            if not asset.is_file():
                raise FileNotFoundError(asset)
            robot_prim = UsdGeom.Xform.Define(stage, robot_path).GetPrim()
            robot_prim.GetReferences().AddReference(str(asset))
        stage.Load(robot_path)
        body_path = robot_path+'/'+binding['articulation_relative']
        body = stage.GetPrimAtPath(body_path)
        if not body.IsValid() or not body.HasAPI(UsdPhysics.ArticulationRootAPI):
            raise ValueError('수확 articulation root가 잘못됐습니다: '+body_path)
        wheel_before = wheel_properties(stage, robot_prim)
        cache = UsdGeom.XformCache()
        base_before = np.asarray(cache.GetLocalToWorldTransform(body), dtype=float)
        arm_config = deepcopy(config)
        if arm_config.get('box_floor', {}).get('enabled', False):
            arm_config['box_floor']['asset_path'] = str((root/arm_config['box_floor']['asset_path']).resolve())
        report['arm_setup'] = configure_harvest_arm(stage, robot_path, arm_config)
        fruits = configure_farm_fruits(stage, root, config['fruit'], survey)
        expected = args.expected_fruits if args.expected_fruits is not None else config['fruit'].get('expected_count')
        report['fruit_count'] = len(fruits)
        if expected is not None and len(fruits) != int(expected):
            raise AssertionError(f'전체 과실 개수 불일치: {len(fruits)} != {expected}')
        if not fruits:
            raise AssertionError('과실이 없습니다.')
        if args.fruit_index >= len(fruits):
            raise ValueError('fruit-index가 전체 과실 개수 이상입니다.')
        cache.Clear()
        report['checks']['wheel_authoring_preserved'] = wheel_before == wheel_properties(stage, robot_prim)
        report['checks']['base_authoring_preserved'] = bool(np.array_equal(base_before, np.asarray(cache.GetLocalToWorldTransform(body))))
        scenes = [str(p.GetPath()) for p in stage.Traverse() if p.IsA(UsdPhysics.Scene)]
        if len(scenes) > 1:
            raise ValueError('PhysicsScene이 여러 개입니다.')
        world = World(physics_dt=dt, rendering_dt=1/render_hz, stage_units_in_meters=1.,
                      physics_prim_path=scenes[0] if scenes else '/World/physicsScene', backend='numpy')
        attachment = FruitAttachments(world, fruits, config['stem'])
        robot = world.scene.add(SingleArticulation(prim_path=body_path, name='harvest_physics_check'))
        world.reset()
        robot.initialize()
        names = report['arm_setup']['joint_names']
        joint_ids = np.asarray([robot.get_dof_index(name) for name in names], dtype=np.int32)
        if len(set(joint_ids.tolist())) != 6:
            raise AssertionError('오른팔 6개 관절 mapping이 잘못됐습니다.')
        home = np.asarray(report['arm_setup']['home_positions_rad'], dtype=float)
        if home.shape != (6,) or not np.isfinite(home).all():
            raise ValueError('오른팔 HOME 6개 값이 필요합니다.')
        wheel_ids = np.asarray([robot.get_dof_index(name) for name in device['base']['wheel_joints']], dtype=np.int32)
        robot.set_joint_positions(home, joint_indices=joint_ids)
        robot.set_joint_velocities(np.zeros(6), joint_indices=joint_ids)
        robot.apply_action(ArticulationAction(joint_positions=home, joint_indices=joint_ids))
        robot.apply_action(ArticulationAction(joint_velocities=np.zeros(len(wheel_ids)), joint_indices=wheel_ids))
        attachment.initialize()
        initial_positions, initial_orientations = (np.asarray(value).copy()
            for value in attachment.view.get_world_poses())
        selected = args.fruit_index
        selected_axis = attachment.axes[selected]/np.linalg.norm(attachment.axes[selected])
        report['selected_fruit'] = dict(index=selected, prim_path=attachment.paths[selected],
            threshold_n=float(attachment.thresholds[selected]),
            mass_kg=float(np.asarray(attachment.view.get_masses()).reshape(-1)[selected]),
            initial_root_world_m=initial_positions[selected].tolist(),
            initial_root_orientation_wxyz=initial_orientations[selected].tolist(),
            rest_orientation_wxyz=attachment.rest_orientation[selected].tolist(),
            center_of_mass_local_m=attachment.local_com[selected].tolist(),
            inverse_inertia_body_kg_inv_m_inv2=attachment.inverse_inertia[selected].tolist(),
            attachment_local_m=attachment.tips[selected].tolist(),
            anchor_world_m=attachment.anchors[selected].tolist(),
            tension_axis_world=selected_axis.tolist(), applied_force_location='world_center_of_mass',
            fruit_threshold_seed=config['fruit']['seed'],
            tension_diagnostic='tension_N는 복원력 상한 적용 후, raw_tension_N는 상한 적용 전 인장력입니다.')
        print('HARVEST_PHYSICS_SELECTED', json.dumps(report['selected_fruit'], ensure_ascii=False), flush=True)
        if args.gui:
            from isaacsim.core.utils.viewports import set_camera_view
            target = initial_positions[selected]
            sideways = np.cross(selected_axis, np.array([0., 0., 1.]))
            eye = target+.7*selected_axis+.25*sideways+np.array([0., 0., .22])
            set_camera_view(eye=eye, target=target)
            report['viewport'] = dict(eye_world_m=eye.tolist(), target_world_m=target.tolist())
        initial_base, initial_base_q = (np.asarray(value).copy() for value in robot.get_world_pose())
        initial_wheels = np.asarray(robot.get_joint_positions(joint_indices=wheel_ids)).copy()
        initial_home = np.asarray(robot.get_joint_positions(joint_indices=joint_ids)).copy()
        report['checks']['home_initialized'] = bool(np.allclose(initial_home, home, atol=1e-6))
        report['home_initial_rad'] = initial_home.tolist()
        report['checks']['masses_9g'] = bool(np.allclose(attachment.view.get_masses(), .009, atol=1e-8, rtol=1e-5))
        max_rest_drift = max_base_drift = max_wheel_drift = 0.
        events = []
        step_count = 0

        def step(*, pull_index: int | None = None, force_n: float | None = None) -> None:
            nonlocal step_count
            if not app.is_running() or not world.is_playing():
                raise RuntimeError('물리 검사 도중 Isaac/timeline이 중단됐습니다.')
            previous_time = float(world.current_time)
            events.extend(attachment.update(dt, previous_time))
            if pull_index is not None and attachment.attached[pull_index]:
                positions, orientations = attachment.view.get_world_poses()
                com = np.asarray(positions)+attachment._rotate(np.asarray(orientations), attachment.local_com)
                axis = attachment.axes[pull_index]
                magnitude = args.pull_force_n if force_n is None else force_n
                force = (axis/np.linalg.norm(axis)*magnitude)[None].astype(np.float32)
                attachment.view.apply_forces_and_torques_at_pos(forces=force,
                    positions=com[pull_index:pull_index+1].astype(np.float32),
                    indices=np.asarray([pull_index], dtype=np.int32), is_global=True)
            # render=True이면 60Hz app update 안에서 물리8tick이 진행될 수 있어 사용하지 않습니다.
            world.step(render=False)
            actual_dt = float(world.current_time)-previous_time
            if not math.isclose(actual_dt, dt, abs_tol=1e-7, rel_tol=1e-5):
                raise AssertionError(f'단일 외력 갱신당 물리 tick 불일치: {actual_dt} != {dt}')
            step_count += 1
            if step_count % render_every == 0:
                before_render = float(world.current_time)
                world.render()
                if not math.isclose(float(world.current_time), before_render, abs_tol=1e-9):
                    raise AssertionError('render가 별도 physics tick을 진행했습니다.')
            values = (*attachment.view.get_world_poses(), attachment.view.get_velocities(),
                      robot.get_joint_positions(), robot.get_joint_velocities(), *robot.get_world_pose())
            if not all(np.isfinite(value).all() for value in values):
                raise FloatingPointError('과실/로봇 상태에 비유한값이 있습니다.')

        def force_probe(seconds: float, force_n: float | None) -> dict:
            """부착 상태에서 평가한 최대값과 외력 초기 0.2초의 tick별 진단을 기록합니다."""
            ticks = math.ceil(seconds/dt)
            attached_before = int(attachment.attached.sum())
            velocity_before = np.asarray(attachment.view.get_velocities()[selected], dtype=float).copy()
            maxima = dict(extension_m=None, displacement_m=None, tension_n=None, raw_tension_n=None, sustained_s=None)
            attached_samples = 0
            trajectory = []
            start_time = float(world.current_time)
            for tick in range(ticks):
                was_attached = bool(attachment.attached[selected])
                sample = None
                if force_n is not None and tick < math.ceil(.2/dt):
                    # core 입력과 같은 pre-step pose/속도를 저장하여 원본 수식과 재대조할 수 있습니다.
                    positions, orientations = attachment.view.get_world_poses()
                    sample = dict(sim_time_s=float(world.current_time),
                        elapsed_s=float(world.current_time)-start_time, attached_before=was_attached,
                        root_world_m=np.asarray(positions[selected]).tolist(),
                        orientation_wxyz=np.asarray(orientations[selected]).tolist(),
                        velocity_world=np.asarray(attachment.view.get_velocities()[selected]).tolist())
                step(pull_index=selected if force_n is not None else None, force_n=force_n)
                state = attachment.last_step
                values = dict(extension_m=state.extension[selected], displacement_m=state.displacement[selected],
                    tension_n=state.tension[selected], raw_tension_n=state.raw_tension[selected],
                    sustained_s=state.timer[selected])
                # 이탈을 결정한 tick은 포함하며, 이미 이탈한 과실의 미적용 가상 줄기값은 제외합니다.
                if was_attached:
                    attached_samples += 1
                    for key, value in values.items():
                        maxima[key] = float(value) if maxima[key] is None else max(maxima[key], float(value))
                if sample is not None:
                    sample.update({key: float(value) for key, value in values.items()})
                    sample.update(attached_after=bool(state.attached[selected]),
                        probe_force_applied_n=force_n if state.attached[selected] else 0.,
                        applied_stem_force_world_n=state.force[selected].tolist(),
                        applied_stem_torque_world_nm=state.torque[selected].tolist())
                    trajectory.append(sample)
            return dict(force_n=0. if force_n is None else force_n, simulated_s=ticks*dt,
                threshold_n=float(attachment.thresholds[selected]), maxima=maxima,
                maxima_scope='attached_before_tick_including_detach_tick',
                maxima_sample_count=attached_samples, first_0_2s_trajectory=trajectory,
                selected_attached=bool(attachment.attached[selected]),
                attached_count_before=attached_before, attached_count_after=int(attachment.attached.sum()),
                detach_count=attached_before-int(attachment.attached.sum()),
                initial_velocity=velocity_before.tolist(),
                final_velocity=np.asarray(attachment.view.get_velocities()[selected], dtype=float).tolist())

        for tick in range(math.ceil(args.seconds/dt)):
            step()
            positions = np.asarray(attachment.view.get_world_poses()[0])
            max_rest_drift = max(max_rest_drift, float(np.linalg.norm(positions-initial_positions, axis=-1).max()))
            max_base_drift = max(max_base_drift, float(np.linalg.norm(np.asarray(robot.get_world_pose()[0])-initial_base)))
            max_wheel_drift = max(max_wheel_drift, float(np.abs(robot.get_joint_positions(joint_indices=wheel_ids)-initial_wheels).max()))
            if tick % round(hz) == 0:
                print('HARVEST_PHYSICS_REST', tick, attachment.summary(), flush=True)
        report['rest'] = dict(simulated_s=math.ceil(args.seconds/dt)*dt,
            max_root_displacement_m=max_rest_drift, max_base_displacement_m=max_base_drift,
            max_wheel_displacement_rad=max_wheel_drift, final_home_rad=robot.get_joint_positions(joint_indices=joint_ids).tolist(),
            initial_base_position_m=initial_base.tolist(), initial_base_orientation_wxyz=initial_base_q.tolist(),
            final_base_position_m=robot.get_world_pose()[0].tolist(), **attachment.summary())
        report['checks'].update(no_spontaneous_detach=bool(attachment.attached.all()),
            rest_displacement_bounded=max_rest_drift<=args.max_rest_drift_m,
            base_displacement_bounded=max_base_drift<=args.max_base_drift_m,
            wheel_displacement_bounded=max_wheel_drift<=args.max_wheel_drift_rad,
            finite_states=True, physics_tick_preserved=True)
        if args.pull and all(report['checks'].values()):
            hold = force_probe(args.hold_seconds, args.hold_force_n)
            recovery = force_probe(.5, None)
            report['hold_probe'] = dict(prim_path=attachment.paths[selected], hold=hold, recovery=recovery)
            report['checks']['low_force_stays_attached'] = bool(hold['selected_attached'] and hold['detach_count'] == 0)
            report['checks']['low_force_recovery_stays_attached'] = bool(recovery['selected_attached'] and recovery['detach_count'] == 0)
            console_hold = {name: {key: value for key, value in data.items() if key != 'first_0_2s_trajectory'}
                            for name, data in (('hold', hold), ('recovery', recovery))}
            print('HARVEST_PHYSICS_HOLD', json.dumps(console_hold, ensure_ascii=False), flush=True)
        if args.pull and all(report['checks'].values()):
            pull_start = float(world.current_time)
            while attachment.attached[selected] and float(world.current_time)-pull_start < args.pull_seconds:
                step(pull_index=selected)
            detached = not bool(attachment.attached[selected])
            report['checks']['selected_physically_detached'] = detached
            z_before = float(attachment.view.get_world_poses()[0][selected, 2])
            velocity_before = np.asarray(attachment.view.get_velocities()[selected], dtype=float).copy()
            fall_start = float(world.current_time)
            trajectory = [dict(elapsed_s=0., z_m=z_before, vz_mps=float(velocity_before[2]))]
            max_z, peak_time, min_vz = z_before, 0., float(velocity_before[2])
            fall_ticks = math.ceil(args.fall_seconds/dt)
            for tick in range(fall_ticks):
                step()
                z = float(attachment.view.get_world_poses()[0][selected, 2])
                vz = float(attachment.view.get_velocities()[selected, 2])
                elapsed = float(world.current_time)-fall_start
                if z > max_z:
                    max_z, peak_time = z, elapsed
                min_vz = min(min_vz, vz)
                if (tick+1) % render_every == 0 or tick+1 == fall_ticks:
                    trajectory.append(dict(elapsed_s=elapsed, z_m=z, vz_mps=vz))
            z_after = float(attachment.view.get_world_poses()[0][selected, 2])
            velocity_after = np.asarray(attachment.view.get_velocities()[selected], dtype=float)
            elapsed = fall_ticks*dt
            # 분리 직후 상향속도가 있을 수 있어 먼저 정점을 지난 뒤 낙하를 관측합니다.
            # 무접촉 자유낙하 예상치는 진단용이며 농장 충돌이 있으므로 일치 여부를 강제하지 않습니다.
            fell_with_downward_velocity = min_vz < -.05 and min_vz < float(velocity_before[2])
            report['pull'] = dict(prim_path=attachment.paths[selected], force_n=args.pull_force_n,
                detached=detached, post_force_seconds=elapsed, detached_z_m=z_before,
                detached_velocity=velocity_before.tolist(), final_z_m=z_after,
                peak_z_m=max_z, peak_elapsed_s=peak_time, minimum_vz_mps=min_vz,
                post_force_drop_m=z_before-z_after, drop_from_peak_m=max_z-z_after,
                ballistic_no_contact_z_m=z_before+float(velocity_before[2])*elapsed-.5*9.81*elapsed**2,
                ballistic_no_contact_vz_mps=float(velocity_before[2])-9.81*elapsed,
                final_velocity=velocity_after.tolist(), post_detach_trajectory=trajectory)
            report['checks']['detached_gravity_drop'] = bool(detached and
                z_before-z_after >= args.minimum_fall_m and fell_with_downward_velocity)
        report.update(detach_events=events, physics_steps=step_count, final=attachment.summary())
        report['scene_sha256_after'] = digest(scene)
        report['checks']['source_scene_preserved'] = report['scene_sha256_after'] == scene_hash
        failed = [key for key, value in report['checks'].items() if not value]
        if failed:
            raise AssertionError('물리 검사 실패: '+', '.join(failed))
        report['status'] = 'PASSED'
    except Exception as error:
        report.update(status='FAILED', error=type(error).__name__+': '+str(error), traceback=traceback.format_exc())
        raise
    finally:
        report['finished_at_utc'] = datetime.now(timezone.utc).isoformat()
        # cleanup 경로에서 Kit가 종료되더라도 이미 수행한 검사와 실패 원인은 보존합니다.
        persist_report(report)
        print('HARVEST_PHYSICS_PRE_SHUTDOWN', report['status'], report.get('error', ''),
              report['result_file'], flush=True)
        try:
            if world is not None:
                world.stop()
        finally:
            app.close(skip_cleanup=False)


def main() -> int:
    args = arguments()
    root = args.project_root.expanduser().resolve()
    now = datetime.now(timezone.utc)
    output = (root/args.output).resolve() if args.output else root/'sim/runs/robotarm'/('physics_smoke_'+now.strftime('%Y%m%dT%H%M%S.%fZ'))/'result.json'
    if not output.is_relative_to(root/'sim'):
        raise ValueError('물리 검사 결과는 sim 내부에 저장해야 합니다.')
    output.parent.mkdir(parents=True, exist_ok=True)
    report = dict(schema_version=1, started_at_utc=now.isoformat(), status='RUNNING',
                  requested_pull=args.pull, result_file=str(output))
    try:
        execute(args, report)
        report['status'] = 'PASSED'
    except Exception as error:
        report.update(status='FAILED', error=type(error).__name__+': '+str(error), traceback=traceback.format_exc())
    finally:
        report['finished_at_utc'] = datetime.now(timezone.utc).isoformat()
        persist_report(report)
    print('HARVEST_PHYSICS_RESULT', report['status'], output, flush=True)
    if report['status'] != 'PASSED':
        print(report.get('error', 'UNKNOWN'), flush=True)
    return 0 if report['status'] == 'PASSED' else 1


if __name__ == '__main__':
    exit_code = main()
    # main이 반환할 때 결과 JSON 저장과 SimulationApp.close의 정상 정리가 끝났습니다.
    # Kit 확장의 잔여 non-daemon thread가 CLI 종료를 막아도 실제 검사 종료코드를 보존합니다.
    # 라이브러리 import 경로에서는 강제 프로세스 종료를 호출하지 않습니다.
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(exit_code)
