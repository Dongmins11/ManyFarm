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
    parser.add_argument('--duration-s', type=float, help='검증용 실행 시간(시뮬레이션 초). 생략하면 계속 실행')
    args = parser.parse_args()
    if args.duration_s is not None and (not math.isfinite(args.duration_s) or args.duration_s <= 0):
        parser.error('--duration-s는 유한한 양수여야 합니다.')
    root = args.project_root.expanduser().resolve()
    for module_path in args.module_path:
        sys.path.insert(0, str(Path(module_path).resolve()))
    from farm_sim_runtime.fleet_config import load_fleet
    configs, task = load_fleet(root, args.fleet_config)
    from farm_sim_runtime.harvest_physics import (
        HarvestPhysics, PhysicsTicks, initialize_arm_home, load_physics_profile)
    physics_profile = load_physics_profile(root, configs)
    assets = args.assets_root.resolve() if args.assets_root else root/'sim/assets'
    scene = args.scene.expanduser().resolve() if args.scene else assets/configs[0]['scene']
    if not scene.is_file():
        raise FileNotFoundError(scene)
    from isaacsim import SimulationApp
    sys.argv = [sys.argv[0]]
    app = SimulationApp({'headless':args.headless, 'renderer':'RayTracedLighting', 'fast_shutdown':False})
    world, robots, clock_transport, harvest_physics = None, [], None, None
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
        if physics_profile is not None:
            harvest_physics = HarvestPhysics(stage, root, physics_profile)
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
            if harvest_physics is not None and cfg['robot_id'] == task['harvest_robot']['robot_id']:
                harvest_physics.configure_robot(robot_path)
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
            bindings.append((cfg,robot_path,str(body.GetPath()),static,T_scan,camera_path,T_camera,T_asset_control))
        scenes = [str(p.GetPath()) for p in stage.Traverse() if p.IsA(UsdPhysics.Scene)]
        if len(scenes) > 1:
            raise RuntimeError('Multiple PhysicsScene prims; select one scene before running')
        dt = 1./configs[0]['runtime']['physics_hz']
        ticks = PhysicsTicks(configs[0]['runtime']['physics_hz'], configs[0]['runtime']['render_hz'])
        world = World(physics_dt=dt,rendering_dt=1./configs[0]['runtime']['render_hz'],stage_units_in_meters=1.,
                      physics_prim_path=scenes[0] if scenes else '/World/physicsScene',backend='numpy')
        session = uuid.uuid4().hex
        if harvest_physics is not None:
            harvest_physics.register(world, session)
        clock_transport = LocalDatagrams(task['clock']['command_port'], task['clock']['telemetry_port'])
        diagnostic = DriveDiagnostics(root/'sim/runs/drive_diagnostics'/session, session)
        for cfg,robot_path,body_path,static,T_scan,camera_path,T_camera,T_asset_control in bindings:
            base = BaseSim(world,body_path,cfg['base'],name=cfg['robot_id']+'_drive')
            rt = cfg['runtime']
            diagnostic.describe(stage, cfg, robot_path)
            robots.append(dict(cfg=cfg,path=robot_path,base=base,static=static,T_scan=T_scan,
                camera_path=camera_path,T_camera=T_camera,T_asset_control=T_asset_control,camera=None,lidar=None,
                transport=LocalDatagrams(rt['command_port'],rt['telemetry_port']),
                gate=CommandGate(session,cfg['base']['command_timeout_s']),history=deque(maxlen=round(5/dt)),
                last_scan=-math.inf,last_telemetry=-math.inf,seq=0,camera_frames=0))
        world.reset()
        for robot in robots:
            cfg, base = robot['cfg'], robot['base']
            base.initialize()
            if harvest_physics is not None and robot['path'] in harvest_physics.arm_reports:
                initialize_arm_home(base.robot, harvest_physics.arm_reports[robot['path']])
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
            if cfg['lidar']['enabled']:
                robot['lidar']=LidarSim(cfg['lidar'],robot['path'],robot['T_scan'])
            print(f"[two_robot_sim] {cfg['robot_id']} at station {task['stations'][cfg['robot_id']]} using {robot['path']}",flush=True)
        if harvest_physics is not None:
            harvest_physics.initialize()
        hcfg = task['harvest_robot']
        truth = SceneTruth(stage,root/hcfg['scene_snapshot_file'],hcfg['robot_id'],task['map_id'],session,hcfg['workspace'])
        previous = float(world.current_time)
        start_sim = previous
        last_truth = -math.inf
        while app.is_running():
            wall = time.monotonic()
            for robot in robots:
                for message in robot['transport'].receive():
                    accepted = robot['gate'].accept(message)
                    diagnostic.received(robot['cfg']['robot_id'], message, accepted)
            if not world.is_playing():
                for robot in robots:
                    robot['gate'].stop()
                app.update();time.sleep(.01);continue
            for robot in robots:
                robot['applied_cmd'] = robot['gate'].value()
                robot['base'].command(*robot['applied_cmd'])
            ticks.step(world, harvest_physics)
            now = float(world.current_time)
            if now <= previous:
                raise RuntimeError('Simulation reset detected; restart both ROS and simulator test processes')
            clock_transport.send(dict(kind='clock', session=session, stamp_ns=round(now*1e9), sent=time.monotonic()))
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
                if robot['lidar'] and now-robot['last_scan']>=1./cfg['lidar']['fps']-1e-8:
                    ranges=robot['lidar'].sample(T);robot['last_scan']=now
                if robot['camera']:
                    robot['camera_frames']+=int(robot['camera'].publish(robot['history'],dt*.51))
                if now-robot['last_telemetry']>=1./rt['telemetry_hz']-1e-8 or ranges is not None:
                    robot['seq']+=1
                    robot['transport'].send(dict(kind='state',session=session,seq=robot['seq'],sent=time.monotonic(),
                        stamp_ns=round(now*1e9),odom=odom,joint_positions=positions,joint_velocities=velocities,
                        static_tf=robot['static'],scan=ranges,camera_frames=robot['camera_frames']))
                    robot['last_telemetry']=now
            if now-last_truth>=.2:
                harvest=next(r for r in robots if r['cfg']['robot_id']==hcfg['robot_id'])
                truth.capture(round(now*1e9),harvest['T_world_base']);last_truth=now
            previous=now
            if args.duration_s is not None and now-start_sim >= args.duration_s:
                print('[farm_fleet] bounded run complete: '+json.dumps(dict(simulated_s=now-start_sim,
                    robots=[dict(robot_id=r['cfg']['robot_id'],camera_frames=r['camera_frames'],
                                 telemetry_packets=r['seq']) for r in robots])),flush=True)
                break
            if configs[0]['runtime'].get('realtime',True):
                time.sleep(max(0.,dt-(time.monotonic()-wall)))
    except KeyboardInterrupt:
        pass
    finally:
        for robot in robots:
            try:robot['base'].command(0.,0.)
            except Exception:pass
            if robot['camera']:
                robot['camera'].close()
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
