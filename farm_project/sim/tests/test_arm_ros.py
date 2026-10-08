"""ROS/Isaac 없이 실제 서버 루프의 유실 복구·수량·취소 확인을 검사합니다."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import sys
import threading
import time
from types import ModuleType, SimpleNamespace as NS
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'sim/ros_ws/src/farm_sim_devices'))
from farm_sim_devices.arm_ros import ArmRosServer, ArmRosSettings, goal_fields, valid_status


def module(name: str, **members: object) -> ModuleType:
    value = ModuleType(name)
    value.__dict__.update(members)
    return value


def goal() -> NS:
    return NS(robot_id='harvest_01', map_id='farm', timestamp='now', harvest_task=NS(
        task_id='task', window_id='window', expected_count=9,
        goal_pose=NS(frame_id='map', position=NS(x=1., y=2., z=0.), yaw=.3)))


class Handle:
    def __init__(self) -> None:
        self.request, self.goal_id = goal(), NS(uuid=list(range(16)))
        self.is_cancel_requested, self.feedbacks, self.status = False, [], None

    def publish_feedback(self, value: NS) -> None:
        self.feedbacks.append((value.success_count, value.failed_count))

    def succeed(self) -> None:
        self.status = 'SUCCESS'

    def abort(self) -> None:
        self.status = 'FAILED'

    def canceled(self) -> None:
        self.status = 'CANCELED'


class ArmRosTests(unittest.TestCase):
    def setUp(self) -> None:
        self.sent, self.hook = [], lambda _: None
        self.node = NS(session='session', last_seen=time.monotonic(),
            config=dict(robot_id='harvest_01', map_id='farm', runtime=dict(transport_timeout_s=5.)),
            transport=NS(send=self.send), get_logger=lambda: NS(warning=lambda _: None))
        fake = NS(Feedback=NS, Result=NS)
        modules = {'rclpy':module('rclpy'), 'rclpy.action':module('rclpy.action',
            ActionServer=lambda *a, **k: NS(destroy=lambda: None),
            GoalResponse=NS(ACCEPT=True, REJECT=False), CancelResponse=NS(ACCEPT=True)),
            'rclpy.callback_groups':module('rclpy.callback_groups', ReentrantCallbackGroup=lambda: object()),
            'farm_interfaces':module('farm_interfaces'),
            'farm_interfaces.action':module('farm_interfaces.action', HarvestTask=fake)}
        with patch.dict(sys.modules, modules):
            self.server = ArmRosServer(self.node, dict(start_retry_s=.01, keepalive_hz=100.,
                status_timeout_s=.08, cancel_timeout_s=.06, execution_timeout_s=.3))
        self.handle = Handle()

    def send(self, message: dict) -> None:
        self.sent.append(message)
        self.hook(message)

    def state(self, status: str = 'RUNNING', counts: tuple[int, int] = (0, 0), **changes: object) -> dict:
        return dict(dict(job_id=bytes(self.handle.goal_id.uuid).hex(), status=status, stage='POLICY',
            success_count=counts[0], failed_count=counts[1], event_seq=sum(counts),
            error_code='', error_message='', safe_stopped=status != 'RUNNING'), **changes)

    def observe(self, status: str = 'RUNNING', counts: tuple[int, int] = (0, 0), **changes: object) -> None:
        self.server.observe('session', self.state(status, counts, **changes))

    def test_lost_start_retransmits_and_mixed_counts_keep_original_identity(self) -> None:
        starts = 0
        def peer(message: dict) -> None:
            nonlocal starts
            if message['op'] == 'start':
                starts += 1
                if starts == 2:
                    self.observe(counts=(1, 0))
            elif message['op'] == 'keepalive':
                self.observe('SUCCESS', (2, 1))
        self.hook = peer
        self.assertTrue(self.server.accept(self.handle.request))
        self.assertFalse(self.server.accept(goal()))
        result = self.server.execute(self.handle)
        self.assertEqual(starts, 2)
        self.assertEqual((result.result_code, self.handle.status), ('SUCCESS', 'SUCCESS'))
        self.assertEqual((result.expected_count, result.harvested_count, result.failed_count), (9, 2, 1))
        self.assertEqual((result.robot_id, result.task_id, result.window_id), ('harvest_01', 'task', 'window'))
        self.assertEqual(self.handle.feedbacks, [(0, 0), (1, 0), (2, 1)])
        self.assertEqual(self.sent[0]['goal_pose'], dict(x=1., y=2., yaw=.3))
        self.assertTrue(all(a['seq'] < b['seq'] for a, b in zip(self.sent, self.sent[1:])))
        self.assertEqual(self.sent[-1]['op'], 'ack')
        self.observe('SUCCESS', (2, 1))
        self.assertEqual([m['op'] for m in self.sent[-2:]], ['ack', 'ack'])

    def test_cancel_waits_stopped_terminal_and_preserves_counts(self) -> None:
        started = threading.Event()
        cancels = 0
        def peer(message: dict) -> None:
            nonlocal cancels
            if message['op'] == 'start':
                self.observe(counts=(1, 2)); started.set()
            if message['op'] == 'cancel':
                cancels += 1
                if cancels == 2:
                    self.observe('CANCELED', (1, 2))
        self.hook = peer
        self.server.accept(self.handle.request)
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(self.server.execute, self.handle)
            self.assertTrue(started.wait(1.))
            self.handle.is_cancel_requested = True
            self.assertTrue(self.server.cancel(self.handle))
            result = future.result(timeout=2.)
        self.assertEqual(cancels, 2)
        self.assertEqual(result.result_code, 'CANCELED')
        self.assertEqual((result.harvested_count, result.failed_count), (1, 2))

    def test_no_status_then_no_stop_confirmation_blocks_new_goals(self) -> None:
        self.server.accept(self.handle.request)
        result = self.server.execute(self.handle)
        self.assertEqual((result.result_code, result.error_code), ('FAILED', 'CANCEL_UNCONFIRMED'))
        self.assertIn('cancel', [m['op'] for m in self.sent])
        self.assertFalse(self.server.accept(goal()))

    def test_new_session_cannot_confirm_old_job(self) -> None:
        def peer(message: dict) -> None:
            if message['op'] == 'start':
                self.observe(counts=(1, 0))
                self.node.session = 'replacement'
                self.server.observe('replacement', self.state('SUCCESS', (50, 0)))
        self.hook = peer
        self.server.accept(self.handle.request)
        result = self.server.execute(self.handle)
        self.assertEqual(result.error_code, 'CANCEL_UNCONFIRMED')
        self.assertEqual(result.harvested_count, 1)
        self.assertTrue(all(m['session'] == 'session' for m in self.sent))

    def test_counter_regression_requests_cancel_and_reports_protocol_failure(self) -> None:
        def peer(message: dict) -> None:
            if message['op'] == 'start':
                self.observe(counts=(2, 0))
                self.observe(counts=(1, 0), event_seq=3)
            elif message['op'] == 'cancel':
                self.observe('CANCELED', (2, 0), event_seq=4)
        self.hook = peer
        self.server.accept(self.handle.request)
        result = self.server.execute(self.handle)
        self.assertEqual((result.result_code, result.error_code), ('FAILED', 'ARM_PROTOCOL_ERROR'))
        self.assertEqual(result.harvested_count, 2)

    def test_unsafe_terminal_immediately_fails_and_blocks(self) -> None:
        self.hook = lambda message: self.observe('FAILED', (1, 1), safe_stopped=False,
            error_code='CANCEL_UNCONFIRMED', error_message='cannot stop') if message['op'] == 'start' else None
        self.server.accept(self.handle.request)
        result = self.server.execute(self.handle)
        self.assertEqual((result.result_code, result.error_code), ('FAILED', 'CANCEL_UNCONFIRMED'))
        self.assertFalse(self.server.accept(goal()))
        self.assertEqual(result.failed_count, 1)

    def test_terminal_success_cannot_erase_prior_protocol_failure(self) -> None:
        def peer(message: dict) -> None:
            if message['op'] == 'start':
                self.observe(counts=(2, 0))
                self.observe(counts=(1, 0), event_seq=3)
                self.observe('SUCCESS', (2, 0), event_seq=4)
        self.hook = peer
        self.server.accept(self.handle.request)
        result = self.server.execute(self.handle)
        self.assertEqual((result.result_code, result.error_code), ('FAILED', 'ARM_PROTOCOL_ERROR'))
        self.assertEqual(result.harvested_count, 2)

    def test_transport_errors_never_return_success(self) -> None:
        def peer(message: dict) -> None:
            if message['op'] == 'start':
                self.observe('SUCCESS')
            elif message['op'] == 'ack':
                raise OSError('closed')
        self.hook = peer
        self.server.accept(self.handle.request)
        result = self.server.execute(self.handle)
        self.assertEqual((result.result_code, result.error_code), ('FAILED', 'CANCEL_UNCONFIRMED'))

    def test_invalid_goal_settings_status_and_stale_link_rejected(self) -> None:
        for changes in ({'endpoint':''}, {'keepalive_hz':0}, {'cancel_timeout_s':float('nan')}):
            with self.assertRaises(ValueError):
                ArmRosSettings.from_mapping(changes)
        invalid = goal(); invalid.harvest_task.goal_pose.frame_id = 'odom'
        with self.assertRaises(ValueError):
            goal_fields(invalid, self.node.config)
        self.assertFalse(self.server.accept(invalid))
        for changes in ({'success_count':-1}, {'failed_count':True}, {'safe_stopped':1}, {'status':'IDLE'}):
            self.assertFalse(valid_status(self.state(**changes)))
        self.node.last_seen -= 10.
        self.assertFalse(self.server.accept(goal()))


if __name__ == '__main__':
    unittest.main()
