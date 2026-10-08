"""기존 농장/과실의 실제 PhysX Teacher 측정 어댑터를 검사한다.

--dock-json의 T_world_logical_base에 reset 전에 로봇 전체만 처음 배치한다.
과실/로봇은 reset 후 이동시키지 않으며 HOME 초기화 뒤 drive 목표만 사용한다.
정책·수확 성공 검증은 이 도구의 범위가 아니다.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sys
import traceback

import numpy as np


def json_value(value: object) -> object:
    """측정 numpy 값을 손실 없이 JSON 배열/스칼라로 기록한다."""
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.generic):
        return value.item()
    raise TypeError(type(value).__name__)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project-root', type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument('--dock-json', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--ticks', type=int, default=24)
    args = parser.parse_args()
    if args.ticks <= 0:
        parser.error('--ticks must be positive')
    root = args.project_root.resolve()
    output = (root/args.output).resolve()
    if not output.is_relative_to(root/'sim'):
        parser.error('결과는 sim 안에 저장해야 합니다.')
    output.parent.mkdir(parents=True, exist_ok=True)
    config_dir = root/'sim/ros_ws/src/farm_sim_config/config'
    cfg = json.loads((config_dir/'harvest.json').read_text())
    physical = json.loads((config_dir/'robotarm_physics.json').read_text())
    policy = json.loads((config_dir/'teacher_policy.json').read_text())
    dock = json.loads((root/args.dock_json).read_text())
    for package in ('farm_sim_runtime', 'farm_sim_devices'):
        sys.path.insert(0, str(root/'sim/ros_ws/src'/package))
    source = root/'sim/assets'/cfg['scene']
    digest_before = hashlib.sha256(source.read_bytes()).hexdigest()
    report = dict(status='RUNNING', scope='actual_farm_teacher_device_only', checks={}, dock=dock,
                  started_at_utc=datetime.now(timezone.utc).isoformat(), result_file=str(output))
    from isaacsim import SimulationApp
    sys.argv = [sys.argv[0]]
    app = SimulationApp({'headless': True, 'renderer': 'RayTracedLighting', 'fast_shutdown': False})
    world = physics = None
    try:
        import omni.usd
        from pxr import Gf, UsdGeom, UsdPhysics
        from isaacsim.core.api import World
        from isaacsim.core.prims import SingleArticulation
        from isaacsim.core.utils.stage import open_stage
        from isaacsim.core.utils.types import ArticulationAction
        from farm_sim_runtime.harvest_physics import HarvestPhysics, initialize_arm_home
        from farm_sim_runtime.bed_collisions import ensure_bed_collisions
        from farm_sim_devices.control_frame import asset_from_control, station_root_transform
        from farm_sim_devices.teacher_device import TeacherDevice

        if not open_stage(str(source)):
            raise RuntimeError('농장 scene을 열지 못했습니다.')
        stage = omni.usd.get_context().get_stage()
        stage.SetEditTarget(stage.GetSessionLayer())
        ensure_bed_collisions(stage)
        physics = HarvestPhysics(stage, root, physical)
        binding = cfg['scene_binding']
        robot_path = next((p for p in binding['robot_prim_candidates'] if stage.GetPrimAtPath(p).IsValid()), binding['robot_prim'])
        robot_prim = stage.GetPrimAtPath(robot_path)
        if not robot_prim.IsValid():
            robot_prim = UsdGeom.Xform.Define(stage, robot_path).GetPrim()
            robot_prim.GetReferences().AddReference(str(root/'sim/assets'/binding['asset_file']))
        stage.Load(robot_path)
        body_path = robot_path+'/'+binding['articulation_relative']
        body = stage.GetPrimAtPath(body_path)
        cache = UsdGeom.XformCache()

        def matrix(prim: object) -> np.ndarray:
            return np.asarray(cache.GetLocalToWorldTransform(prim), dtype=float).T

        desired = np.asarray(dock['T_world_logical_base'], dtype=float)
        if desired.shape != (4, 4) or not np.isfinite(desired).all():
            raise ValueError('dock 4x4 변환이 필요합니다.')
        desired[2, 3] = matrix(body)[2, 3]
        placed = station_root_transform(desired, matrix(body), matrix(robot_prim), asset_from_control(binding))
        parent = robot_prim.GetParent()
        local = np.linalg.inv(matrix(parent)) @ placed
        xform = UsdGeom.Xformable(robot_prim)
        xform.ClearXformOpOrder()
        xform.SetResetXformStack(False)
        xform.AddTransformOp().Set(Gf.Matrix4d(*map(float, local.T.reshape(-1))))
        arm_report = physics.configure_robot(robot_path, robot_id=cfg['robot_id'])
        scenes = [str(p.GetPath()) for p in stage.Traverse() if p.IsA(UsdPhysics.Scene)]
        dt = 1/physical['physics_hz']
        world = World(physics_dt=dt, rendering_dt=1/physical['render_hz'], stage_units_in_meters=1.,
                      physics_prim_path=scenes[0], backend='numpy')
        articulation = world.scene.add(SingleArticulation(prim_path=body_path, name='teacher_device_probe'))
        physics.register(world, 'teacher_device_probe_'+datetime.now().strftime('%Y%m%dT%H%M%S'))
        device_config = dict(policy['device'], **{key: policy['runtime'][key] for key in
            ('box_min', 'box_max', 'box_contact_tolerance', 'box_bottom_contact_tolerance', 'sequence')})
        device = TeacherDevice(world, articulation, robot_path, physics, cfg['robot_id'], device_config)
        world.reset()
        articulation.initialize()
        initialize_arm_home(articulation, arm_report)
        wheels = np.asarray([articulation.get_dof_index(n) for n in cfg['base']['wheel_joints']], dtype=np.int32)
        articulation.apply_action(ArticulationAction(joint_velocities=np.zeros(len(wheels)), joint_indices=wheels))
        physics.initialize()
        device.initialize()
        physics.set_activity(cfg['robot_id'], True)
        physical_hz = physics.prepare_frame(float(world.current_time))
        if physical_hz != physical['physics_hz']:
            raise AssertionError('활성 수확 reference 주기가 아닙니다.')
        # 초기 HOME command가 실제 link transform에 반영된 다음 목표 snapshot을 만든다.
        physics.update(dt, float(world.current_time))
        world.step(render=False)
        device.observe_physics_tick(dt, float(world.current_time))
        candidates = device.candidates()
        report['candidates'] = candidates
        if not candidates:
            raise AssertionError('실제 초기 dock에 연속 근거리 후보가 없습니다.')
        target = next((c['target_id'] for c in candidates if c['target_id'] == dock.get('target_id')), candidates[0]['target_id'])
        device.select_target(target)
        initial = device.sample()
        report.update(target_id=target, initial=initial, lower_rad=device.lower, upper_rad=device.upper,
                      home_rad=device.home, contacts_initial=device.contacts_for_recovery(),
                      contact_shape=list(device._finger_view.get_contact_force_matrix(dt=dt).shape),
                      finger_paths=device._finger_paths, arm_contact_paths=device._arm_view.prim_paths)
        report['checks']['contact_shape'] = report['contact_shape'] == [2, len(physics.fruits), 3]
        report['checks']['finite_state'] = all(np.isfinite(initial[k]).all() for k in
            ('q', 'qd', 'tcp_position', 'fruit_position', 'fruit_com_position', 'fixed_force', 'moving_force'))
        report['checks']['home_initialized'] = bool(np.max(np.abs(initial['q']-device.home)) < .01)
        report['checks']['collision_shape'] = bool(initial['collision_vertices'].ndim == 2 and len(initial['collision_vertices']) > 8)
        report['checks']['target_attached'] = initial['attached']
        samples = []
        device.command(device.home)
        for _ in range(args.ticks):
            physics.update(dt, float(world.current_time))
            world.step(render=False)
            device.observe_physics_tick(dt, float(world.current_time))
            samples.append(device.sample())
        report['final'] = samples[-1]
        report['checks']['time_elapsed'] = bool(np.isclose(samples[-1]['time_s']-initial['time_s'], args.ticks*dt))
        report['checks']['source_preserved'] = digest_before == hashlib.sha256(source.read_bytes()).hexdigest()
        report['checks']['no_pose_teleport_after_reset'] = True
        report['status'] = 'PASSED' if all(report['checks'].values()) else 'FAILED'
        report['physics_summary'] = physics.attachments.summary()
    except Exception as error:
        report.update(status='FAILED', error=type(error).__name__+': '+str(error), traceback=traceback.format_exc())
    finally:
        report['finished_at_utc'] = datetime.now(timezone.utc).isoformat()
        output.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=json_value, allow_nan=False)+'\n')
        print('TEACHER_DEVICE_RESULT', report['status'], report.get('error', ''), output, flush=True)
        if physics is not None:
            physics.close()
        if world is not None:
            world.stop()
        app.close(skip_cleanup=False)
    return 0 if report['status'] == 'PASSED' else 1


if __name__ == '__main__':
    code = main()
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(code)
