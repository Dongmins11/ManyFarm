"""ROS 장치 없이 sim/real 경과시간·일시정지·취소 제한을 가상 시계로 검증한다."""
from types import SimpleNamespace as NS
from unittest.mock import patch
import unittest

from action_msgs.msg import GoalStatus
from builtin_interfaces.msg import Time as TimeMsg
from geometry_msgs.msg import PoseStamped
from nav_msgs.msg import Path
from rclpy.task import Future
from farm_navigation.nav2_client import Nav2Client
from farm_navigation.navigation_types import NavigationSettings


class ExecutionClockTests(unittest.TestCase):
    def setUp(self):
        self.wall, self.sim, self.rate = 0., 0., .42
        self.pause_until, self.finish_sim = 0., None
        self.result = Future()
        self.response = NS(status=GoalStatus.STATUS_SUCCEEDED, result=NS(error_code=0))
        self.clock = NS(ros_time_is_active=True, now=self.now)
        self.client = Nav2Client.__new__(Nav2Client)
        self.client._node = NS(get_clock=lambda:self.clock, get_logger=lambda:NS(warning=lambda _:None))
        self.client._settings = NavigationSettings(mode='follow_path')
        self.client._pending = self.client._handle = self.client._result = None
        self.handle = NS(accepted=True, get_result_async=lambda:self.result,
                         cancel_goal_async=lambda:Future())
        accepted = Future(); accepted.set_result(self.handle)
        self.client._follow = NS(send_goal_async=lambda *a,**k:accepted)
        self.path = Path(); self.path.poses = [PoseStamped(), PoseStamped()]
        self.addCleanup(patch.stopall)
        patch('farm_navigation.nav2_client.time.monotonic', lambda:self.wall).start()
        patch('farm_navigation.nav2_client.time.sleep', self.sleep).start()

    def now(self):
        return NS(nanoseconds=round(self.sim*1e9),
                  to_msg=lambda:TimeMsg(sec=int(self.sim), nanosec=round((self.sim%1)*1e9)))

    def sleep(self, unused):
        # 수백 초를 기다리지 않고 반복마다 가상 실시간1초를 진행한다.
        self.wall += 1.
        if self.wall > self.pause_until:
            self.sim += self.rate
        if self.finish_sim is not None and self.sim >= self.finish_sim and not self.result.done():
            self.result.set_result(self.response)

    def execute(self, check=lambda:None):
        return self.client.execute((0.,0.), 0., self.path, check)

    def test_slow_sim_completes_after_300_wall_seconds(self):
        self.finish_sim = 200.
        self.assertEqual(self.execute(), GoalStatus.STATUS_SUCCEEDED)
        self.assertGreater(self.wall, 300.)
        self.assertLess(self.sim, 300.)
        self.assertFalse(self.client.has_goal)

    def test_navigate_to_pose_uses_same_execution_clock(self):
        self.client._settings = NavigationSettings(mode='navigate_to_pose')
        self.client._navigate = self.client._follow
        self.finish_sim = 200.
        self.assertEqual(self.execute(), GoalStatus.STATUS_SUCCEEDED)
        self.assertGreater(self.wall, 300.)

    def test_installed_ros_clock_selects_sim_and_monotonic(self):
        from rclpy.clock import ROSClock
        from rclpy.time import Time
        from rclpy.time_source import TimeSource
        clock = ROSClock()
        source = TimeSource()
        source.attach_clock(clock)
        self.client._node = NS(get_clock=lambda:clock)
        self.wall = 12.
        self.assertEqual(self.client._execution_clock()(), 12.)
        source.ros_time_is_active = True
        clock.set_ros_time_override(Time(seconds=30))
        read = self.client._execution_clock()
        self.assertEqual(read(), 30.)
        self.wall = 500.
        self.assertEqual(read(), 30.)
        clock.set_ros_time_override(Time(seconds=31))
        self.assertEqual(read(), 31.)

    def test_sim_limit_still_expires_and_preserves_goal_for_cancel(self):
        with self.assertRaisesRegex(TimeoutError, '주행 완료 시간 초과'):
            self.execute()
        self.assertGreaterEqual(self.sim, 300.)
        self.assertLess(self.sim, 301.)
        self.assertGreater(self.wall, 700.)
        self.assertTrue(self.client.has_goal)
        self.assertIs(self.client._result, self.result)

    def test_pause_does_not_consume_execution_budget(self):
        self.pause_until, self.finish_sim = 400., 10.
        self.assertEqual(self.execute(), GoalStatus.STATUS_SUCCEEDED)
        self.assertGreater(self.wall, 400.)

    def test_real_uses_monotonic_even_if_ros_clock_stops(self):
        self.clock.ros_time_is_active = False
        self.clock.now = lambda: self.fail('real 경과시간은 ROS 시계를 읽지 않아야 한다')
        self.rate = 0.
        with self.assertRaisesRegex(TimeoutError, '주행 완료 시간 초과'):
            self.execute()
        self.assertEqual(self.wall, 300.)

    def test_response_timeout_waits_for_sim_resume(self):
        self.pause_until = 50.
        with self.assertRaisesRegex(TimeoutError, '응답 시간 초과'):
            self.client._wait(Future(), 5., lambda:None)
        self.assertGreaterEqual(self.sim, 5.)
        self.assertGreater(self.wall, 50.)

    def test_cancel_timeout_waits_for_sim_resume(self):
        self.pause_until = 50.
        self.client._handle, self.client._result = self.handle, self.result
        with self.assertRaisesRegex(TimeoutError, '응답 시간 초과'):
            self.client.cancel()
        self.assertGreaterEqual(self.sim, 10.)
        self.assertGreater(self.wall, 50.)
        self.assertTrue(self.client.has_goal)

    def test_operator_cancel_is_checked_while_sim_paused(self):
        self.rate = 0.
        def check():
            if self.wall >= 5.:
                raise RuntimeError('operator_cancel')
        with self.assertRaisesRegex(RuntimeError, 'operator_cancel'):
            self.execute(check)
        self.assertEqual(self.wall, 5.)
        self.assertTrue(self.client.has_goal)

    def test_sim_rewind_fails_instead_of_extending_deadline(self):
        self.sim = 100.
        def check():
            if self.wall == 3.:
                self.sim = 0.
        with self.assertRaisesRegex(RuntimeError, '시계가 역행'):
            self.execute(check)
        self.assertTrue(self.client.has_goal)

    def test_tf_recovery_overall_budget_also_uses_sim_time(self):
        self.client._settings = NavigationSettings(mode='follow_path', tf_recovery_enabled=True)
        self.client._recovery_probe = lambda:True
        self.client._last_control_feedback = 0.
        self.client._stop_publishers = []
        self.finish_sim = 200.
        self.assertEqual(self.execute(), GoalStatus.STATUS_SUCCEEDED)
        self.assertGreater(self.wall, 300.)

    def test_tf_recovery_overall_budget_expires_in_sim_time(self):
        self.client._settings = NavigationSettings(mode='follow_path', tf_recovery_enabled=True)
        self.client._recovery_probe = lambda:True
        self.client._last_control_feedback = 0.
        self.client._stop_publishers = []
        with self.assertRaisesRegex(TimeoutError, '전체 주행 시간 초과'):
            self.execute()
        self.assertGreaterEqual(self.sim, 300.)
        self.assertGreater(self.wall, 700.)


    def adaptive_route(self):
        self.client._nominal_linear_speed_mps = .1
        self.client._node.get_logger = lambda:NS(warning=lambda _:None, info=lambda _:None)
        self.path.poses[1].pose.position.x = 27.5

    def test_long_trip_can_finish_after_old_deadline(self):
        self.adaptive_route(); self.finish_sim = 400.
        self.assertEqual(self.execute(), GoalStatus.STATUS_SUCCEEDED)
        self.assertGreater(self.sim, 300.)
        self.assertFalse(self.client.has_goal)

    def test_long_trip_still_times_out_and_keeps_cancel_handle(self):
        self.adaptive_route()
        with self.assertRaisesRegex(TimeoutError, '주행 완료 시간 초과'):
            self.execute()
        self.assertGreaterEqual(self.sim, 610.)
        self.assertLess(self.sim, 611.)
        self.assertTrue(self.client.has_goal)

    def test_tf_recovery_uses_same_adaptive_outer_budget(self):
        self.adaptive_route()
        self.client._settings = NavigationSettings(mode='follow_path', tf_recovery_enabled=True)
        self.client._recovery_probe = lambda:True
        self.client._last_control_feedback = 0.
        self.client._stop_publishers = []
        self.finish_sim = 400.
        self.assertEqual(self.execute(), GoalStatus.STATUS_SUCCEEDED)

    def test_real_uses_adaptive_wall_budget(self):
        self.adaptive_route(); self.clock.ros_time_is_active = False; self.rate = 0.
        with self.assertRaisesRegex(TimeoutError, '주행 완료 시간 초과'):
            self.execute()
        self.assertEqual(self.wall, 610.)


if __name__ == '__main__':
    unittest.main()
