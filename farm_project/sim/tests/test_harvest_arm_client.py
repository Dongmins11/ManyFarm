"""Isaac/ROS 없이 내부 팔 Action의 수량 전달과 취소 소유권을 검사합니다."""
from concurrent.futures import Future
from dataclasses import dataclass
import importlib
from pathlib import Path
import sys
import threading
from types import ModuleType, SimpleNamespace as NS
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'robot/ros_ws/src/harvest_robot'))
from harvest_robot.arm_client import ArmActionClient, ArmActionSettings, ArmExecutionError
from harvest_robot.contract import result_fields
from harvest_robot.mission import HarvestMission, MissionCanceled


def done(value: object) -> Future:
    future = Future()
    future.set_result(value)
    return future


def goal() -> NS:
    return NS(robot_id='harvest_01', map_id='farm', timestamp='now', harvest_task=NS(
        task_id='task', window_id='window', expected_count=9,
        goal_pose=NS(position=NS(x=1., y=2.), yaw=0.)))


def terminal(status: int = 4, success: int = 2, failed: int = 1, **fields: object) -> NS:
    data = result_fields(goal(), {4: 'SUCCESS', 5: 'CANCELED', 6: 'FAILED'}[status],
                         harvested_count=success, failed_count=failed)
    data.update(fields)
    return NS(status=status, result=NS(**data))


def feedback(success: int, failed: int, **fields: object) -> NS:
    data = dict(robot_id='harvest_01', task_id='task', success_count=success, failed_count=failed)
    data.update(fields)
    return NS(feedback=NS(**data))


class HandleFixture:
    def __init__(self, result: Future, cancel_terminal: NS | None = None) -> None:
        self.accepted, self.result = True, result
        self.cancel_terminal = cancel_terminal
        self.cancel_requests = 0
        self.goal_id = NS(uuid=list(range(16)))
        self.cancel_ack = NS(return_code=0, goals_canceling=[NS(goal_id=self.goal_id)])

    def get_result_async(self) -> Future:
        return self.result

    def cancel_goal_async(self) -> Future:
        self.cancel_requests += 1
        if self.cancel_terminal is not None:
            self.result.set_result(self.cancel_terminal)
        return done(self.cancel_ack)


class ClientFixture:
    def __init__(self, handle: HandleFixture, *, pending: Future | None = None) -> None:
        self.handle = handle
        self.pending = done(handle) if pending is None else pending
        self.ready = True
        self.sent = False
        self.callback = None
        self.initial_feedback = []

    def server_is_ready(self) -> bool:
        return self.ready

    def send_goal_async(self, request: NS, *, feedback_callback: object) -> Future:
        self.sent, self.callback = True, feedback_callback
        for value in self.initial_feedback:
            feedback_callback(value)
        return self.pending

    def destroy(self) -> None:
        pass


def client(raw: ClientFixture) -> ArmActionClient:
    settings = ArmActionSettings('sim/harvest_arm', .001, .001, .001, .001)
    return ArmActionClient(None, settings, client=raw)


