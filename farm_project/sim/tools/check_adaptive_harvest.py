"""농장 전체의 60/480Hz 전환·근처 과실 활성화·실제 외력 분리를 검사합니다.

정책/주행 성공 시험이 아닙니다. 로봇은 초기 장면에서만 과실 근처에 배치하며,
실행 중 과실 pose·분리 상태·mount 위치를 강제로 바꾸지 않습니다.
"""
import argparse
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import sys
import traceback

import numpy as np

from check_harvest_physics import digest, persist_report


class PullProbe:
    """운영 줄기 갱신 후 선택 과실 COM에만 시험 외력을 합산합니다."""

    def __init__(self, physics: object) -> None:
        self.physics, self.selected = physics, None

    def update(self, dt_s: float, sim_time_s: float) -> None:
        self.physics.update(dt_s, sim_time_s)
        attachment, index = self.physics.attachments, self.selected
        if index is None or not attachment.attached[index]:
            return
        from farm_sim_devices.stem_physics import quaternion_matrix
        position, orientation = attachment.view.get_world_poses(indices=np.array([index], dtype=np.int32))
        com = np.asarray(position) + (quaternion_matrix(np.asarray(orientation)) @ attachment.local_com[index:index+1, :, None])[..., 0]
        axis = attachment.axes[index] / np.linalg.norm(attachment.axes[index])
        attachment.view.apply_forces_and_torques_at_pos(forces=(3.*axis)[None].astype(np.float32),
            positions=com.astype(np.float32), indices=np.array([index], dtype=np.int32), is_global=True)


def exercise(world: object, physics: object, schedule: object, report: dict) -> None:
    """공개 활동 입력과 실제 물리 응답만으로 전환·분리 동작을 검증합니다."""
    from pxr import UsdPhysics
    attachment = physics.attachments
    anchors, rest = attachment.anchors.copy(), attachment.rest_orientation.copy()
    initial = np.asarray(attachment.view.get_world_poses()[0]).copy()
    checks, trace = report['checks'], []
    start = float(world.current_time)
    probe = PullProbe(physics)

    def frame(label: str) -> int:
        before = float(world.current_time)
        hz = physics.prepare_frame(before)
        schedule.step_frame(world, probe, physics_hz=hz)
        positions = np.asarray(attachment.view.get_world_poses()[0])
        if not np.isfinite(positions).all() or not np.isfinite(attachment.current_velocities()).all():
            raise FloatingPointError('과실 상태가 비유한값입니다.')
        trace.append(dict(phase=label, start_s=before, end_s=float(world.current_time), physics_hz=hz,
                          active=int(attachment.active.sum()), detached=int((~attachment.attached).sum())))
        return hz

    def require(name: str, condition: bool) -> None:
        checks[name] = bool(condition)
        if not condition:
            raise AssertionError(name)

    def until_idle(label: str) -> None:
        for _ in range(120):
            if frame(label) == 60:
                return
        raise AssertionError(label+': 2초 안에 idle 60Hz로 복귀하지 않았습니다.')

    report['trace'] = trace
    for _ in range(30):
        require('idle_60hz', frame('idle') == 60)
    require('all_288_initially_frozen', len(attachment.paths) == 288 and not attachment.active.any()
        and all(UsdPhysics.RigidBodyAPI(world.stage.GetPrimAtPath(path)).GetKinematicEnabledAttr().Get()
                for path in attachment.paths))
    require('idle_pose_preserved', np.allclose(attachment.view.get_world_poses()[0], initial, atol=1e-5, rtol=0))
    physics.set_activity('adaptive_test_harvest', True)
    require('harvest_480hz', frame('activate') == 480)
    active = np.flatnonzero(attachment.active)
    require('only_near_fruits_active', 0 < len(active) < 288)
    selected, far = int(active[0]), int(np.flatnonzero(~attachment.active)[-1])
    report['selected_fruit'] = dict(index=selected, prim_path=attachment.paths[selected],
        threshold_n=float(attachment.thresholds[selected]), tension_axis_world=attachment.axes[selected].tolist())
    report['active_count'] = len(active)
    report['far_fruit'] = attachment.paths[far]
    for _ in range(60):
        require('active_rate_480hz', frame('attached_rest') == 480)
    require('no_spontaneous_detach', attachment.attached.all())
    physics.set_activity('adaptive_test_harvest', False)
    until_idle('freeze')
    frozen_pose = np.asarray(attachment.view.get_world_poses()[0]).copy()
    require('attached_region_frozen', not attachment.active.any())
    for _ in range(6):
        frame('frozen_rest')
    require('freeze_preserves_settled_pose', np.allclose(attachment.view.get_world_poses()[0], frozen_pose, atol=1e-5, rtol=0))
    physics.set_activity('adaptive_test_harvest', True)
    hz = physics.prepare_frame(float(world.current_time))
    require('reactivation_does_not_teleport', np.allclose(attachment.view.get_world_poses()[0], frozen_pose, atol=1e-5, rtol=0))
    require('reactivation_selects_same_fruit', attachment.active[selected] and hz == 480)
    for _ in range(30):
        frame('reactivate_settle')
    probe.selected = selected
    for _ in range(60):
        frame('pull_3n')
        if not attachment.attached[selected]:
            break
    probe.selected = None
    require('physically_detached', not attachment.attached[selected])
    z_start = float(attachment.view.get_world_poses()[0][selected, 2])
    velocity_start = attachment.current_velocities()[selected].copy()
    physics.set_activity('adaptive_test_harvest', False)
    min_vz, max_z = float(velocity_start[2]), z_start
    for _ in range(42):
        frame('gravity_coast')
        min_vz = min(min_vz, float(attachment.current_velocities()[selected, 2]))
        max_z = max(max_z, float(attachment.view.get_world_poses()[0][selected, 2]))
        require('detached_stays_dynamic', attachment.active[selected] and not
            UsdPhysics.RigidBodyAPI(world.stage.GetPrimAtPath(attachment.paths[selected])).GetKinematicEnabledAttr().Get())
    z_end = float(attachment.view.get_world_poses()[0][selected, 2])
    report['gravity'] = dict(start_z_m=z_start, end_z_m=z_end, peak_z_m=max_z,
        drop_m=z_start-z_end, minimum_vz_m_s=min_vz, initial_velocity=velocity_start.tolist())
    require('gravity_drop_after_detach', z_start-z_end >= .003 and min_vz < -.05)
    until_idle('post_detach_settle')
    require('anchors_and_rest_preserved', np.array_equal(anchors, attachment.anchors) and np.array_equal(rest, attachment.rest_orientation))
    require('far_fruit_unchanged', np.allclose(attachment.view.get_world_poses()[0][far], initial[far], atol=1e-5, rtol=0))
    require('all_objects_preserved', len(attachment.paths) == 288 and
        all(world.stage.GetPrimAtPath(path).IsValid() for path in attachment.paths))
    require('continuous_frame_time', math.isclose(float(world.current_time)-start, schedule.frame_count/60, abs_tol=1e-6))
    report.update(frame_count=schedule.frame_count, physics_ticks=schedule.total_ticks,
        simulated_s=float(world.current_time)-start, final=attachment.summary(),
        detach_events=[json.loads(line) for line in (physics.directory/'detach_events.jsonl').read_text().splitlines()])


