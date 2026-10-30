"""복귀 단계·오류 분류·재시도 계약을 모의 I/O로 검증한다. ROS 노드는 만들지 않는다."""
from concurrent.futures import Future
from dataclasses import replace
from threading import get_ident
from types import SimpleNamespace as NS
from unittest.mock import Mock, patch
import unittest

from action_msgs.msg import GoalStatus
from geometry_msgs.msg import PoseStamped
from nav_msgs.msg import Path
from nav2_msgs.action import FollowPath
from farm_common.action_handoff import ActionInterrupted
from farm_navigation.collision_recovery import Nav2ControlUnavailable, run_with_collision_recovery
from farm_navigation.nav2_client import Nav2Client
from farm_navigation.navigation_types import NavigationSettings
from harvest_robot.station_return_real import reverse_control_error
from harvest_robot.station_return_states import ReturnController


class ControllerTests(unittest.TestCase):
    def test_states_run_io_in_worker_and_transitions_in_action_thread(self) -> None:
        events = []
        caller = get_ident()
        mission = NS(**{name:lambda n=name:events.append((n, get_ident()))
                        for name in ('prepare', 'navigate', 'cleanup')})
        controller = ReturnController(mission)
        transition = controller.transition
        transitions = []
        def record(state: object) -> None:
            transitions.append((type(state).__name__, get_ident()))
            transition(state)
        controller.transition = record
        controller.run()
        self.assertEqual([x[0] for x in events], ['prepare', 'navigate', 'cleanup'])
        self.assertTrue(all(thread != caller for _, thread in events))
        self.assertEqual([x[0] for x in transitions],
                         ['PrepareReturnState', 'ReverseReturnState', 'CleanupReturnState', 'NoneType'])
        self.assertTrue(all(thread == caller for _, thread in transitions))

    def test_prepare_failure_and_navigation_cancel_always_cleanup(self) -> None:
        for stage in ('prepare', 'navigate'):
            mission = NS(prepare=Mock(), navigate=Mock(), cleanup=Mock())
            error = ActionInterrupted('cancel') if stage == 'navigate' else RuntimeError('prepare')
            getattr(mission, stage).side_effect = error
            controller = ReturnController(mission)
            with self.assertRaises(type(error)):
                controller.run()
            mission.cleanup.assert_called_once()
            if stage == 'prepare':
                mission.navigate.assert_not_called()

    def test_cleanup_failure_is_available_to_action_completion(self) -> None:
        mission = NS(prepare=Mock(), navigate=Mock(), cleanup=Mock(side_effect=RuntimeError('stop')))
        controller = ReturnController(mission)
        controller.run()
        self.assertEqual(str(controller.cleanup_error), 'stop')

    def test_stale_completion_does_not_transition_new_state(self) -> None:
        mission = NS(prepare=Mock(), navigate=Mock(), cleanup=Mock())
        controller = ReturnController(mission)
        old = Future()
        old.set_exception(RuntimeError('old goal'))
        controller._events.put((-1, object(), old))
        controller.run()
        mission.navigate.assert_called_once()
        self.assertIsNone(controller.error)


class RetryTests(unittest.TestCase):
    def client(self, *, classifier=reverse_control_error) -> Nav2Client:
        client = object.__new__(Nav2Client)
        client._settings = NavigationSettings(mode='follow_path', collision_retry_count=5)
        client._retryable_control_error = classifier
        client._pause_clock_factory = None
        client._node = NS(get_clock=lambda:NS(ros_time_is_active=False,
            now=lambda:NS(to_msg=lambda:PoseStamped().header.stamp)), get_logger=lambda:Mock())
        client._pending = client._handle = client._result = None
        return client

    def test_only_aborted_no_valid_control_collision_is_classified(self) -> None:
        path = Path(poses=[PoseStamped(), PoseStamped()])
        cases = [
            (GoalStatus.STATUS_ABORTED, FollowPath.Result.NO_VALID_CONTROL, 'Collision on reverse route', True),
            (GoalStatus.STATUS_ABORTED, FollowPath.Result.NO_VALID_CONTROL, 'Collision on reverse heading alignment', True),
            (GoalStatus.STATUS_ABORTED, FollowPath.Result.NO_VALID_CONTROL, 'Invalid heading', False),
            (GoalStatus.STATUS_CANCELED, FollowPath.Result.NO_VALID_CONTROL, 'Collision on reverse route', False),
            (GoalStatus.STATUS_ABORTED, 999, 'Collision on reverse route', False),
        ]
        for status, code, message, retryable in cases:
            with self.subTest(status=status, code=code, message=message):
                client = self.client()
                client._follow = Mock()
                response = NS(status=status, result=NS(error_code=code, error_msg=message))
                client._wait = Mock(side_effect=[NS(accepted=True, get_result_async=Mock()), response])
                with self.assertRaises(RuntimeError) as raised:
                    client._execute_once((0., 0.), 0., path, lambda:None)
                self.assertEqual(isinstance(raised.exception, Nav2ControlUnavailable), retryable)
                self.assertFalse(client.has_goal)

    def test_default_classifier_is_unchanged(self) -> None:
        client = self.client(classifier=None)
        self.assertTrue(client._retryable_message(''))
        self.assertTrue(client._retryable_message('Collision ahead'))
        self.assertFalse(client._retryable_message('Collision on reverse route'))

    def test_existing_recovery_reuses_path_and_keeps_retry_limit(self) -> None:
        for exhausted in (False, True):
            with self.subTest(exhausted=exhausted):
                client = self.client()
                client._settings = replace(client._settings, collision_retry_count=2)
                client._recovery_stop = Mock()
                client._recovery_probe = lambda:True
                client._execute_once = Mock(side_effect=([Nav2ControlUnavailable('collision')]*3
                    if exhausted else [Nav2ControlUnavailable('collision'), 4]))
                clock = [0.]
                def recovery(*args: object, **kwargs: object) -> int:
                    return run_with_collision_recovery(*args, **kwargs, clock=lambda:clock[0],
                        sleep=lambda dt:clock.__setitem__(0, clock[0]+dt))
                path = Path()
                with patch('farm_navigation.nav2_client.run_with_collision_recovery', recovery):
                    if exhausted:
                        with self.assertRaises(Nav2ControlUnavailable):
                            client.execute((0.,0.), 0., path, lambda:None)
                    else:
                        self.assertEqual(client.execute((0.,0.), 0., path, lambda:None), 4)
                self.assertEqual(client._execute_once.call_count, 3 if exhausted else 2)
                self.assertTrue(all(call.args[2] is path for call in client._execute_once.call_args_list))
                self.assertTrue(client._recovery_stop.called)

    def test_cancel_during_retry_wait_prevents_resend(self) -> None:
        client = self.client()
        client._recovery_probe = lambda:True
        canceled = [False]
        client._recovery_stop = lambda:canceled.__setitem__(0, True)
        client._execute_once = Mock(side_effect=Nav2ControlUnavailable('collision'))
        def check() -> None:
            if canceled[0]:
                raise ActionInterrupted('operator cancel')
        with self.assertRaises(ActionInterrupted):
            client.execute((0.,0.), 0., Path(), check)
        client._execute_once.assert_called_once()


if __name__ == '__main__':
    unittest.main()
