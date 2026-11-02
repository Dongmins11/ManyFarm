"""실제 수확 자산의 외형 인스턴스 해제 시 기하·물리·원본 보존 검사."""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'sim/ros_ws/src/farm_sim_runtime'))
from farm_sim_runtime.robotarm_asset_setup import expand_box_visual_instances
try:
    from pxr import Usd, UsdGeom
except ImportError:
    Usd = None


@unittest.skipIf(Usd is None, 'USD Python 환경이 필요합니다.')
class RobotVisualInstancesTests(unittest.TestCase):
    def test_geometry_physics_and_source_preserved(self) -> None:
        stage = Usd.Stage.CreateInMemory()
        robot = UsdGeom.Xform.Define(stage, '/Robot').GetPrim()
        robot.GetReferences().AddReference(str(
            ROOT/'sim/assets/robots/harvest_count_test/harvest_robot.usd'))
        root_before = stage.GetRootLayer().ExportToString()

        def snapshot() -> dict:
            return {str(p.GetPath()): dict(type=p.GetTypeName(), schemas=p.GetAppliedSchemas(),
                attributes={a.GetName(): str(a.Get()) for a in p.GetAttributes()},
                relationships={r.GetName(): [str(t) for t in r.GetTargets()]
                               for r in p.GetRelationships()})
                for p in Usd.PrimRange(robot, Usd.TraverseInstanceProxies())}

        before = snapshot()
        paths = expand_box_visual_instances(stage, robot)
        self.assertIn('/Robot/front_left_post/visuals', paths)
        self.assertIn('/Robot/box_front_wall/visuals', paths)
        self.assertTrue(all(not stage.GetPrimAtPath(p).IsInstance() for p in paths))
        self.assertTrue(stage.GetPrimAtPath('/Robot/box_front_wall/collisions').IsInstance())
        self.assertEqual(snapshot(), before)
        self.assertEqual(stage.GetRootLayer().ExportToString(), root_before)
        self.assertEqual(expand_box_visual_instances(stage, robot), [])


if __name__ == '__main__':
    unittest.main()
