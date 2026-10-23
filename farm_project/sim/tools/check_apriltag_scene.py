"""USD Python에서 전체 벽면 부착 범위와 카메라 광학 변환을 직접 검증합니다."""
import json
from pathlib import Path
import sys
import numpy as np
from pxr import Usd, UsdGeom

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT/'sim/ros_ws/src/farm_sim_runtime'),
                str(ROOT/'sim/ros_ws/src/farm_sim_devices')]
from farm_sim_runtime.apriltag_scene import install_tags, mount_camera
from farm_sim_devices.control_frame import asset_from_control


def check() -> dict:
    config = json.loads((ROOT/'sim/ros_ws/src/farm_sim_config/config/harvest.json').read_text())
    stage = Usd.Stage.Open(str(ROOT/'sim/assets'/config['scene']))
    stage.SetEditTarget(stage.GetSessionLayer())
    count = install_tags(stage, ROOT, config)
    binding = config['scene_binding']
    robot = next((p for p in binding['robot_prim_candidates'] if stage.GetPrimAtPath(p)), None)
    if robot is None:
        robot = binding['robot_prim']
        UsdGeom.Xform.Define(stage,robot).GetPrim().GetReferences().AddReference(str(ROOT/'sim/assets'/binding['asset_file']))
    mount_camera(stage, robot, config)
    cache = UsdGeom.XformCache()
    def matrix(relative: str) -> np.ndarray:
        return np.array(cache.GetLocalToWorldTransform(stage.GetPrimAtPath(robot+'/'+relative))).T
    optical = np.linalg.inv(matrix(binding['articulation_relative'])@asset_from_control(binding))
    optical = optical@matrix(binding['camera_relative'])@np.diag([1.,-1.,-1.,1.])
    np.testing.assert_allclose(optical,config['camera']['T_base_optical'],atol=1e-8)
    bbox = UsdGeom.BBoxCache(Usd.TimeCode.Default(),['default','render'])
    data = json.loads((ROOT/config['apriltag_map']).read_text())
    for tag in data['tags']:
        bounds = bbox.ComputeWorldBound(stage.GetPrimAtPath(tag['wall_prim'])).ComputeAlignedRange()
        low,high = np.array(bounds.GetMin()),np.array(bounds.GetMax())
        prim = stage.GetPrimAtPath(f"/World/AprilTags/{tag['section_id']}/Tag_{tag['id']}")
        points = np.array(UsdGeom.Mesh(prim).GetPointsAttr().Get())
        normal = np.array(tag['normal_map'])
        outside = high[0] if normal[0]>0 else low[0]
        np.testing.assert_allclose((points[:,0]-outside)*normal[0],.001,atol=1e-6)
        assert np.all(points[:,1:] >= low[1:]-1e-6) and np.all(points[:,1:] <= high[1:]+1e-6)
        np.testing.assert_allclose(np.linalg.norm(points[1]-points[0]),.064,atol=1e-6)
        np.testing.assert_allclose(np.linalg.norm(points[2]-points[1]),.069,atol=1e-6)
        pattern = UsdGeom.Mesh(stage.GetPrimAtPath(str(prim.GetPath())+'/Pattern'))
        code_points = np.array(pattern.GetPointsAttr().Get())
        assert code_points.shape == (256, 3)
        center = np.array(tag['tag_center_map_m'])
        for axis in (np.array(tag['right_map']), np.array([0.,0.,1.])):
            projected = (code_points-center)@axis
            np.testing.assert_allclose([projected.min(),projected.max()],
                                      [-tag['black_edge_m']/2,tag['black_edge_m']/2],atol=1e-6)
        np.testing.assert_allclose((code_points-center)@normal,1e-5,atol=1e-6)
        assert np.dot(np.cross(code_points[3]-code_points[0],code_points[2]-code_points[0]),normal)>0
        colors = np.array(pattern.GetDisplayColorAttr().Get())
        cells = np.array(data['pattern_cells'][str(tag['id'])]).reshape(-1)
        np.testing.assert_array_equal(colors,np.repeat(cells[:,None],3,axis=1))
    return dict(tags=count, walls=len({t['wall_prim'] for t in data['tags']}),
                optical_transform=optical.tolist(), status='PASS', physics_or_render_test=False)


if __name__ == '__main__':
    print(json.dumps(check(),ensure_ascii=False,indent=2))
