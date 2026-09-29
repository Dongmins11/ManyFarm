"""Isaac Sim 5.1 진입점. ROS/rclpy는 이 Python 프로세스로 import하지 않습니다."""
import argparse
from collections import deque
import json
import math
from pathlib import Path
import sys
import time
import uuid


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--config',type=Path,required=True)
    parser.add_argument('--assets-root',type=Path,required=True)
    parser.add_argument('--headless',action='store_true')
    parser.add_argument('--module-path',action='append',default=[])
    args=parser.parse_args()
    for path in args.module_path:
        sys.path.insert(0,str(Path(path).resolve()))
    config=json.loads(args.config.read_text())
    root=args.assets_root.expanduser().resolve()
    scene=(root/config['scene']).resolve()
    if not scene.is_relative_to(root) or not scene.is_file():
        raise FileNotFoundError(f'농장 씬을 찾을 수 없습니다: {scene}')
    import numpy as np
    from farm_sim_devices.wire import LocalDatagrams,CommandGate
    from isaacsim import SimulationApp
    sys.argv=[sys.argv[0]]
    app=SimulationApp({'headless':args.headless,'renderer':'RayTracedLighting'})
    world=base=camera=transport=None
    try:
        import omni.usd
        from pxr import UsdGeom,UsdPhysics,Gf
        from isaacsim.core.api import World
        from isaacsim.core.utils.stage import open_stage
        from farm_sim_devices.base_sim import BaseSim
        from farm_sim_devices.camera_sim import CameraSim
        from farm_sim_devices.lidar_sim import LidarSim
        if not open_stage(str(scene)):
            raise RuntimeError(f'씬을 열지 못했습니다: {scene}')
        stage=omni.usd.get_context().get_stage()
        # 실행 중 설정은 session layer만 사용. 원본 USD 저장하지 않음.
        stage.SetEditTarget(stage.GetSessionLayer())
        if abs(UsdGeom.GetStageMetersPerUnit(stage)-1.0)>1e-9 or UsdGeom.GetStageUpAxis(stage)!='Z':
            raise RuntimeError('현재 연결부는 metersPerUnit=1, Z-up 씬을 요구합니다.')
        from farm_sim_runtime.bed_collisions import ensure_bed_collisions
        bed_collision_report=ensure_bed_collisions(stage)
        print('[farm_sim] bed collision: '+json.dumps(bed_collision_report,ensure_ascii=False),flush=True)
        binding=config['scene_binding'];robot_path=binding['robot_prim'].rstrip('/')
        def prim(relative):
            p=stage.GetPrimAtPath(robot_path+'/'+relative)
            if not p.IsValid():raise RuntimeError(f'로봇 구성 요소가 없습니다: {p.GetPath()} ({relative})')
            return p
        body=prim(binding['articulation_relative'])
        if not body.HasAPI(UsdPhysics.ArticulationRootAPI):
            raise RuntimeError(f'ArticulationRoot가 아닙니다: {body.GetPath()}')
        link=prim(binding['base_link_relative']);scan_prim=prim(binding['lidar_relative'])
        camera_prim=prim(binding['camera_relative'])
        if not camera_prim.IsA(UsdGeom.Camera):raise RuntimeError('지정한 camera prim이 Camera가 아닙니다.')
        cache=UsdGeom.XformCache()
        def matrix(p):return np.asarray(cache.GetLocalToWorldTransform(p),dtype=float).T
        T_world_body=matrix(body)
        inverse=np.linalg.inv(T_world_body)
        T_base_link=inverse@matrix(link)
        T_base_scan=inverse@matrix(scan_prim)
        T_base_optical=inverse@matrix(camera_prim)@np.diag([1.,-1.,-1.,1.])
        for name,T in [('base_link',T_base_link),('scan',T_base_scan),('camera',T_base_optical)]:
            if not np.allclose(T[:3,:3].T@T[:3,:3],np.eye(3),atol=1e-5):
                raise RuntimeError(f'{name}에 비단위 scale이 있습니다.')
        frames=config['frames']
        def static_tf(parent,child,T):
            q=Gf.Matrix4d(*map(float,T.T.reshape(-1))).ExtractRotationQuat()
            return {'parent':parent,'child':child,'translation':T[:3,3].tolist(),
                    'rotation_xyzw':[*map(float,q.GetImaginary()),float(q.GetReal())]}
        static=[static_tf(frames['base_footprint'],frames['base_link'],T_base_link),
                static_tf(frames['base_link'],frames['scan'],np.linalg.inv(T_base_link)@T_base_scan),
                static_tf(frames['base_link'],frames['camera_optical'],np.linalg.inv(T_base_link)@T_base_optical)]
        scenes=[str(p.GetPath()) for p in stage.Traverse() if p.IsA(UsdPhysics.Scene)]
        if len(scenes)>1:raise RuntimeError('PhysicsScene이 여러 개입니다. 사용할 씬을 먼저 정리하세요.')
        dt=1.0/config['runtime']['physics_hz']
        if config['runtime']['render_hz']!=config['runtime']['physics_hz']:
            raise ValueError('이 초기 구현은 physics_hz와 render_hz가 같아야 합니다.')
        world=World(physics_dt=dt,rendering_dt=dt,stage_units_in_meters=1.0,
                    physics_prim_path=scenes[0] if scenes else '/World/physicsScene',backend='numpy')
        base=BaseSim(world,str(body.GetPath()),config['base'])
        world.reset()
        base.initialize()
        session=uuid.uuid4().hex
        gate=CommandGate(session,config['base']['command_timeout_s'])
        rt=config['runtime']
        transport=LocalDatagrams(rt['command_port'],rt['telemetry_port'])
        if config['camera']['enabled']:
            camera=CameraSim(str(camera_prim.GetPath()),config['camera'],session,
                             frames['camera_optical'],T_base_optical)
            camera.initialize()
        lidar=LidarSim(config['lidar'],robot_path,T_base_scan) if config['lidar']['enabled'] else None
        history=deque(maxlen=round(5/dt))
        initial_z=float(base.pose()[0][2]);last_sim=float(world.current_time)
        last_telemetry=last_scan=-math.inf;packet_sequence=0
        camera_frames=0;next_log=time.monotonic()+5.0
        print(f'[farm_sim] 준비 완료: {robot_path}',flush=True)
        print(f'[farm_sim] camera left, wheel r={config["base"]["wheel_radius_m"]}m; ROS 명령 대기',flush=True)
        while app.is_running():
            wall_start=time.monotonic()
            for message in transport.receive():gate.accept(message)
            if not world.is_playing():
                gate.stop()
                app.update()
                time.sleep(.01)
                continue
            base.command(*gate.value())
            world.step(render=True)
            now=float(world.current_time)
            if now<=last_sim:
                raise RuntimeError('시뮬레이션 시간 reset 감지. 연결 프로그램을 재시작하세요.')
            odom,positions,velocities=base.sample(now-last_sim)
            last_sim=now
            history.append((now,odom))
            position,orientation=base.pose()
            if float(position[2])<initial_z-rt['drop_limit_m']:
                raise RuntimeError('로봇이 아래로 떨어졌습니다. 바닥 collision을 확인하세요. 원본은 변경하지 않았습니다.')
            q=Gf.Quatd(float(orientation[0]),Gf.Vec3d(*map(float,orientation[1:])))
            transform=Gf.Matrix4d(1.0);transform.SetRotate(q);transform.SetTranslateOnly(Gf.Vec3d(*map(float,position)))
            T_world_base=np.asarray(transform).T
            ranges=None
            if lidar and now-last_scan>=1.0/config['lidar']['fps']-1e-8:
                ranges=lidar.sample(T_world_base);last_scan=now
            if camera:camera_frames+=int(camera.publish(history,dt*.51))
            if now-last_telemetry>=1.0/rt['telemetry_hz']-1e-8 or ranges is not None:
                packet_sequence+=1
                packet=dict(kind='state',session=session,seq=packet_sequence,sent=time.monotonic(),
                            stamp_ns=round(now*1e9),odom=odom,joint_positions=positions,
                            joint_velocities=velocities,static_tf=static,scan=ranges,
                            camera_frames=camera_frames)
                transport.send(packet);last_telemetry=now
            if time.monotonic()>=next_log:
                print(f'[farm_sim] sim={now:.2f}s odom=({odom[0]:.2f},{odom[1]:.2f}) RGB-D frames={camera_frames}',flush=True)
                next_log=time.monotonic()+5.0
            if rt['realtime']:
                time.sleep(max(0.0,dt-(time.monotonic()-wall_start)))
    except KeyboardInterrupt:
        pass
    finally:
        if base is not None:
            try:base.command(0.0,0.0)
            except Exception:pass
        if camera is not None:
            try:camera.close()
            except Exception:pass
        if transport is not None:transport.close()
        if world is not None:
            try:world.stop()
            except Exception:pass
        app.close()


if __name__=='__main__':
    main()
