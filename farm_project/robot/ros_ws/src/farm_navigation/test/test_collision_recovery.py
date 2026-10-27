"""장치 없는 재시도 경계 검사. 실제 주행 시험과 구분한다."""
import unittest
from farm_navigation.collision_recovery import Nav2ControlUnavailable, run_with_collision_recovery
from farm_navigation.navigation_types import NavigationSettings

class RecoveryTests(unittest.TestCase):
    def run_case(self, failures, retries, ready=lambda: True, check=lambda: None):
        now = [0.0]
        attempts, stops, logs, waiting = [], [], [], []
        def execute():
            attempts.append(now[0])
            if len(attempts) <= failures:
                raise Nav2ControlUnavailable('106')
            return 4
        def sleep(dt):
            now[0] += dt
        result = run_with_collision_recovery(execute, ready, lambda: stops.append(now[0]),
            check, retries, logs.append, clock=lambda: now[0], sleep=sleep, waiting=waiting.append)
        return result, attempts, stops, logs, waiting

    def test_two_failures_then_success(self):
        result, attempts, stops, logs, waiting = self.run_case(2, 5)
        self.assertEqual(result, 4)
        self.assertEqual(len(attempts), 3)
        self.assertGreaterEqual(attempts[1]-attempts[0], 2.)
        self.assertTrue(stops)
        self.assertEqual(waiting, [True, False, True, False])
        self.assertIn('retry=2/5', logs[2])

    def test_limit_and_default_disabled(self):
        for retries in (0, 1, 5):
            with self.assertRaises(Nav2ControlUnavailable):
                self.run_case(9, retries)
        self.assertEqual(NavigationSettings.from_mapping({}).collision_retry_count, 0)
        for value in (True, -1, 1.5, '5'):
            with self.assertRaises(ValueError):
                NavigationSettings.from_mapping({'collision_retry_count': value})

    def test_unready_times_out(self):
        with self.assertRaises(TimeoutError):
            self.run_case(1, 5, ready=lambda: False)

    def test_other_error_is_not_retried(self):
        def fail():
            raise RuntimeError('105')
        with self.assertRaisesRegex(RuntimeError, '105'):
            run_with_collision_recovery(fail, lambda: True, lambda: None, lambda: None, 5, lambda _: None)

    def test_cancel_during_wait(self):
        calls = [0]
        def check():
            calls[0] += 1
            if calls[0] == 3:
                raise InterruptedError('cancel')
        with self.assertRaises(InterruptedError):
            self.run_case(2, 5, check=check)

class ClientRecoveryTests(unittest.TestCase):
    def test_retry_excludes_wait_and_keeps_route_budget(self):
        from unittest.mock import Mock, patch
        from types import SimpleNamespace
        from farm_navigation.nav2_client import Nav2Client
        client = Nav2Client.__new__(Nav2Client)
        client._settings = NavigationSettings(mode='follow_path', collision_retry_count=5, goal_timeout_s=1.)
        client._recovery_probe = lambda: True
        client._recovery_stop = lambda: None
        client._node = SimpleNamespace(get_logger=lambda: SimpleNamespace(warning=lambda _: None))
        now = [0.]
        client._execution_clock = lambda: lambda: now[0]
        client._execution_timeout = Mock(return_value=3.)
        calls = []
        def execute(xy, yaw, path, check):
            check()
            calls.append(1)
            if len(calls) == 1:
                raise Nav2ControlUnavailable('106')
            now[0] += 2.
            check()  # 대기 2초와 실행 2초 중 실행만 3초 예산에 포함한다.
            return 4
        client._execute_once = execute
        def recovery(*args, **kwargs):
            def sleep(dt):
                now[0] += dt
            return run_with_collision_recovery(*args, **kwargs, clock=lambda: now[0], sleep=sleep)
        with patch('farm_navigation.nav2_client.run_with_collision_recovery', side_effect=recovery):
            self.assertEqual(client._execute_authorized((0., 0.), 0., None, lambda: None), 4)
        self.assertEqual(len(calls), 2)
        client._execution_timeout.assert_called_once_with(None)
