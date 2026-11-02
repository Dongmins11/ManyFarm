"""먼 쪽 깊이 확장 시 가까운 경계·정차 목표·기존 창 재사용을 검증한다."""
from dataclasses import replace
from pathlib import Path
import sys
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scout_robot.b_planner import Config, Fruit, plan_harvest, extend_plan

class FarDepthExtension(unittest.TestCase):
    def test_far_only_and_goal_unchanged(self):
        cfg = Config(route_end=2.)
        fruit = Fruit('a', .5, 0., .5)
        old = plan_harvest([fruit], cfg).tasks[0]
        expanded = replace(cfg, far_depth_extension=.15)
        plan = plan_harvest([fruit], expanded)
        new = plan.tasks[0]
        self.assertAlmostEqual(new.window_y_min, old.window_y_min)
        self.assertAlmostEqual(new.window_y_max, old.window_y_max + .15)
        self.assertEqual((new.base_x,new.base_y,new.arm_x), (old.base_x,old.base_y,old.arm_x))
        result = extend_plan(plan, [Fruit('far', .55, .19, .5)], expanded)
        self.assertEqual(len(result.tasks), 1)
        self.assertIn('far', result.tasks[0].member_ids)
        rejected = plan_harvest([Fruit('near', .5, -.051, .5), Fruit('outside', .6, .201, .5)], expanded)
        self.assertEqual(len(rejected.tasks), 0)
        self.assertEqual(len(rejected.holds), 2)

    def test_invalid_extension(self):
        for value in (-.1, float('nan'), float('inf')):
            with self.assertRaises(ValueError):
                Config(far_depth_extension=value).validate()

if __name__ == '__main__':
    unittest.main()
