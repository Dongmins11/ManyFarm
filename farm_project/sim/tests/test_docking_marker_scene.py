"""USD Python: 장착 좌표·모델 이동 추종·원본 물리 보존 검사."""
import json
from pathlib import Path
import sys
import unittest

import numpy as np
from pxr import Gf, Usd, UsdGeom, UsdPhysics

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'sim/ros_ws/src/farm_sim_runtime'))
from farm_sim_runtime.docking_marker_scene import install_docking_markers


class DockingMarkerSceneTests(unittest.TestCase):
    def test_real_assets_mounting_and_physics_preserved(self) -> None:
        stage = Usd.Stage.Open(str(ROOT/'sim/assets/envs/output/farm_with_plants_v5.usd'))
        stage.SetEditTarget(stage.GetSessionLayer())
        robot = UsdGeom.Xform.Define(stage, '/World/harvest_robot')
        robot.GetPrim().GetReferences().AddReference(str(ROOT/'sim/assets/robots/harvest_count_test/harvest_robot.usd'))
        before = {str(a.GetPath()): a.Get() for p in stage.Traverse() for a in p.GetAttributes()
                  if a.GetName().startswith(('physics:', 'drive:', 'physx'))}
        selected = 'sim/assets/docking_markers/layout.provisional.json'
        layout = json.loads((ROOT/selected).read_text())
        records = install_docking_markers(stage, ROOT, selected)
        self.assertEqual({r['id'] for r in records}, {40,41,42})
        cache = UsdGeom.XformCache()
        def matrix(path: str) -> np.ndarray:
            return np.asarray(cache.GetLocalToWorldTransform(stage.GetPrimAtPath(path))).T
        for item, record in zip(layout['markers'], records):
            local = np.linalg.inv(matrix(item['reference_prim'])) @ matrix(record['path'])
            np.testing.assert_allclose(local[:3,3], item['center_m'], atol=1e-9)
            np.testing.assert_allclose(local[:3,0], item['right'], atol=1e-9)
            np.testing.assert_allclose(local[:3,1], item['up'], atol=1e-9)
            self.assertFalse(any(p.HasAPI(UsdPhysics.CollisionAPI) for p in Usd.PrimRange(stage.GetPrimAtPath(record['path']))))
        for path, value in before.items():
            self.assertEqual(stage.GetAttributeAtPath(path).Get(), value, path)
        # base_link가 이동하면 마커도 따라가는지 확인한다.
        marker_path = records[0]['path']
        before_position = matrix(marker_path)[:3,3].copy()
        parent = UsdGeom.Xformable(stage.GetPrimAtPath(layout['markers'][0]['parent_prim']))
        parent.AddTranslateOp(opSuffix='test_move').Set(Gf.Vec3d(1.,2.,0.))
        cache.Clear()
        np.testing.assert_allclose(matrix(marker_path)[:3,3]-before_position, [1.,2.,0.], atol=1e-8)

    def test_existing_fleet_without_layout_is_unchanged(self) -> None:
        self.assertEqual(install_docking_markers(None, ROOT, None), [])


if __name__ == '__main__':
    unittest.main()
