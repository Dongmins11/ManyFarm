"""Isaac Python: 실제 농장에서 정차 카메라 렌더를 저장합니다. 주행 시험은 아닙니다."""
import json
import math
import argparse
from pathlib import Path
import sys
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT/'sim/runs/apriltag_20261008'
sys.path[:0] = [str(ROOT/'sim/ros_ws/src/farm_sim_runtime'),
                str(ROOT/'sim/ros_ws/src/farm_sim_devices'),
                str(ROOT/'robot/ros_ws/src/farm_common')]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=OUTPUT)
    parser.add_argument('--robot', choices=('scout','harvest'), default='harvest')
    args = parser.parse_args()
    output = args.output.resolve()
    from isaacsim import SimulationApp
    app = SimulationApp({'headless':True, 'renderer':'RayTracedLighting', 'fast_shutdown':False})
    try:
        import omni.usd
        import omni.timeline
        from pxr import UsdGeom, Gf, Usd
        from isaacsim.core.utils.stage import open_stage
        from farm_sim_runtime.apriltag_scene import install_tags, mount_camera
        from farm_sim_runtime.scout_mount import install_scout_mount
        from farm_sim_devices.camera_sim import CameraSim
        from farm_sim_devices.control_frame import asset_from_control, station_root_transform
        from PIL import Image
        config = json.loads((ROOT/f'sim/ros_ws/src/farm_sim_config/config/{args.robot}.json').read_text())
        camera_key = 'tag_camera' if args.robot == 'scout' else 'camera'
        frame_key = 'tag_camera_optical' if args.robot == 'scout' else 'camera_optical'
        camera_cfg = config[camera_key]
        camera_cfg['shm_name'] = f'farm_{args.robot}_apriltag_render_check'
        open_stage(str(ROOT/'sim/assets'/config['scene']))
        stage = omni.usd.get_context().get_stage()
        stage.SetEditTarget(stage.GetSessionLayer())
        count = install_tags(stage, ROOT, config)
        binding = config['scene_binding']
        robot_path = binding['robot_prim']
        robot = stage.GetPrimAtPath(robot_path)
        if not robot.IsValid():
            robot = UsdGeom.Xform.Define(stage, robot_path).GetPrim()
            robot.GetReferences().AddReference(str(ROOT/'sim/assets'/binding['asset_file']))
        cache = UsdGeom.XformCache()
        def matrix(path: str) -> np.ndarray:
            return np.array(cache.GetLocalToWorldTransform(stage.GetPrimAtPath(path))).T
        # SEC01의 로봇별 현행 작업선과 ID104를 사용합니다. 모든 위치는 설정에서 읽습니다.
        tag_map = json.loads((ROOT/config['apriltag_map']).read_text())
        tags = tag_map['tags']
        map_world = np.asarray(tag_map['T_map_world'],float)
        tag = next(t for t in tags if t['section_id']=='SEC01' and t['id']==104)
        survey = json.loads((ROOT/'sim/ros_ws/src/farm_sim_config/config/scout_survey.json').read_text())
        section = survey['sections'][tag['section_id']]
        if args.robot == 'scout':
            start,end = (section['survey_geometry'][key] for key in ('start_xy_m','end_xy_m'))
            yaw = math.atan2(end[1]-start[1],end[0]-start[0])
            route_x = start[0]
        else:
            yaw = section['harvest_route']['heading_rad']
            route_x = section['harvest_route']['x_m']
        desired = np.eye(4)
        desired[:3,:3] = [[math.cos(yaw),-math.sin(yaw),0],[math.sin(yaw),math.cos(yaw),0],[0,0,1]]
        desired[0,3] = route_x
        offset = desired[:3,:3]@np.asarray(camera_cfg['T_base_optical'])[:3,3]
        desired[1,3] = tag['tag_center_map_m'][1]-offset[1]
        local = station_root_transform(desired,matrix(robot_path+'/'+binding['articulation_relative']),
                                       matrix(robot_path),asset_from_control(binding))
        xform = UsdGeom.Xformable(robot); xform.ClearXformOpOrder()
        xform.AddTransformOp().Set(Gf.Matrix4d(*local.T.flatten().tolist()))
        mount_camera(stage,robot_path,config)
        install_scout_mount(stage,ROOT,robot_path,config)
        # 속도 명령 없는 정차 광학 시험입니다.
        timeline = omni.timeline.get_timeline_interface()
        timeline.play()
        camera = CameraSim(robot_path+'/'+binding[camera_key+'_relative'], camera_cfg,
                           'apriltag-render-check', config['frames'][frame_key],
                           np.array(camera_cfg['T_base_optical']))
        camera.initialize()
        # RGB와 같은 획득 콜백에 렌더 카메라 변환을 보존합니다. 초기 배치가 정답이라고 가정하지 않습니다.
        camera.camera.attach_annotator('CameraParams')
        for _ in range(100):
            app.update()
        frame = camera.camera.get_current_frame()
        rgb = np.asarray(frame.get('rgb'))
        if rgb.shape[:2] != (camera_cfg['height'],camera_cfg['width']):
            raise RuntimeError(f'렌더 영상 없음: {rgb.shape}')
        output.mkdir(parents=True,exist_ok=True)
        Image.fromarray(rgb[:,:,:3].astype(np.uint8)).save(output/'sec01_id104.png')
        from farm_common.rgbd_shm import RgbdReader
        stamp = float(frame['rendering_time'])
        view = np.asarray(frame['CameraParams']['cameraViewTransform'],float).reshape(4,4)
        # Replicator view는 USD 행벡터 world→camera. ROS optical은 Y/Z 부호를 뒤집습니다.
        world_camera = np.linalg.inv(view).T @ np.diag([1.,-1.,-1.,1.])
        map_camera = map_world @ world_camera
        map_base = map_camera @ np.linalg.inv(np.asarray(camera_cfg['T_base_optical'],float))
        expected_pose = [float(map_base[0,3]),float(map_base[1,3]),
                         math.atan2(map_base[1,0],map_base[0,0])]
        cache.Clear()
        sample_time = float(timeline.get_current_time())
        usd_world_base = matrix(robot_path+'/'+binding['articulation_relative']) @ asset_from_control(binding)
        sdk_position,sdk_orientation = camera.camera.get_world_pose(camera_axes='ros')
        assert camera.publish([(stamp, [0.,0.,0.,0.,0.])], .01)
        packet = RgbdReader(camera_cfg['shm_name']).read()
        assert packet is not None
        np.testing.assert_array_equal(packet['rgb'], rgb[:,:,:3])
        assert np.isnan(packet['depth']).all()
        (output/'render_check.json').write_text(json.dumps(dict(tags=count,robot=args.robot,
            requested_pose=[desired[0,3],desired[1,3],yaw],
            expected_pose_map=dict(zip(('x','y','yaw'),expected_pose)),
            expected_pose=expected_pose,t_base_camera=camera_cfg['T_base_optical'],
            render_pose=dict(source='CameraParams acquired with RGB',stamp_s=stamp,
                world_camera_optical=world_camera.tolist(),map_base=map_base.tolist()),
            current_pose=dict(sample_time_s=sample_time,world_base=usd_world_base.tolist(),
                camera_position_world=np.asarray(sdk_position).tolist(),
                camera_orientation_wxyz_ros=np.asarray(sdk_orientation).tolist()),
            rendering_time=frame.get('rendering_time'),shape=list(rgb.shape),
            shared_memory_metadata=packet['metadata'],
            lens_parameters=camera.camera.get_opencv_pinhole_properties(),
            note='정차 광학 시험. 주행/주행 보정 성공이 아님.'),ensure_ascii=False,indent=2)+'\n')
        camera.close(); timeline.stop()
    finally:
        app.close(wait_for_replicator=False)


if __name__ == '__main__':
    main()