def execute(args: argparse.Namespace, report: dict) -> None:
    root = args.project_root.resolve()
    for package in ('farm_sim_runtime', 'farm_sim_devices'):
        sys.path.insert(0, str(root/'sim/ros_ws/src'/package))
    profile = json.loads((root/args.config).read_text())
    if not profile.get('adaptive', {}).get('enabled', False):
        raise ValueError('adaptive가 활성화된 물리 프로파일이 필요합니다.')
    device = json.loads((root/profile['harvest_device_config']).read_text())
    scene = root/'sim/assets'/device['scene']
    report.update(scene=str(scene), scene_sha256_before=digest(scene), checks={}, policy_loaded=False)
    from isaacsim import SimulationApp
    sys.argv = [sys.argv[0]]
    app = SimulationApp(dict(headless=not args.gui, renderer='RayTracedLighting', fast_shutdown=False))
    world = physics = None
    try:
        import omni.usd
        from pxr import Gf, UsdGeom, UsdPhysics
        from isaacsim.core.api import World
        from isaacsim.core.prims import SingleArticulation
        from isaacsim.core.utils.stage import open_stage
        from isaacsim.core.utils.types import ArticulationAction
        from farm_sim_runtime.bed_collisions import ensure_bed_collisions
        from farm_sim_runtime.harvest_physics import HarvestPhysics, initialize_arm_home
        from farm_sim_runtime.physics_schedule import AdaptivePhysicsTicks
        if not open_stage(str(scene)):
            raise RuntimeError('농장 scene 열기 실패')
        stage = omni.usd.get_context().get_stage()
        stage.SetEditTarget(stage.GetSessionLayer())
        ensure_bed_collisions(stage)
        binding = device['scene_binding']
        path = next((p for p in binding.get('robot_prim_candidates', []) if stage.GetPrimAtPath(p).IsValid()), binding['robot_prim'])
        prim = stage.GetPrimAtPath(path)
        if not prim.IsValid():
            prim = UsdGeom.Xform.Define(stage, path).GetPrim()
            prim.GetReferences().AddReference(str(root/'sim/assets'/binding['asset_file']))
        stage.Load(path)
        physics = HarvestPhysics(stage, root, profile)
        arm = physics.configure_robot(path, robot_id='adaptive_test_harvest')
        mount_path = physics.harvesters['adaptive_test_harvest']['mount_path']
        report['mount_path'] = mount_path
        cache = UsdGeom.XformCache()
        mount_before = np.asarray(cache.GetLocalToWorldTransform(stage.GetPrimAtPath(mount_path)).ExtractTranslation(), dtype=float)
        first = physics.fruits[0]
        fruit_position = np.asarray(first['initial_position_world_m'], dtype=float)
        axis = np.asarray(first['tension_axis_world'], dtype=float)
        target_mount_xy = fruit_position[:2]+.5*axis[:2]
        transform = np.asarray(cache.GetLocalToWorldTransform(prim)).T.copy()
        # 최초 reset 전에만 실제 장착점이 첫 과실의 통로 쪽 0.5m에 오도록 배치합니다.
        transform[:2, 3] += target_mount_xy-mount_before[:2]
        local = np.linalg.inv(np.asarray(cache.GetLocalToWorldTransform(prim.GetParent())).T) @ transform
        xform = UsdGeom.Xformable(prim)
        xform.ClearXformOpOrder()
        xform.AddTransformOp(opSuffix='adaptiveTestStart').Set(Gf.Matrix4d(*local.T.reshape(-1)))
        report['robot_initial_world_transform'] = transform.tolist()
        cache.Clear()
        mount_after = np.asarray(cache.GetLocalToWorldTransform(stage.GetPrimAtPath(mount_path)).ExtractTranslation(), dtype=float)
        fruit_positions = np.asarray([fruit['initial_position_world_m'] for fruit in physics.fruits])
        report['initial_placement'] = dict(reference_fruit=first['prim_path'],
            reference_fruit_world_m=fruit_position.tolist(), tension_axis_world=axis.tolist(),
            mount_before_world_m=mount_before.tolist(), mount_after_world_m=mount_after.tolist(),
            target_mount_xy_m=target_mount_xy.tolist(),
            reference_fruit_distance_m=float(np.linalg.norm(mount_after-fruit_position)),
            nearest_fruit_distance_m=float(np.linalg.norm(fruit_positions-mount_after, axis=1).min()))
        scenes = [str(p.GetPath()) for p in stage.Traverse() if p.IsA(UsdPhysics.Scene)]
        if len(scenes) > 1:
            raise ValueError('PhysicsScene이 여러 개입니다.')
        world = World(physics_dt=1/480, rendering_dt=1/60, backend='numpy', stage_units_in_meters=1.,
                      physics_prim_path=scenes[0] if scenes else '/World/physicsScene')
        physics.register(world, 'adaptive_check_'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%f'))
        report['physics_log_directory'] = str(physics.directory)
        robot = world.scene.add(SingleArticulation(prim_path=path+'/'+binding['articulation_relative'], name='adaptive_check_robot'))
        world.reset()
        robot.initialize()
        initialize_arm_home(robot, arm)
        wheels = np.asarray([robot.get_dof_index(name) for name in device['base']['wheel_joints']], dtype=np.int32)
        robot.apply_action(ArticulationAction(joint_velocities=np.zeros(len(wheels)), joint_indices=wheels))
        physics.initialize()
        if args.gui:
            from isaacsim.core.utils.viewports import set_camera_view
            eye = fruit_position+.9*axis+.4*np.cross(axis, [0., 0., 1.])+[0., 0., .45]
            set_camera_view(eye=eye, target=fruit_position)
        exercise(world, physics, AdaptivePhysicsTicks(480, 60), report)
        report['scene_sha256_after'] = digest(scene)
        report['checks']['source_scene_preserved'] = report['scene_sha256_after'] == report['scene_sha256_before']
        if not all(report['checks'].values()):
            raise AssertionError('adaptive 검사 실패')
        report['status'] = 'PASSED'
    except Exception as error:
        report.update(status='FAILED', error=repr(error), traceback=traceback.format_exc())
        raise
    finally:
        persist_report(report)
        print('ADAPTIVE_PRE_SHUTDOWN', report['status'], report.get('error', ''), flush=True)
        try:
            if physics is not None:
                physics.close()
        finally:
            try:
                if world is not None:
                    world.stop()
            finally:
                app.close(skip_cleanup=False)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project-root', type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument('--config', type=Path, default=Path('sim/ros_ws/src/farm_sim_config/config/robotarm_physics.json'))
    parser.add_argument('--output', type=Path, default=Path('sim/runs/robotarm/adaptive_20261006/result.json'))
    parser.add_argument('--gui', action='store_true')
    args = parser.parse_args()
    output = (args.project_root/args.output).resolve()
    if not output.is_relative_to(args.project_root.resolve()/'sim/runs'):
        parser.error('결과는 프로젝트의 sim/runs 내부에 저장해야 합니다.')
    output.parent.mkdir(parents=True, exist_ok=True)
    report = dict(status='RUNNING', result_file=str(output), started_at_utc=datetime.now(timezone.utc).isoformat())
    try:
        execute(args, report)
    except Exception as error:
        report.update(status='FAILED', error=repr(error), traceback=traceback.format_exc())
    report['finished_at_utc'] = datetime.now(timezone.utc).isoformat()
    persist_report(report)
    print('ADAPTIVE_RESULT', report['status'], output, flush=True)
    return 0 if report['status'] == 'PASSED' else 1


if __name__ == '__main__':
    code = main()
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(code)
