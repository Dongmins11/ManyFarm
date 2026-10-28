"""실물 인계 통합 시 보존할 시뮬 주행·공통 소유권 경계 검사."""
import math
from pathlib import Path
import sys
import threading
from types import SimpleNamespace as S
import unittest

ROOT = Path(__file__).resolve().parents[2]
for package in ('farm_common', 'farm_navigation', 'harvest_robot'):
    sys.path.insert(0, str(ROOT/'robot/ros_ws/src'/package))

from farm_common.action_handoff import ActionHandoff
from farm_navigation.nav2_client import Nav2Client
from farm_navigation.navigation_types import NavigationSettings, RoutePlan
from farm_navigation.parallel_approach import straight_plan
from harvest_robot.configuration import load_harvest_config
from harvest_robot.jetson_state import JetsonSettings


class MergeBoundaryTests(unittest.TestCase):
    def test_short_forward_window_keeps_independent_lateral_tolerance(self):
        # 2cm 전방·1cm 횡오차는 목표선 각도가 크지만 D-059 기본 정책상 허용된다.
        template = RoutePlan('test', 'revision', 'map', (), (), 0.)
        plan = straight_plan(template, {'yaw': 0.}, (0., 0.), 0., (.02, .01), .02, .05)
        self.assertEqual(plan.points[-1], (.02, .01))
        with self.assertRaisesRegex(RuntimeError, 'path_heading'):
            straight_plan(template, {'yaw': 0.}, (0., 0.), 0., (.02, .01), .02, .05,
                          path_heading_limit=math.radians(5.))

    def test_explicit_path_limit_does_not_relax_body_or_forward_checks(self):
        template = RoutePlan('test', 'revision', 'map', (), (), 0.)
        for yaw, target, reason in ((.1, (1., 0.), 'body_heading'),
                                    (0., (-1., 0.), 'not_ahead')):
            with self.subTest(reason=reason), self.assertRaisesRegex(RuntimeError, reason):
                straight_plan(template, {'yaw': 0.}, (0., 0.), yaw, target, .02, .05,
                              path_heading_limit=math.radians(5.))

    def test_distance_budget_and_explicit_handoff_clock_keep_distinct_policies(self):
        client = Nav2Client.__new__(Nav2Client)
        client._settings = NavigationSettings(mode='follow_path')
        client._nominal_linear_speed_mps = .1
        path = S(poses=[S(pose=S(position=S(x=x, y=0.))) for x in (0., 30.)])
        self.assertEqual(client._execution_timeout(path), 660.)
        client._pause_clock_factory = lambda: lambda: 0.
        self.assertEqual(client._execution_timeout(path), 300.)

    def test_external_handoff_check_does_not_hold_ownership_lock(self):
        handoff = ActionHandoff()
        self.assertTrue(handoff.reserve('transfer', 'T1', preempt=False, interruptible=False))
        observed = threading.Event()
        workers = []
        def check():
            def inspect():
                self.assertEqual(handoff.current, ('transfer', 'T1'))
                observed.set()
            worker = threading.Thread(target=inspect, daemon=True)
            workers.append(worker)
            worker.start()
            self.assertTrue(observed.wait(1.), '외부 check 중 소유권 조회가 잠금에 막혔습니다.')
        try:
            handoff.acquire('transfer', 'T1', check)
            self.assertFalse(handoff.reserve('return', 'R1'))
        finally:
            handoff.release('transfer', 'T1')
            for worker in workers:
                worker.join(1.)

    def test_existing_sim_profile_does_not_enable_real_hardware_gates(self):
        config = load_harvest_config(ROOT/'sim/ros_ws/src/farm_sim_config/config/harvest_task.json', ROOT)
        self.assertFalse(config['transfer']['enabled'])
        self.assertIsNone(JetsonSettings.from_config(config.get('jetson_connection', {})))
        self.assertNotIn('handoff_runtime', config)


if __name__ == '__main__':
    unittest.main()
