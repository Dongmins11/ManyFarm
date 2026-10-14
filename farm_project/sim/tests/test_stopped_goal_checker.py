"""정지 도착 checker의 공통 사전검사·실행 중 파라미터 조회 계약을 검사합니다."""
from pathlib import Path
import sys
from types import SimpleNamespace as NS
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'robot/ros_ws/src/farm_navigation'))
from farm_navigation.arrival import NavigationConfigurationError, validate_goal_checkers
from farm_navigation.nav2_client import Nav2Client
from farm_navigation.navigation_types import NavigationSettings


def parameters(plugin: str = 'StoppedGoalChecker', name: str = 'goal_checker') -> dict:
    values = {'goal_checker_plugins': [name], 'controller_plugins': ['FollowPath'],
              'progress_checker_plugins': ['progress_checker'],
              'min_x_velocity_threshold': .001, 'min_y_velocity_threshold': .001,
              'min_theta_velocity_threshold': .001}
    values.update({f'{name}.{key}': value for key, value in {
        'plugin': f'nav2_controller::{plugin}', 'xy_goal_tolerance': .015,
        'yaw_goal_tolerance': .01, 'stateful': False,
        'symmetric_yaw_tolerance': False,
        'trans_stopped_velocity': .005, 'rot_stopped_velocity': .02,
    }.items()})
    return values


class StoppedGoalCheckerTests(unittest.TestCase):
    def test_stopped_checker_uses_navigation_stop_limits(self) -> None:
        checked = validate_goal_checkers(parameters(), .02, .05)[0]
        self.assertEqual(checked['trans_stopped_velocity'], .005)
        self.assertEqual(checked['rot_stopped_velocity'], .02)
        validate_goal_checkers(parameters(), .02, .05,
                               stopped_linear_limit=.006, stopped_angular_limit=.03)

    def test_missing_nonfinite_nonpositive_and_nonnumeric_velocities_rejected(self) -> None:
        for key in ('trans_stopped_velocity', 'rot_stopped_velocity'):
            for value in (None, True, 0, -.01, float('nan'), float('inf'), '0.001'):
                with self.subTest(key=key, value=value):
                    values = parameters()
                    values[f'goal_checker.{key}'] = value
                    with self.assertRaisesRegex(NavigationConfigurationError, key):
                        validate_goal_checkers(values, .02, .05)
            values = parameters()
            del values[f'goal_checker.{key}']
            with self.assertRaisesRegex(NavigationConfigurationError, key):
                validate_goal_checkers(values, .02, .05)

    def test_default_plugin_velocities_and_looser_than_monitor_limits_rejected(self) -> None:
        for key, value in (('trans_stopped_velocity', .25), ('rot_stopped_velocity', .25),
                           ('trans_stopped_velocity', .0051), ('rot_stopped_velocity', .0201)):
            with self.subTest(key=key, value=value):
                values = parameters()
                values[f'goal_checker.{key}'] = value
                with self.assertRaisesRegex(NavigationConfigurationError, 'must not exceed'):
                    validate_goal_checkers(values, .02, .05)
        with self.assertRaisesRegex(NavigationConfigurationError, 'must not exceed'):
            validate_goal_checkers(parameters(), .02, .05,
                                   stopped_linear_limit=.004, stopped_angular_limit=.01)

    def test_stopped_checker_rechecks_position_and_preserves_tight_pose_gate(self) -> None:
        for value in (True, None, 0, 'false'):
            values = parameters()
            values['goal_checker.stateful'] = value
            with self.subTest(stateful=value), self.assertRaisesRegex(NavigationConfigurationError, 'stateful=false'):
                validate_goal_checkers(values, .02, .05)
        for key, value in (('xy_goal_tolerance', .02), ('yaw_goal_tolerance', .05),
                           ('symmetric_yaw_tolerance', True)):
            values = parameters()
            values[f'goal_checker.{key}'] = value
            with self.subTest(key=key), self.assertRaises(NavigationConfigurationError):
                validate_goal_checkers(values, .02, .05)

    def test_velocity_masking_cannot_hide_nonstopped_motion_completely(self) -> None:
        for thresholds in ((.001, .5, .001), (.003, .004, .001), (.001, .001, .02)):
            values = parameters()
            for axis, value in zip(('x', 'y', 'theta'), thresholds):
                values[f'min_{axis}_velocity_threshold'] = value
            with self.subTest(thresholds=thresholds), self.assertRaisesRegex(NavigationConfigurationError, 'masking thresholds'):
                validate_goal_checkers(values, .02, .05)
        values = parameters()
        for axis in ('x', 'y', 'theta'):
            values[f'min_{axis}_velocity_threshold'] = 0
        self.assertTrue(validate_goal_checkers(values, .02, .05))

    def test_missing_invalid_velocity_masking_thresholds_rejected(self) -> None:
        for axis in ('x', 'y', 'theta'):
            key = f'min_{axis}_velocity_threshold'
            for value in (None, False, -.001, float('nan'), float('inf'), '0'):
                values = parameters()
                values[key] = value
                with self.subTest(key=key, value=value), self.assertRaisesRegex(NavigationConfigurationError, key):
                    validate_goal_checkers(values, .02, .05)
            values = parameters()
            del values[key]
            with self.assertRaisesRegex(NavigationConfigurationError, key):
                validate_goal_checkers(values, .02, .05)

    def test_simple_checker_retains_existing_three_argument_contract(self) -> None:
        values = parameters('SimpleGoalChecker')
        values['goal_checker.stateful'] = True
        del values['goal_checker.trans_stopped_velocity']
        del values['goal_checker.rot_stopped_velocity']
        for axis in ('x', 'y', 'theta'):
            del values[f'min_{axis}_velocity_threshold']
        self.assertEqual(validate_goal_checkers(values, .02, .05), [{
            'id': 'goal_checker', 'xy_goal_tolerance': .015,
            'yaw_goal_tolerance': .01, 'stateful': True}])
        with self.assertRaisesRegex(NavigationConfigurationError, 'unsupported'):
            validate_goal_checkers(parameters('UnknownGoalChecker'), .02, .05)