class ArmClientTests(unittest.TestCase):
    def test_partial_result_forwarded_without_expected_quota_and_late_feedback_ignored(self) -> None:
        raw = ClientFixture(HandleFixture(done(terminal())))
        raw.initial_feedback = [feedback(0, 0), feedback(1, 0)]
        arm, counts = client(raw), []
        result = arm.execute(goal(), lambda: None, lambda a, b: counts.append((a, b)))
        self.assertEqual(result['result_code'], 'SUCCESS')
        self.assertEqual((result['harvested_count'], result['failed_count']), (2, 1))
        self.assertEqual(counts, [(0, 0), (1, 0), (2, 1)])
        self.assertFalse(arm.has_goal)
        raw.callback(feedback(99, 0))
        self.assertEqual(counts[-1], (2, 1))

    def test_cancel_after_late_acceptance_waits_terminal_and_preserves_counts(self) -> None:
        result, pending = Future(), Future()
        handle = HandleFixture(result, terminal(5, 1, 0))
        raw = ClientFixture(handle, pending=pending)
        raw.initial_feedback = [feedback(1, 0)]
        arm, counts = client(raw), []
        def check() -> None:
            if raw.sent:
                raise MissionCanceled('cancel')
        with self.assertRaises(MissionCanceled):
            arm.execute(goal(), check, lambda a, b: counts.append((a, b)))
        self.assertTrue(arm.has_goal)
        pending.set_result(handle)
        result = arm.cancel()
        self.assertEqual(result['result_code'], 'CANCELED')
        self.assertEqual(counts[-1], (1, 0))
        self.assertEqual(handle.cancel_requests, 1)
        self.assertFalse(arm.has_goal)

    def test_cancel_ack_without_terminal_is_not_completion(self) -> None:
        raw = ClientFixture(HandleFixture(Future()))
        arm = client(raw)
        with self.assertRaisesRegex(ArmExecutionError, '시간 초과'):
            arm.execute(goal(), lambda: None, lambda *_: None)
        with self.assertRaises(ArmExecutionError):
            arm.cancel()
        self.assertTrue(arm.has_goal)
        self.assertEqual(raw.handle.cancel_requests, 1)

    def test_canceled_requires_own_ack_but_terminal_race_preserves_success(self) -> None:
        for status in (4, 5, 6):
            with self.subTest(status=status):
                raw = ClientFixture(HandleFixture(Future(), terminal(status)))
                raw.handle.cancel_ack = NS(return_code=0, goals_canceling=[NS(goal_id=NS(uuid=[99]*16))])
                arm = client(raw)
                with self.assertRaises(ArmExecutionError):
                    arm.execute(goal(), lambda: None, lambda *_: None)
                if status == 5:
                    with self.assertRaisesRegex(ArmExecutionError, 'ACK'):
                        arm.cancel()
                    self.assertTrue(arm.has_goal)
                else:
                    self.assertEqual(arm.cancel()['result_code'], {4:'SUCCESS',6:'FAILED'}[status])
                    self.assertFalse(arm.has_goal)

    def test_identity_count_regression_and_status_mismatch_rejected(self) -> None:
        for response in (terminal(window_id='other'), terminal(success=0),
                         terminal(result_code='FAILED'), terminal(harvested_count=-1)):
            with self.subTest(response=response):
                raw = ClientFixture(HandleFixture(done(response)))
                raw.initial_feedback = [feedback(1, 0)]
                with self.assertRaises(ArmExecutionError) as caught:
                    client(raw).execute(goal(), lambda: None, lambda *_: None)
                self.assertEqual(caught.exception.code, 'ARM_PROTOCOL_ERROR')

    def test_unavailable_and_rejected_do_not_create_active_goal(self) -> None:
        for unavailable in (True, False):
            raw = ClientFixture(HandleFixture(done(terminal())))
            raw.ready = not unavailable
            raw.handle.accepted = False
            arm = client(raw)
            with self.assertRaises(ArmExecutionError) as caught:
                arm.execute(goal(), lambda: None, lambda *_: None)
            self.assertEqual(caught.exception.code, 'ARM_UNAVAILABLE' if unavailable else 'ARM_REJECTED')
            self.assertFalse(arm.has_goal)

    def test_settings_and_failed_result(self) -> None:
        for config in ({}, {'endpoint': ''}, {'endpoint': 'x', 'cancel_timeout_s': 0},
                       {'endpoint': 'x', 'execution_timeout_s': float('nan')}):
            with self.assertRaises(ValueError):
                ArmActionSettings.from_mapping(config)
        raw = ClientFixture(HandleFixture(done(terminal(6, 1, 2, error_code='ARM_ERROR', error_message='motor'))))
        result = client(raw).execute(goal(), lambda: None, lambda *_: None)
        self.assertEqual((result['result_code'], result['error_code']), ('FAILED', 'ARM_ERROR'))

    def test_server_stop_unconfirmed_is_not_cleared_as_safe_terminal(self) -> None:
        raw = ClientFixture(HandleFixture(done(terminal(6, 1, 0, error_code='CANCEL_UNCONFIRMED'))))
        arm = client(raw)
        with self.assertRaises(ArmExecutionError) as caught:
            arm.execute(goal(), lambda: None, lambda *_: None)
        self.assertEqual(caught.exception.code, 'CANCEL_UNCONFIRMED')
        with self.assertRaises(ArmExecutionError):
            arm.cancel()
        self.assertTrue(arm.has_goal)


@dataclass
class Arrival:
    stamp_ns: int = 123


