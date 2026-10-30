"""시뮬 전용 다중 articulation 실행. v0.8.5 물리 연결부를 현재 설정 계약에 이식."""
import argparse
from collections import deque
import json
import math
from pathlib import Path
import sys
import time
import uuid
import numpy as np


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--project-root', type=Path, required=True)
    parser.add_argument('--fleet-config', type=Path, required=True)
    parser.add_argument('--assets-root', type=Path)
    parser.add_argument('--module-path', action='append', default=[])
    parser.add_argument('--scene', type=Path)
    parser.add_argument('--headless', action='store_true')
    parser.add_argument('--physics-device', choices=('cpu', 'gpu'),
                        help='비교 시험용 PhysX 실행 장치. 생략하면 기존 물리 프로파일 유지')
    parser.add_argument('--performance-log', type=Path,
                        help='일반 fleet의 프레임별 물리/렌더/센서/평가 시간 JSONL')
    parser.add_argument('--harvest-test-ui', action='store_true',
                        help='독립 시험용 배치/가변 Hz 수확 패널. sim/tools/harvest_test_ui.py에서 실행')
    parser.add_argument('--harvest-test-seed', type=int)
    parser.add_argument('--harvest-test-auto-run', action='store_true',
                        help='검증용: 패널 배치→정지 확인→수확 버튼을 한 번 자동 실행')
    parser.add_argument('--harvest-test-auto-physics', action='store_true',
                        help='검증용: 배치 후 팔 없이 주변 물리8초 관찰→비활성 요청')
    parser.add_argument('--stop-after-arm-job', action='store_true',
                        help='검증용: 첫 팔 작업의 최종 결과를 보낸 프레임 뒤 정상 종료')
    parser.add_argument('--teacher-diagnostic-trace', action='store_true',
                        help='회신용 실제 관측/정규화/정책 출력과 USD·PhysX·복귀 연속 기록')
    parser.add_argument('--duration-s', type=float, help='검증용 실행 시간(시뮬레이션 초). 생략하면 계속 실행')
    args = parser.parse_args()
    if ((args.harvest_test_ui and args.headless)
            or ((args.harvest_test_auto_run or args.harvest_test_auto_physics) and not args.harvest_test_ui)
            or (args.harvest_test_auto_run and args.harvest_test_auto_physics)):
        parser.error('수확 시험 UI는 GUI에서 실행하며 auto-run은 시험 UI 전용입니다.')
    if args.duration_s is not None and (not math.isfinite(args.duration_s) or args.duration_s <= 0):
        parser.error('--duration-s는 유한한 양수여야 합니다.')
    root = args.project_root.expanduser().resolve()
    for module_path in args.module_path:
        sys.path.insert(0, str(Path(module_path).resolve()))
    from farm_sim_runtime.fleet_config import load_fleet
    configs, task = load_fleet(root, args.fleet_config)
    if args.harvest_test_ui:
        if task['harvest_robot'] is None:
            parser.error('수확 시험 UI에는 evaluation_config가 필요합니다.')
        snapshot = Path(task['harvest_robot']['scene_snapshot_file']).resolve()
        if len(configs) != 1 or not snapshot.is_relative_to(root/'sim/runs/harvest_test_ui'):
            parser.error('sim/tools/harvest_test_ui.py의 독립 설정으로 실행하세요.')
    from farm_sim_runtime.harvest_physics import (
        HarvestPhysics, initialize_arm_travel, load_physics_profile)
    from farm_sim_runtime.physics_schedule import AdaptivePhysicsTicks
    physics_profile = load_physics_profile(root, configs)
    assets = args.assets_root.resolve() if args.assets_root else root/'sim/assets'
    scene = args.scene.expanduser().resolve() if args.scene else assets/configs[0]['scene']
    if not scene.is_file():
        raise FileNotFoundError(scene)
    from isaacsim import SimulationApp
    sys.argv = [sys.argv[0]]
    app = SimulationApp({'headless':args.headless, 'disable_viewport_updates':args.headless,
                         'renderer':'RayTracedLighting', 'fast_shutdown':False})
    world, robots, clock_transport, harvest_physics = None, [], None, None
    test_controller, test_panel = None, None
    performance_log = None
    sorter_scene, sorter_runtime = None, None
    try:
        import omni.usd
        from pxr import UsdGeom, UsdPhysics, Gf, Usd
        from isaacsim.core.api import World
        from isaacsim.core.utils.stage import open_stage
        from farm_sim_runtime.drive_diagnostics import DriveDiagnostics
        from farm_sim_devices.base_sim import BaseSim
        from farm_sim_devices.camera_sim import CameraSim
        from farm_sim_devices.lidar_sim import LidarSim
        from farm_sim_devices.wire import LocalDatagrams, CommandGate
        from farm_sim_devices.scene_truth import SceneTruth
        from farm_sim_devices.teacher_device import TeacherDevice
        from farm_sim_devices.arm_session import ArmSession
        from farm_sim_devices.control_frame import (
            asset_from_control, station_root_transform, relative_sensor_transforms)
        if not open_stage(str(scene)):
            raise RuntimeError('Cannot open scene '+str(scene))
        stage = omni.usd.get_context().get_stage()
        stage.SetEditTarget(stage.GetSessionLayer())
        if UsdGeom.GetStageUpAxis(stage) != 'Z' or abs(UsdGeom.GetStageMetersPerUnit(stage)-1.) > 1e-8:
            raise ValueError('Scene must use metres and Z-up')
        from farm_sim_runtime.bed_collisions import ensure_bed_collisions
        print('[farm_fleet] bed collisions: '+json.dumps(ensure_bed_collisions(stage)), flush=True)
        from farm_sim_runtime.scout_mount import install_scout_mount, scout_mount_static_tf
        from farm_sim_runtime.apriltag_scene import install_tags, mount_camera
        for cfg in configs:
            print('[farm_fleet] AprilTags: '+str(install_tags(stage, root, cfg)), flush=True)
        if physics_profile is not None:
            harvest_physics = HarvestPhysics(stage, root, physics_profile)
        if task.get('sorter'):
            from farm_sim_runtime.sorter_scene import SorterScene
            sorter_scene = SorterScene(stage, root, task['sorter'], harvest_physics)
        cache = UsdGeom.XformCache()
        def matrix(prim):
            return np.asarray(cache.GetLocalToWorldTransform(prim), float).T
        def require(path):
            p = stage.GetPrimAtPath(path)
            if not p.IsValid():
                raise RuntimeError('Missing scene prim: '+str(path))
            return p
        def static_tf(parent, child, T):
            q = Gf.Matrix4d(*map(float, T.T.reshape(-1))).ExtractRotationQuat()
            return dict(parent=parent, child=child, translation=T[:3,3].tolist(),
                        rotation_xyzw=[*map(float,q.GetImaginary()),float(q.GetReal())])
        T_map_world = np.asarray(task.get('evaluation',{}).get('T_map_world',np.eye(4)),float)
        if T_map_world.shape != (4,4) or not np.allclose(T_map_world[:3,:3].T@T_map_world[:3,:3],np.eye(3),atol=1e-6):
            raise ValueError('Invalid independently configured map/world registration')
        # Reposition entire robot roots before physics initialization. Never save the source USD.
        bindings = []
        for cfg in configs:
            binding = cfg['scene_binding']
            T_asset_control = asset_from_control(binding)
            candidates = binding.get('robot_prim_candidates',[binding['robot_prim']])
            robot_path = next((p for p in candidates if stage.GetPrimAtPath(p).IsValid()), binding['robot_prim'])
            robot = stage.GetPrimAtPath(robot_path)
            if not robot.IsValid():
                asset = assets/binding['asset_file']
                if not asset.is_file():
                    raise FileNotFoundError('Robot asset not found: '+str(asset))
                robot = UsdGeom.Xform.Define(stage,robot_path).GetPrim()
                robot.GetReferences().AddReference(str(asset))
            stage.Load(robot_path)
            mount_camera(stage, robot_path, cfg)
            install_scout_mount(stage, root, robot_path, cfg)
            if harvest_physics is not None and (cfg['robot_id'] == (task['harvest_robot'] or {}).get('robot_id')
                    or cfg['runtime'].get('harvest_activity', {}).get('enabled', False)):
                harvest_physics.configure_robot(robot_path, robot_id=cfg['robot_id'],
                    activity_config=cfg['runtime'].get('harvest_activity'))
            body = require(robot_path+'/'+binding['articulation_relative'])
            if not body.HasAPI(UsdPhysics.ArticulationRootAPI):
                raise RuntimeError('Not an articulation root: '+str(body.GetPath()))
            cache.Clear()
            old_body, old_root = matrix(body), matrix(robot)
            station = task['stations'][cfg['robot_id']]
            yaw = float(station['yaw_rad'])
            desired_map = np.eye(4)
            desired_map[:3,:3] = [[math.cos(yaw),-math.sin(yaw),0],[math.sin(yaw),math.cos(yaw),0],[0,0,1]]
            desired_map[:3,3] = [*station['xy_m'],float((T_map_world@old_body)[2,3])]
            desired_world = np.linalg.inv(T_map_world)@desired_map
            root_world = station_root_transform(desired_world,old_body,old_root,T_asset_control)
            parent = robot.GetParent()
            parent_world = matrix(parent) if parent.IsValid() and not parent.IsPseudoRoot() else np.eye(4)
            local = np.linalg.inv(parent_world)@root_world
            xform = UsdGeom.Xformable(robot)
            xform.ClearXformOpOrder()
            xform.SetResetXformStack(False)
            xform.AddTransformOp().Set(Gf.Matrix4d(*map(float,local.T.reshape(-1))))
            cache.Clear()
            if not np.allclose(matrix(body)@T_asset_control, desired_world, atol=1e-5):
                raise RuntimeError('station root transform failed: '+cfg['robot_id'])
            inv = np.linalg.inv(matrix(body)@T_asset_control)
            link = require(robot_path+'/'+binding['base_link_relative'])
            scan = require(robot_path+'/'+binding['lidar_relative'])
            T_link, T_scan = relative_sensor_transforms(
                matrix(body),matrix(link),matrix(scan),T_asset_control)
            frames = cfg['frames']
            static = [static_tf(frames['base_footprint'],frames['base_link'],T_link),
                      static_tf(frames['base_link'],frames['scan'],np.linalg.inv(T_link)@T_scan)]
            camera_path, T_camera = None, None
            if cfg['camera']['enabled']:
                camera_prim = require(robot_path+'/'+binding['camera_relative'])
                if not camera_prim.IsA(UsdGeom.Camera):
                    raise RuntimeError('Configured camera is not a USD Camera')
                camera_path = str(camera_prim.GetPath())
                T_camera = inv@matrix(camera_prim)@np.diag([1.,-1.,-1.,1.])
                static.append(static_tf(frames['base_link'],frames['camera_optical'],np.linalg.inv(T_link)@T_camera))
            static.extend(scout_mount_static_tf(stage, robot_path, cfg))
            tag_camera_path,T_tag_camera=None,None
            if cfg.get('tag_camera',{}).get('enabled'):
                tag_prim=require(robot_path+'/'+binding['tag_camera_relative'])
                if not tag_prim.IsA(UsdGeom.Camera):
                    raise RuntimeError('Configured tag_camera is not a USD Camera')
                tag_camera_path=str(tag_prim.GetPath())
                T_tag_camera=inv@matrix(tag_prim)@np.diag([1.,-1.,-1.,1.])
                if not np.allclose(T_tag_camera[:3,:3].T@T_tag_camera[:3,:3],np.eye(3),atol=1e-5):
                    raise RuntimeError('tag_camera에 비단위 scale이 있습니다.')
            bindings.append((cfg,robot_path,str(body.GetPath()),static,T_scan,camera_path,T_camera,
                             tag_camera_path,T_tag_camera,T_asset_control))
        from farm_sim_runtime.docking_marker_scene import install_docking_markers
        print('[docking_markers] '+json.dumps(install_docking_markers(
            stage, root, task.get('docking_markers'))), flush=True)
        scenes = [str(p.GetPath()) for p in stage.Traverse() if p.IsA(UsdPhysics.Scene)]
        if len(scenes) > 1:
            raise RuntimeError('Multiple PhysicsScene prims; select one scene before running')
        dt = 1./configs[0]['runtime']['physics_hz']
        ticks = AdaptivePhysicsTicks(configs[0]['runtime']['physics_hz'], configs[0]['runtime']['render_hz'],
                                     batch_usd_writeback=args.harvest_test_ui)
        frame_dt = ticks.frame_dt
        world = World(physics_dt=dt,rendering_dt=1./configs[0]['runtime']['render_hz'],stage_units_in_meters=1.,
                      physics_prim_path=scenes[0] if scenes else '/World/physicsScene',backend='numpy')
        session = uuid.uuid4().hex
        if harvest_physics is not None:
            harvest_physics.register(world, session)
        if sorter_scene is not None:
            sorter_scene.register(world)
        if args.physics_device is not None:
            # 학습 프로파일 적용 뒤, reset 전에만 비교용 실행 장치를 선택한다.
            context = world.get_physics_context()
            context.enable_gpu_dynamics(args.physics_device == 'gpu')
            context.set_broadphase_type('GPU' if args.physics_device == 'gpu' else 'MBP')
        context = world.get_physics_context()
        print('[physics_device] '+json.dumps(dict(requested=args.physics_device or 'profile',
            gpu_dynamics=context.is_gpu_dynamics_enabled(),
            broadphase=context.get_broadphase_type())), flush=True)
        clock_transport = LocalDatagrams(task['clock']['command_port'], task['clock']['telemetry_port'])
        diagnostic = DriveDiagnostics(root/'sim/runs/drive_diagnostics'/session, session)
        for cfg,robot_path,body_path,static,T_scan,camera_path,T_camera,tag_camera_path,T_tag_camera,T_asset_control in bindings:
            base = BaseSim(world,body_path,cfg['base'],name=cfg['robot_id']+'_drive')
            rt = cfg['runtime']
            diagnostic.describe(stage, cfg, robot_path)
            robots.append(dict(cfg=cfg,path=robot_path,base=base,static=static,T_scan=T_scan,
                camera_path=camera_path,T_camera=T_camera,T_asset_control=T_asset_control,camera=None,lidar=None,
                tag_camera_path=tag_camera_path,T_tag_camera=T_tag_camera,tag_camera=None,tag_camera_frames=0,
                transport=LocalDatagrams(rt['command_port'],rt['telemetry_port']),
                gate=CommandGate(session,cfg['base']['command_timeout_s']),history=deque(maxlen=math.ceil(5/frame_dt)+2),
                last_scan=-math.inf,last_telemetry=-math.inf,seq=0,camera_frames=0,arm=None,arm_device=None))
            arm_cfg = rt.get('harvest_arm', {})
            if arm_cfg.get('enabled', False):
                if harvest_physics is None:
                    raise ValueError('Teacher requires configured harvest physics')
                profile = json.loads((root/arm_cfg['profile']).read_text())
                robots[-1]['arm_profile'] = profile
                device_config = dict(profile['device'], **{key: profile['runtime'][key] for key in
                    ('box_min', 'box_max', 'box_contact_tolerance', 'box_bottom_contact_tolerance', 'sequence')})
                robots[-1]['arm_device'] = TeacherDevice(world, base.robot, robot_path,
                    harvest_physics, cfg['robot_id'], device_config)
        world.reset()
        for robot in robots:
            cfg, base = robot['cfg'], robot['base']
            base.initialize()
            if harvest_physics is not None and robot['path'] in harvest_physics.arm_reports:
                initialize_arm_travel(base.robot, harvest_physics.arm_reports[robot['path']])
            from farm_sim_runtime.station_spawn import verify_station_pose
            position, orientation = base.pose()
            q = Gf.Quatd(float(orientation[0]), Gf.Vec3d(*map(float, orientation[1:])))
            pose = Gf.Matrix4d(1.); pose.SetRotate(q); pose.SetTranslateOnly(Gf.Vec3d(*map(float, position)))
            logical = np.asarray(pose).T @ robot['T_asset_control']
            logical_q = Gf.Matrix4d(*map(float, logical.T.reshape(-1))).ExtractRotationQuat()
            verify_station_pose(dict(task['stations'][cfg['robot_id']], T_map_world=T_map_world),
                logical[:3,3], [float(logical_q.GetReal()), *map(float, logical_q.GetImaginary())])
            robot['initial_z'] = float(base.pose()[0][2])
            if cfg['camera']['enabled']:
                camera = CameraSim(robot['camera_path'],cfg['camera'],session,cfg['frames']['camera_optical'],robot['T_camera'])
                camera.initialize();robot['camera']=camera
            if cfg.get('tag_camera',{}).get('enabled'):
                camera = CameraSim(robot['tag_camera_path'],cfg['tag_camera'],session,
                    cfg['frames']['tag_camera_optical'],robot['T_tag_camera'])
                camera.initialize();robot['tag_camera']=camera
            if cfg['lidar']['enabled']:
                robot['lidar']=LidarSim(cfg['lidar'],robot['path'],robot['T_scan'])
            print(f"[two_robot_sim] {cfg['robot_id']} at station {task['stations'][cfg['robot_id']]} using {robot['path']}",flush=True)
        if harvest_physics is not None:
            harvest_physics.initialize()
        if sorter_scene is not None:
            from farm_sim_runtime.sorter_runtime import SorterRuntime
            sorter_scene.initialize()
            sorter_runtime = SorterRuntime(sorter_scene, robots, session)
        for robot in robots:
            device = robot['arm_device']
            if device is not None:
                device.initialize()
                profile = robot['arm_profile']
                arm_cfg = robot['cfg']['runtime']['harvest_arm']
                backend = arm_cfg.get('backend', 'teacher')
                if backend in ('student_d435', 'student_u20'):
                    from farm_sim_devices.student_session import StudentRuntime, StudentArmSession
                    settings = json.loads((root/arm_cfg['student_profile']).read_text())
                    if backend != 'student_'+settings['camera']:
                        raise ValueError('Student backend와 카메라 프로파일 불일치')
                    controller = StudentRuntime(root, settings, world, device, profile['runtime'])
                    robot['arm'] = StudentArmSession(session, robot['cfg']['robot_id'], task['map_id'],
                        device, controller, harvest_physics, profile['session'], root/'sim/runs/robotarm/student')
                elif backend == 'teacher':
                    from farm_sim_devices.teacher_policy import TeacherController
                    profile['joint_limits'] = dict(lower=device.lower.tolist(), upper=device.upper.tolist(),
                                                   home=device.home.tolist())
                    controller = TeacherController(profile, project_root=root, device='cpu')
                    if args.teacher_diagnostic_trace:
                        controller.enable_diagnostic_trace()
                    robot['arm'] = ArmSession(session, robot['cfg']['robot_id'], task['map_id'],
                        device, controller, harvest_physics, profile['session'], root/'sim/runs/robotarm/teacher')
                    if args.teacher_diagnostic_trace:
                        from farm_sim_runtime.teacher_diagnostics import TeacherRuntimeRecorder
                        robot['teacher_recorder'] = TeacherRuntimeRecorder(robot,
                            root/'sim/runs/robotarm/diagnostics'/session/robot['cfg']['robot_id'])
                else:
                    raise ValueError('지원하지 않는 수확 정책 backend: '+backend)
                print('[harvest_arm] '+json.dumps(dict(robot_id=robot['cfg']['robot_id'], backend=backend)), flush=True)
        # 장면 구성과 PhysX 초기화가 끝난 다음 viewport 물리 메뉴를 등록한다.
        if not args.headless:
            from farm_sim_runtime.harvest_physics_inspector import enable_physics_debug_ui
            enable_physics_debug_ui()
        if args.harvest_test_ui:
            from farm_sim_runtime.harvest_test_ui import HarvestTestController, HarvestTestPanel
            test_controller = HarvestTestController(robots[0], harvest_physics, task, root,
                                                    seed=args.harvest_test_seed)
            test_panel = HarvestTestPanel(test_controller)
            performance_log = (test_controller.directory/'frame_performance.jsonl').open('w')
        elif args.performance_log:
            args.performance_log.parent.mkdir(parents=True, exist_ok=True)
            performance_log = args.performance_log.open('w')
        auto_phase = 'place'
        auto_physics_stop_at = math.inf
        def after_physics(dt_s: float, sim_s: float) -> None:
            for robot in robots:
                if robot['arm'] is not None:
                    robot['arm'].observe_physics_tick(dt_s, sim_s)
                if (robot['arm'] is not None and (ticks.frame_count+1) % ticks.render_every == 0 and
                        robot['cfg']['runtime'].get('harvest_arm', {}).get('backend') in ('student_d435', 'student_u20')):
                    robot['arm'].prepare_capture(sim_s)
        hcfg = task['harvest_robot']
        truth = (SceneTruth(stage,root/hcfg['scene_snapshot_file'],hcfg['robot_id'],task['map_id'],session,hcfg['workspace'])
                 if hcfg is not None else None)
        from farm_sim_runtime.basket_monitor import BasketMonitor
        basket_monitor = BasketMonitor(stage, robots, task['basket_alignment']) if task.get('basket_alignment') else None
        if sorter_runtime is not None:sorter_runtime.basket_monitor = basket_monitor
        previous = float(world.current_time)
        start_sim = previous
        last_truth = -math.inf
        frame_deadline = time.monotonic()
        while app.is_running():
            wall = time.monotonic()
            frame_start = time.perf_counter()
            frame_arm = (test_controller.arm if test_controller else
                next((r['arm'] for r in robots if r['arm'] is not None and r['arm'].busy), None))
            frame_status = frame_arm.state['status'] if frame_arm else ''
            frame_stage = frame_arm.state['stage'] if frame_arm else ''
            if float(world.current_time) < previous-1e-10:
                raise RuntimeError('Simulation reset detected; restart the simulator test process')
            if test_controller is not None:
                if (args.harvest_test_auto_run or args.harvest_test_auto_physics) and float(world.current_time)-start_sim > 1.:
                    if auto_phase == 'place' and test_controller.can_place:
                        test_controller.request('place')
                        auto_phase = 'harvest'
                    elif auto_phase == 'harvest' and test_controller.ready:
                        test_controller.request('physics' if args.harvest_test_auto_physics else 'harvest')
                        auto_phase = 'observe' if args.harvest_test_auto_physics else 'done'
                        auto_physics_stop_at = float(world.current_time)+8.
                    elif auto_phase == 'observe' and float(world.current_time) >= auto_physics_stop_at:
                        test_controller.request('physics')
                        auto_phase = 'done'
                test_controller.before_frame(float(world.current_time), playing=world.is_playing())
            for robot in robots:
                for message in robot['transport'].receive():
                    if test_controller is not None:
                        # 이 패널 시험은 외부 ROS/UDP 명령으로 로봇을 움직이지 않는다.
                        continue
                    if message.get('kind') == 'harvest_arm':
                        if robot['arm'] is not None:
                            robot['arm'].accept(message)
                        continue
                    if message.get('kind') == 'harvest_activity':
                        if harvest_physics is not None:
                            harvest_physics.accept_activity(robot['cfg']['robot_id'], message)
                        continue
                    if message.get('kind') == 'camera_activity':
                        if robot['camera'] is not None:
                            robot['camera'].accept_activity(message)
                        continue
                    accepted = robot['gate'].accept(message)
                    diagnostic.received(robot['cfg']['robot_id'], message, accepted)
                if robot['camera'] is not None:
                    robot['camera'].update_activity()
            if not world.is_playing():
                if sorter_runtime is not None:
                    sorter_runtime.before_frame(float(world.current_time), frame_dt, playing=False)
                for robot in robots:
                    robot['gate'].stop()
                if test_panel is not None:
                    test_panel.before_render(float(world.current_time), ticks.physics_hz)
                    test_panel.update(float(world.current_time), ticks.physics_hz, playing=False)
                app.update();time.sleep(.01)
                frame_deadline = time.monotonic()
                continue
            control_finished = time.perf_counter()
            if sorter_runtime is not None:
                sorter_runtime.before_frame(float(world.current_time), frame_dt)
            for robot in robots:
                if robot['arm'] is not None:
                    # 팔 작업/복귀에는 학습 물리를 유지한다. 양팔 접힘과 작업
                    # 종료를 모두 확인한 뒤에만 주행용 정밀 제동 설정으로 돌아간다.
                    from farm_sim_runtime.teacher_arm_alignment import update_arm_solver_mode
                    arm_active = robot['arm'].busy or not robot['arm'].travel_ready
                    changed = update_arm_solver_mode(robot['base'].robot,
                        harvest_physics.profile.get('teacher_alignment', {}), arm_active=arm_active)
                    if changed is not None:
                        print('[arm_solver] '+json.dumps(dict(robot_id=robot['cfg']['robot_id'],
                            sim_time_s=float(world.current_time), arm_active=arm_active,
                            position_iterations=changed)), flush=True)
                    # 실제 차체 속도를 확인합니다. wheel odom 정지 추정으로 대신하지 않습니다.
                    linear = np.asarray(robot['base'].robot.get_linear_velocity(), dtype=float)
                    angular = np.asarray(robot['base'].robot.get_angular_velocity(), dtype=float)
                    arm_cfg = robot['arm_profile']['session']
                    stationary = (np.isfinite(linear).all() and np.isfinite(angular).all()
                        and np.linalg.norm(linear[:2]) < arm_cfg['base_linear_limit_m_s']
                        and abs(angular[2]) < arm_cfg['base_angular_limit_rad_s'])
                    robot['arm'].tick(float(world.current_time), base_stationary=stationary)
                    if robot.get('teacher_recorder') is not None:
                        robot['teacher_recorder'].sample(float(world.current_time))
                robot['applied_cmd'] = ((0., 0.) if robot['arm'] is not None
                                        and (robot['arm'].busy or not robot['arm'].travel_ready)
                                        else robot['gate'].value())
                robot['base'].command(*robot['applied_cmd'])
            arm_finished = time.perf_counter()
            if test_panel is not None:
                test_panel.apply_hz(float(world.current_time))
            required_hz = (harvest_physics.prepare_frame(float(world.current_time))
                           if harvest_physics is not None else configs[0]['runtime']['physics_hz'])
            if test_panel is not None:
                ticks.allow_rate(required_hz)
                test_panel.before_render(float(world.current_time), required_hz)
            prepare_finished = time.perf_counter()
            # 명령/센서/clock과 물리는60Hz, 렌더 요청은30Hz로 진행한다.
            ticks.step_frame(world, harvest_physics, physics_hz=required_hz, post_step=after_physics)
            step_finished = time.perf_counter()
            now = float(world.current_time)
            if sorter_runtime is not None:
                sorter_runtime.after_frame(now)
            student_camera_started = time.perf_counter()
            for robot in robots:
                if (robot['arm'] is not None
                        and robot['cfg']['runtime'].get('harvest_arm', {}).get('backend') in ('student_d435', 'student_u20')):
                    robot['arm'].after_frame(now)
            student_camera_s = time.perf_counter()-student_camera_started
            if test_controller is not None:
                test_controller.after_frame(now, ticks.physics_hz)
                test_panel.update(now, ticks.physics_hz)
            if now <= previous:
                raise RuntimeError('Simulation reset detected; restart both ROS and simulator test processes')
            clock_transport.send(dict(kind='clock', session=session, stamp_ns=round(now*1e9), sent=time.monotonic()))
            sensor_s = 0.
            for robot in robots:
                cfg = robot['cfg'];rt=cfg['runtime'];base=robot['base']
                odom,positions,velocities=base.sample(now-previous)
                robot['history'].append((now,odom))
                position,orientation=base.pose()
                if float(position[2]) < robot['initial_z']-rt['drop_limit_m']:
                    raise RuntimeError(cfg['robot_id']+' fell below its initial floor height')
                q=Gf.Quatd(float(orientation[0]),Gf.Vec3d(*map(float,orientation[1:])))
                M=Gf.Matrix4d(1.);M.SetRotate(q);M.SetTranslateOnly(Gf.Vec3d(*map(float,position)))
                T=np.asarray(M,float).T@robot['T_asset_control']
                robot['T_world_base']=T
                diagnostic.sample(robot, now, odom, positions, velocities)
                ranges=None
                sensor_started = time.perf_counter()
                if robot['lidar'] and now-robot['last_scan']>=1./cfg['lidar']['fps']-1e-8:
                    ranges=robot['lidar'].sample(T);robot['last_scan']=now
                if robot['camera']:
                    robot['camera_frames']+=int(robot['camera'].publish(robot['history'],frame_dt*.51))
                if robot['tag_camera']:
                    robot['tag_camera_frames']+=int(robot['tag_camera'].publish(robot['history'],frame_dt*.51))
                sensor_s += time.perf_counter() - sensor_started
                test_terminal = (args.stop_after_arm_job and robot['arm'] is not None
                    and robot['arm'].state['status'] in ('SUCCESS','FAILED','CANCELED'))
                if now-robot['last_telemetry']>=1./rt['telemetry_hz']-1e-8 or ranges is not None or test_terminal:
                    robot['seq']+=1
                    robot['transport'].send(dict(kind='state',session=session,seq=robot['seq'],sent=time.monotonic(),
                        stamp_ns=round(now*1e9),odom=odom,joint_positions=positions,joint_velocities=velocities,
                        static_tf=robot['static'],scan=ranges,camera_frames=robot['camera_frames'],
                        camera_active=robot['camera'].active if robot['camera'] else False,
                        tag_camera_frames=robot['tag_camera_frames'],
                        basket_alignment=(basket_monitor.latest if basket_monitor and
                            cfg['robot_id'] in basket_monitor.ids.values() else None),
                        arm=robot['arm'].telemetry() if robot['arm'] is not None else None))
                    robot['last_telemetry']=now
            if basket_monitor is not None:basket_monitor.update(now)
            truth_started = time.perf_counter()
            if truth is not None and now-last_truth>=.2:
                harvest=next(r for r in robots if r['cfg']['robot_id']==hcfg['robot_id'])
                truth.capture(round(now*1e9),harvest['T_world_base']);last_truth=now
            frame_finished = time.perf_counter()
            if performance_log is not None:
                performance_log.write(json.dumps(dict(
                    sim_s=now, wall_s=wall, physics_hz=ticks.physics_hz, status=frame_status, stage=frame_stage,
                    frame_s=frame_finished-frame_start, control_s=control_finished-frame_start,
                    arm_s=arm_finished-control_finished, prepare_s=prepare_finished-arm_finished,
                    post_s=truth_started-step_finished, truth_s=frame_finished-truth_started,
                    sensor_s=sensor_s, student_camera_s=student_camera_s,
                    camera_timings={r['cfg']['robot_id']: r['arm'].controller.rig.frame_timings
                        for r in robots if r['cfg']['runtime'].get('harvest_arm', {}).get('backend') in ('student_d435', 'student_u20')},
                    **ticks.frame_timings))+'\n')
                if ticks.frame_count % 60 == 0:
                    performance_log.flush()
            previous=now
            if args.stop_after_arm_job and any(r['arm'] is not None and
                    r['arm'].state['job_id'] and r['arm'].state['status'] in ('SUCCESS','FAILED','CANCELED')
                    for r in robots):
                print('[farm_fleet] arm job bounded run complete: '+json.dumps(dict(
                    simulated_s=now-start_sim, render_frames=ticks.frame_count, physics_ticks=ticks.total_ticks,
                    arms={r['cfg']['robot_id']: r['arm'].telemetry() for r in robots if r['arm'] is not None})),
                    flush=True)
                break
            if args.duration_s is not None and now-start_sim >= args.duration_s:
                print('[farm_fleet] bounded run complete: '+json.dumps(dict(simulated_s=now-start_sim,
                    render_frames=ticks.frame_count, physics_ticks=ticks.total_ticks,
                    robots=[dict(robot_id=r['cfg']['robot_id'],camera_frames=r['camera_frames'],
                                 tag_camera_frames=r['tag_camera_frames'],
                                 position_world_m=r['T_world_base'][:3,3].tolist(),
                                 telemetry_packets=r['seq']) for r in robots])),flush=True)
                break
            # 렌더가 오래 걸린 다음 tick에 이미 늦은 시간을 추가 sleep으로 누적하지 않는다.
            frame_deadline = max(frame_deadline+frame_dt, wall-frame_dt)
            if configs[0]['runtime'].get('realtime',True):
                delay = frame_deadline-time.monotonic()
                if delay > 0:
                    time.sleep(delay)
    except KeyboardInterrupt:
        pass
    except Exception:
        # SDK 종료 중 native 오류가 나더라도 최초 Python 원인을 로그에 보존한다.
        import traceback
        traceback.print_exc()
        raise
    finally:
        if sorter_runtime is not None:
            sorter_runtime.close()
        if 'truth' in locals() and truth is not None:
            truth.close()
        if performance_log is not None:
            performance_log.close()
        if test_panel is not None:
            try:
                test_panel.close()
            except Exception as error:
                print('[harvest_test] panel cleanup: '+str(error), flush=True)
        if test_controller is not None:
            try:
                test_controller.close()
            except Exception as error:
                print('[harvest_test] controller cleanup: '+str(error), flush=True)
        for robot in robots:
            if robot.get('teacher_recorder') is not None:
                robot['teacher_recorder'].close()
            if robot.get('arm') is not None:
                robot['arm'].close()
            try:robot['base'].command(0.,0.)
            except Exception:pass
            if robot['camera']:
                robot['camera'].close()
            if robot['tag_camera']:
                robot['tag_camera'].close()
            robot['transport'].close()
        if world:
            world.stop()
        if clock_transport is not None: clock_transport.close()
        if harvest_physics is not None: harvest_physics.close()
        app.close()


if __name__ == '__main__':
    import os
    import traceback
    exit_code = 0
    try:
        main()
    except SystemExit as error:
        exit_code = error.code if isinstance(error.code, int) else 1
    except Exception:
        traceback.print_exc()
        exit_code = 1
    finally:
        # main의 장치/로그/app.close 정리 뒤 남는 Kit 스레드만 CLI 종료에서 끝낸다.
        sys.stdout.flush()
        sys.stderr.flush()
        os._exit(exit_code)
