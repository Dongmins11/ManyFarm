"""URDF/USD 광축 일치와 모든 운영 USD 참조 경로를 확인한다(pxr 환경)."""
from pathlib import Path
import sys
import json
import unittest
import xml.etree.ElementTree as ET
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tools'))
from build_basket_laser_assets import ROOT, URDF, BASES, layout, link_pose
from farm_sim_devices.basket_laser import beam_segments
try:
    from pxr import Usd, UsdGeom, UsdPhysics
except ImportError:
    Usd = None


@unittest.skipIf(Usd is None, 'Isaac pxr 환경 필요')
class AssetTests(unittest.TestCase):
    def test_all_operational_usds_match_urdf_and_policy(self) -> None:
        root = ET.parse(URDF).getroot()
        profile = json.loads((ROOT/'sim/ros_ws/src/farm_sim_config/config/student_policy.json').read_text())
        policy = json.loads((ROOT/'sim/ros_ws/src/farm_sim_config/config/teacher_policy.json').read_text())
        expected = beam_segments(policy['runtime']['box_min'], policy['runtime']['box_max'], profile['basket_lasers'])
        assets = BASES + sorted((ROOT/'sim/assets/robots/harvest_count_test').glob('*.usd'))
        assets += [ROOT/'sim/assets/robots/harvest_robot/urdf/harvest_robot/harvest_robot.usd']
        for asset in assets:
            with self.subTest(asset=asset):
                stage = Usd.Stage.Open(str(asset)); cache = UsdGeom.XformCache()
                base = stage.GetDefaultPrim().GetPath().AppendChild('base_link')
                base_matrix = np.asarray(cache.GetLocalToWorldTransform(stage.GetPrimAtPath(base))).T
                mount = base_matrix @ link_pose(root, 'arm_2/base_link')
                for i in range(1,4):
                    for side, endpoints in zip(('emitter','receiver'), expected):
                        name = f'basket_laser_{i}_{side}'
                        prim = stage.GetPrimAtPath(str(base)+'/BasketLasers/'+name+'/optical')
                        self.assertTrue(prim)
                        actual = np.asarray(cache.GetLocalToWorldTransform(prim)).T
                        np.testing.assert_allclose(actual, base_matrix @ link_pose(root, name+'_optical'), atol=1e-6)
                        point = (np.linalg.inv(mount) @ actual)[:3,3]+policy['device']['policy_arm_position_m']
                        np.testing.assert_allclose(point, endpoints[i-1], atol=1e-6)
                        head = stage.GetPrimAtPath(str(prim.GetParent().GetPath())+'/housing')
                        self.assertTrue(head.HasAPI(UsdPhysics.CollisionAPI))
                        self.assertFalse(head.HasAPI(UsdPhysics.RigidBodyAPI))
                    beam = stage.GetPrimAtPath(str(base)+f'/BasketLasers/beam_{i}')
                    self.assertFalse(beam.HasAPI(UsdPhysics.CollisionAPI))

    def test_urdf_fixed_sensor_links_have_no_duplicate_names(self) -> None:
        root = ET.parse(URDF).getroot()
        for tag in ('link','joint'):
            names = [p.get('name') for p in root.findall(tag)]
            self.assertEqual(len(names), len(set(names)))
        heads = layout(root, json.loads((ROOT/'sim/ros_ws/src/farm_sim_config/config/student_policy.json').read_text())['basket_lasers'])[2]
        self.assertEqual(len(heads), 6)
        for name, _, _ in heads:
            self.assertIsNotNone(root.find(f"link[@name='{name}']/collision"))
            self.assertEqual(root.find(f"joint[@name='{name}_joint']").get('type'), 'fixed')

if __name__ == '__main__': unittest.main()