class MissionBridgeTests(unittest.TestCase):
    def test_arm_requested_after_arrival_and_no_arm_in_legacy(self) -> None:
        for enabled in (False, True):
            events = []
            def navigate(*_) -> Arrival:
                events.append('arrived_stopped')
                return Arrival()
            def execute(*_) -> dict:
                events.append('arm')
                return dict(result_code='SUCCESS', harvested_count=2, failed_count=1)
            node = NS(check=lambda: None, navigator=NS(preflight_navigation=lambda: None,
                navigate=navigate, cancel_nav=lambda: events.append('nav_cancel')), blocked=False,
                arm_client=NS(execute=execute, has_goal=False) if enabled else None,
                communication=NS(arm_feedback=lambda *_: None))
            self.assertEqual(HarvestMission(node, goal()).run(), {'stamp_ns': 123})
            self.assertEqual(events, ['arrived_stopped', 'arm'] if enabled else ['arrived_stopped'])

    def test_arm_cancel_failure_blocks_and_still_cleans_navigation(self) -> None:
        events = []
        def execute(*_) -> None:
            raise MissionCanceled('cancel')
        def cancel() -> None:
            events.append('arm_cancel')
            raise RuntimeError('terminal missing')
        node = NS(check=lambda: None, navigator=NS(preflight_navigation=lambda: None,
            navigate=lambda *_: Arrival(), cancel_nav=lambda: events.append('nav_cancel')),
            blocked=False, arm_client=NS(execute=execute, cancel=cancel, has_goal=True),
            communication=NS(arm_feedback=lambda *_: None))
        with self.assertRaisesRegex(RuntimeError, 'CANCEL_UNCONFIRMED'):
            HarvestMission(node, goal()).run()
        self.assertTrue(node.blocked)
        self.assertEqual(events, ['arm_cancel', 'nav_cancel'])


class CommunicationForwardTests(unittest.TestCase):
    def test_real_counts_survive_success_failure_cancel_and_unconfirmed_stop(self) -> None:
        def module(name: str, **values: object) -> ModuleType:
            value = ModuleType(name)
            value.__dict__.update(values)
            return value
        mocks = {'rclpy': module('rclpy'),
            'rclpy.action': module('rclpy.action', ActionServer=lambda *_a, **_k: None,
                GoalResponse=NS(ACCEPT=1, REJECT=2), CancelResponse=NS(ACCEPT=1)),
            'farm_interfaces': module('farm_interfaces'),
            'farm_interfaces.action': module('farm_interfaces.action', HarvestTask=NS(Feedback=NS, Result=NS))}
        with patch.dict(sys.modules, mocks):
            sys.modules.pop('harvest_robot.communication', None)
            communication_module = importlib.import_module('harvest_robot.communication')
            try:
                for mode in ('success', 'failed', 'canceled', 'unconfirmed'):
                    with self.subTest(mode=mode):
                        messages, statuses, records = [], [], []
                        handle = NS(request=goal(), is_cancel_requested=mode in ('canceled', 'unconfirmed'),
                            publish_feedback=messages.append, succeed=lambda: statuses.append('success'),
                            canceled=lambda: statuses.append('canceled'), abort=lambda: statuses.append('aborted'))
                        node = NS(callbacks=None, lock=threading.Lock(), busy=True, blocked=False, stopping=False,
                            completed_ids=set(), mode='sim', check=lambda: None, emit_record=records.append,
                            config={'completion_policy': 'ARRIVAL_THEN_ARM'},
                            get_logger=lambda: NS(error=lambda _message: None))
                        communication = communication_module.HarvestCommunication(node)
                        def run() -> dict:
                            node.arrival_result = {'stamp_ns': 123}
                            node.mission_stage = 'ARM'
                            communication.arm_feedback(1, 0)
                            if mode == 'canceled':
                                raise MissionCanceled('cancel after one harvest')
                            if mode == 'unconfirmed':
                                node.blocked = True
                                raise RuntimeError('stop unconfirmed')
                            communication.arm_feedback(2, 1)
                            node.arm_result = dict(result_code='SUCCESS' if mode == 'success' else 'FAILED',
                                harvested_count=2, failed_count=1,
                                error_code='NONE' if mode == 'success' else 'ARM_ERROR', error_message='')
                            return node.arrival_result
                        with patch.object(communication_module, 'HarvestMission', lambda *_: NS(run=run)):
                            result = communication.execute(handle)
                        expected = {'success': ('success', 'SUCCESS', 2, 1),
                            'failed': ('aborted', 'FAILED', 2, 1), 'canceled': ('canceled', 'CANCELED', 1, 0),
                            'unconfirmed': ('aborted', 'FAILED', 1, 0)}[mode]
                        self.assertEqual((statuses[-1], result.result_code, result.harvested_count, result.failed_count), expected)
                        self.assertEqual(result.expected_count, 9)
                        self.assertTrue(any(message.success_count == 1 for message in messages))
                        self.assertEqual(records[0]['arrival']['stamp_ns'], 123)
                        if mode == 'unconfirmed':
                            self.assertEqual(result.error_code, 'CANCEL_UNCONFIRMED')
                        self.assertFalse(node.busy)
            finally:
                sys.modules.pop('harvest_robot.communication', None)


if __name__ == '__main__':
    unittest.main()
