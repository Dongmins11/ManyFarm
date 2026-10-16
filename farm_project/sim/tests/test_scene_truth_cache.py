"""평가 경계 캐시가 이동·기하 편집·가시성 변경을 보존하는지 실제 USD로 검사한다."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
import numpy as np
try:
    from pxr import Gf, Sdf, Usd, UsdGeom
except ImportError:
    Usd = None
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'ros_ws/src/farm_sim_devices'))
from farm_sim_devices.scene_truth import SceneTruth


@unittest.skipIf(Usd is None, 'Isaac USD Python 환경 필요')
class SceneTruthCacheTests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.output = Path(self.directory.name)/'scene.json'
        self.stage = Usd.Stage.CreateInMemory()
        self.parent = UsdGeom.Xform.Define(self.stage, '/World/Fruits')
        self.fruit = UsdGeom.Xform.Define(self.stage, '/World/Fruits/Fruit')
        self.fruit.GetPrim().CreateAttribute('crop:color', Sdf.ValueTypeNames.String).Set('red')
        self.position = self.fruit.AddTranslateOp()
        self.rotation = self.fruit.AddRotateZOp()
        self.mesh = self.make_mesh('/World/Fruits/Fruit/Model', (0, 0, 0))
        self.truth = SceneTruth(self.stage, self.output, 'harvest_01', 'map', 'test',
                                dict(center_m=[0,0,0], size_m=[1,1,1]))

    def make_mesh(self, path: str, offset: tuple) -> object:
        mesh = UsdGeom.Mesh.Define(self.stage, path)
        mesh.CreatePointsAttr([Gf.Vec3f(0,0,0),Gf.Vec3f(1,0,0),Gf.Vec3f(0,1,0),Gf.Vec3f(0,0,1)])
        mesh.CreateFaceVertexCountsAttr([3]*4)
        mesh.CreateFaceVertexIndicesAttr([0,2,1,0,1,3,0,3,2,1,2,3])
        mesh.AddTranslateOp().Set(Gf.Vec3d(*offset))
        return mesh

    def tearDown(self) -> None:
        self.truth.close()
        self.directory.cleanup()

    def assert_fresh_bounds(self) -> None:
        self.truth.capture(1, np.eye(4))
        result = json.loads(self.output.read_text())
        self.assertTrue(result['complete'])
        bound = UsdGeom.BBoxCache(Usd.TimeCode.Default(), ['default','render'], useExtentsHint=False)
        expected = bound.ComputeWorldBound(self.fruit.GetPrim()).ComputeAlignedRange()
        np.testing.assert_allclose(result['fruits'][0]['aabb_world_m'],
                                   [expected.GetMin(), expected.GetMax()], atol=1e-10)

    def test_root_and_parent_motion_reuse_local_geometry(self) -> None:
        self.assert_fresh_bounds()
        for angle in (0.,37.,90.,-128.):
            self.rotation.Set(angle)
            self.position.Set(Gf.Vec3d(angle/10,2,3))
            self.assertFalse(self.truth.geometry_dirty)
            self.assert_fresh_bounds()
        self.parent.AddTranslateOp().Set(Gf.Vec3d(2,-4,1))
        self.assert_fresh_bounds()

    def test_child_motion_points_and_new_mesh_invalidate(self) -> None:
        self.assert_fresh_bounds()
        self.mesh.GetPointsAttr().Set([Gf.Vec3f(0,0,0),Gf.Vec3f(2,0,0),Gf.Vec3f(0,3,0),Gf.Vec3f(0,0,4)])
        self.assertTrue(self.truth.geometry_dirty)
        self.assert_fresh_bounds()
        self.mesh.AddRotateZOp().Set(29.)
        self.assert_fresh_bounds()
        self.make_mesh('/World/Fruits/Fruit/Other', (-3,-2,-1))
        self.rotation.Set(37.)
        self.assert_fresh_bounds()

    def test_missing_geometry_is_still_incomplete(self) -> None:
        self.assert_fresh_bounds()
        self.mesh.GetPointsAttr().Set([])
        self.truth.capture(2,np.eye(4))
        result=json.loads(self.output.read_text())
        self.assertFalse(result['complete'])
        self.assertIn('Missing fruit geometry',result['error'])

    def test_visibility_changes_are_not_stale(self) -> None:
        self.assert_fresh_bounds()
        self.fruit.CreateVisibilityAttr('invisible')
        self.truth.capture(2,np.eye(4))
        self.assertEqual(json.loads(self.output.read_text())['fruits'],[])
        self.fruit.GetVisibilityAttr().Set('inherited')
        self.assert_fresh_bounds()


if __name__ == '__main__':
    unittest.main()