class GoalCheckerPreflightTests(unittest.TestCase):
    def client(self, values: dict, **settings) -> tuple[Nav2Client, list[list[str]]]:
        client = Nav2Client.__new__(Nav2Client)
        client._settings = NavigationSettings(**settings)
        client._follow = client._navigate = NS(server_is_ready=lambda: True)
        client._parameters = NS(service_is_ready=lambda: True)
        calls = []

        def read(names: list[str], check) -> dict:
            check()
            calls.append(names)
            return {name: values.get(name) for name in names}

        client._read_parameters = read
        return client, calls

    def test_queries_stopped_velocities_only_for_selected_follow_path_checker(self) -> None:
        values = parameters()
        values['goal_checker_plugins'].append('unused')
        values['unused.plugin'] = 'nav2_controller::StoppedGoalChecker'
        client, calls = self.client(values, mode='follow_path')
        result = client.preflight(lambda: None)
        self.assertEqual(result['status'], 'OK')
        self.assertEqual(calls[-1], ['goal_checker.trans_stopped_velocity', 'goal_checker.rot_stopped_velocity',
            'min_x_velocity_threshold', 'min_y_velocity_threshold', 'min_theta_velocity_threshold'])
        self.assertFalse(any(name.startswith('unused.') for names in calls for name in names))
        self.assertEqual(result['checkers'][0]['rot_stopped_velocity'], .02)

    def test_simple_plugin_has_no_extra_parameter_request(self) -> None:
        client, calls = self.client(parameters('SimpleGoalChecker'))
        self.assertEqual(client.preflight(lambda: None)['status'], 'OK')
        self.assertEqual(len(calls), 2)
        self.assertFalse(any(name.endswith('_stopped_velocity') for names in calls for name in names))
        self.assertFalse(any(name.startswith('min_') for names in calls for name in names))

    def test_navigate_to_pose_checks_all_registered_plugins(self) -> None:
        values = parameters('SimpleGoalChecker')
        values.update({key: value for key, value in parameters(name='stopped').items() if key.startswith('stopped.')})
        values['goal_checker_plugins'] = ['goal_checker', 'stopped']
        client, calls = self.client(values)
        result = client.preflight(lambda: None)
        self.assertEqual(len(result['checkers']), 2)
        self.assertEqual(calls[-1], ['stopped.trans_stopped_velocity', 'stopped.rot_stopped_velocity',
            'min_x_velocity_threshold', 'min_y_velocity_threshold', 'min_theta_velocity_threshold'])

    def test_missing_runtime_values_fail_and_actual_monitor_limits_are_used(self) -> None:
        values = parameters()
        del values['goal_checker.rot_stopped_velocity']
        client, _ = self.client(values)
        with self.assertRaisesRegex(NavigationConfigurationError, 'rot_stopped_velocity'):
            client.preflight(lambda: None)
        client, _ = self.client(parameters(), stopped_linear_mps=.004, stopped_angular_rps=.01)
        with self.assertRaisesRegex(NavigationConfigurationError, 'must not exceed'):
            client.preflight(lambda: None)
        values = parameters()
        del values['min_y_velocity_threshold']
        client, _ = self.client(values)
        with self.assertRaisesRegex(NavigationConfigurationError, 'min_y_velocity_threshold'):
            client.preflight(lambda: None)


if __name__ == '__main__':
    unittest.main()
