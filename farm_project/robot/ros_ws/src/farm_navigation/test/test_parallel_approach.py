"""짧은 작업 이동과 허용 범위 밖 정렬/횡오차/후진 거부를 검증한다."""
import math
import unittest
from farm_navigation.navigation_types import RoutePlan
from farm_navigation.parallel_approach import straight_plan


class ParallelApproachTests(unittest.TestCase):
    def setUp(self):
        self.template = RoutePlan('test', 'revision', 'map', (), (), 0.)
        self.corridor = {'entry': (0., 0.), 'exit': (0., 10.), 'yaw': math.pi / 2}
        self.heading = math.radians(3)

    def plan(self, xy, goal, yaw=math.pi / 2):
        return straight_plan(self.template, self.corridor, xy, yaw, goal, .05, self.heading)

    def test_recorded_short_forward_moves_keep_real_goal(self):
        for lateral, forward, yaw_error in [(.018109734122007, .12717299956994, -.2822570531),
                                            (.012837974884969, .090200501970642, .0445519944)]:
            with self.subTest(forward=forward):
                start = (lateral, 2.)
                goal = (0., 2. + forward)
                plan = self.plan(start, goal, math.pi / 2 + math.radians(yaw_error))
                self.assertEqual(plan.points, (start, goal))
                self.assertAlmostEqual(plan.distance_m, math.dist(start, goal))
                self.assertGreater(math.atan2(lateral, forward), self.heading)
                self.assertEqual(plan.edge_ids, ())

    def test_lateral_limit_independent_of_forward_distance(self):
        for forward in (.02, .1, 2.):
            with self.subTest(forward=forward):
                self.plan((.049, 2.), (0., 2. + forward))
                with self.assertRaisesRegex(RuntimeError, 'APPROACH_RECOVERY_REQUIRED'):
                    self.plan((.051, 2.), (0., 2. + forward))

    def test_misaligned_body_still_requires_recovery(self):
        for sign in (-1, 1):
            with self.assertRaisesRegex(RuntimeError, 'APPROACH_RECOVERY_REQUIRED'):
                self.plan((0., 2.), (0., 2.1), math.pi / 2 + sign * math.radians(3.1))

    def test_backward_and_zero_forward_still_rejected(self):
        for goal in ((0., 1.9), (.01, 2.)):
            with self.assertRaisesRegex(RuntimeError, 'APPROACH_RECOVERY_REQUIRED'):
                self.plan((0., 2.), goal)

    def test_direction_is_corridor_relative(self):
        corridor = dict(self.corridor, yaw=math.pi)
        plan = straight_plan(self.template, corridor, (2., .02), math.pi,
                             (1.9, 0.), .05, self.heading)
        self.assertEqual(plan.points[-1], (1.9, 0.))


if __name__ == '__main__':
    unittest.main()
