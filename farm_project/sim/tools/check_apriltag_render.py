"""Isaac Python: 실제 농장에서 정차 카메라 렌더를 저장합니다. 주행 시험은 아닙니다."""
import json
import math
from pathlib import Path
import sys
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT/'sim/runs/apriltag_20261008'
sys.path[:0] = [str(ROOT/'sim/ros_ws/src/farm_sim_runtime'),
                str(ROOT/'sim/ros_ws/src/farm_sim_devices'),
                str(ROOT/'robot/ros_ws/src/farm_common')]


def main() -> None:
    from isaacsim import SimulationApp
    app = SimulationApp({'headless':True, 'renderer':'RayTracedLighting', 'fast_shutdown':False})
    try:
        import omni.usd
        import omni.timeline
        from pxr import UsdGeom, Gf, Usd
        from isaacsim.core.utils.stage import open_stage
        from farm_sim_runtime.apriltag_scene import install_tags, mount_camera
        from farm_sim_devices.camera_sim import CameraSim
        from farm_sim_devices.control_frame import asset_from_control, station_root_transform
        from PIL import Image
        config = json.loads((ROOT/'sim/ros_ws/src/farm_sim_config/config/harvest.json').read_text())
        config['camera']['shm_name'] = 'farm_apriltag_render_check'
        open_stage(str(ROOT/'sim/assets'/config['scene']))
        stage = omni.usd.get_context().get_stage()
        stage.SetEditTarget(stage.GetSessionLayer())
        count = install_tags(stage, ROOT, config)
        binding = config['scene_binding']
        robot_path = binding['robot_prim']
        robot = UsdGeom.Xform.Define(stage, robot_path).GetPrim()
        robot.GetReferences().AddReference(str(ROOT/'sim/assets'/binding['asset_file']))
        cache = UsdGeom.XformCache()
        def matrix(path: str) -> np.ndarray:
            return np.array(cache.GetLocalToWorldTransform(stage.GetPrimAtPath(path))).T
        # SEC01의 현행 수확 정차선과 ID104를 사용합니다. 모든 위치는 설정에서 읽습니다.
        tags = json.loads((ROOT/config['apriltag_map']).read_text())['tags']
        tag = next(t for t in tags if t['id']==104)
        survey = json.loads((ROOT/'sim/ros_ws/src/farm_sim_config/config/scout_survey.json').read_text())
        section = survey['sections'][tag['section_id']]
        yaw = section['harvest_route']['heading_rad']
        desired = np.eye(4)
        desired[:3,:3] = [[math.cos(yaw),-math.sin(yaw),0],[math.sin(yaw),math.cos(yaw),0],[0,0,1]]
        desired[0,3] = section['harvest_route']['x_m']
        offset = desired[:3,:3]@np.asarray(config['camera']['T_base_optical'])[:3,3]
        desired[1,3] = tag['tag_center_map_m'][1]-offset[1]
        local = station_root_transform(desired,matrix(robot_path+'/'+binding['articulation_relative']),
                                       matrix(robot_path),asset_from_control(binding))
        xform = UsdGeom.Xformable(robot); xform.ClearXformOpOrder()
        xform.AddTransformOp().Set(Gf.Matrix4d(*local.T.flatten().tolist()))
        mount_camera(stage,robot_path,config)
        # 속도 명령 없는 정차 광학 시험입니다.
        timeline = omni.timeline.get_timeline_interface()
        timeline.play()
        camera = CameraSim(robot_path+'/'+binding['camera_relative'], config['camera'],
                           'apriltag-render-check', config['frames']['camera_optical'],
                           np.array(config['camera']['T_base_optical']))
        camera.initialize()
        for _ in range(100):
            app.update()
        frame = camera.camera.get_current_frame()
        rgb = np.asarray(frame.get('rgb'))
        if rgb.shape[:2] != (720,1280):
            raise RuntimeError(f'렌더 영상 없음: {rgb.shape}')
        OUTPUT.mkdir(parents=True,exist_ok=True)
        Image.fromarray(rgb[:,:,:3].astype(np.uint8)).save(OUTPUT/'sec01_id104.png')
        from farm_common.rgbd_shm import RgbdReader
        stamp = float(frame['rendering_time'])
        assert camera.publish([(stamp, [0.,0.,0.,0.,0.])], .01)
        packet = RgbdReader(config['camera']['shm_name']).read()
        assert packet is not None
        np.testing.assert_array_equal(packet['rgb'], rgb[:,:,:3])
        assert np.isnan(packet['depth']).all()
        (OUTPUT/'render_check.json').write_text(json.dumps(dict(tags=count,
            rendering_time=frame.get('rendering_time'),shape=list(rgb.shape),
            shared_memory_metadata=packet['metadata'],
            lens_parameters=camera.camera.get_opencv_pinhole_properties(),
            note='정차 광학 시험. 주행/주행 보정 성공이 아님.'),ensure_ascii=False,indent=2)+'\n')
        camera.close(); timeline.stop()
    finally:
        app.close(wait_for_replicator=False)


if __name__ == '__main__':
    main()
