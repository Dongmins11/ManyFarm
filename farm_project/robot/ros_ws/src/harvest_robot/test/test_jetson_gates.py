"""회신의 최소 준비 확인이 도착 후 Goal 직전에만 적용되는지 검증한다."""
from concurrent.futures import Future
from dataclasses import dataclass, replace
from pathlib import Path
import sys
import threading
import time
from types import SimpleNamespace as S
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from harvest_robot.mission import HarvestMission
from harvest_robot.arm_client import ArmActionClient, ArmActionSettings, ArmExecutionError
from harvest_robot.jetson_connection import JetsonConnection
from harvest_robot.jetson_state import JetsonSettings, RuntimeSample, RuntimeTracker

@dataclass
class Arrival:
    arrived: bool = True

def done(value: object) -> Future:
    future = Future()
    future.set_result(value)
    return future

class ReplyGateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.calls = []
        self.connection = JetsonConnection.__new__(JetsonConnection)
        self.connection._lock = threading.RLock()
        self.connection._runtime = RuntimeTracker('test_robot', JetsonSettings('/test/control', '/test/status'))
        self.connection._now = lambda: (time.time_ns(), time.monotonic())
        self.sample = RuntimeSample('test_robot', 'boot_a', 1, time.time_ns(), 'depth_v11',
            True, False, False, False, False, 'UNKNOWN', False, 'NONE')
        self.goal = S(robot_id='test_robot', harvest_task=S(task_id='task', window_id='window',
            expected_count=2, goal_pose=S(position=S(x=0., y=0.), yaw=0.)))

    def receive(self, **changes: object) -> None:
        with self.connection._lock:
            self.connection._runtime.receive(replace(self.sample, stamp_ns=time.time_ns(), **changes), time.monotonic())

    def client(self) -> ArmActionClient:
        def server_ready() -> bool:
            self.calls.append('server')
            return True
        def send(goal: object, **kwargs: object) -> Future:
            self.calls.append('send')
            # 실행 중 ready=false는 정상: 이후 기존 Action 결과 처리만 수행해야 한다.
            self.receive(sequence=2, ready=False)
            result = S(robot_id='test_robot', task_id='task', window_id='window', expected_count=2,
                result_code='SUCCESS', harvested_count=1, failed_count=1, error_code='NONE', error_message='')
            return done(S(accepted=True, get_result_async=lambda: done(S(status=4, result=result))))
        return ArmActionClient(None, ArmActionSettings('/test/arm', readiness_timeout_s=.03),
                               client=S(server_is_ready=server_ready, send_goal_async=send))

    def test_arrival_then_server_then_gate_then_goal_and_busy_ready_false(self) -> None:
        arm = self.client()
        def gate(check: object, timeout: float) -> None:
            self.calls.append('gate')
            self.connection.wait_before_send(check, timeout)
        self.receive()
        node = S(check=lambda: None, jetson_connection=S(wait_before_send=gate),
            navigator=S(preflight_navigation=lambda: None,
                        navigate=lambda *_: self.calls.append('arrival') or Arrival()),
            arm_client=arm, communication=S(arm_feedback=lambda *_: None))
        HarvestMission(node, self.goal).run()
        self.assertEqual(self.calls, ['arrival', 'server', 'gate', 'send'])
        self.assertEqual(node.arm_result['failed_count'], 1)
        self.assertTrue(node.arm_travel_ready)

    def test_unready_rejects_only_after_navigation_and_sends_no_goal(self) -> None:
        arm = self.client()
        self.receive(ready=False)
        node = S(check=lambda: None, jetson_connection=self.connection,
            navigator=S(preflight_navigation=lambda: None,
                navigate=lambda *_: self.calls.append('arrival') or Arrival(),
                cancel_nav=lambda: self.calls.append('existing_cleanup')),
            arm_client=arm, communication=S(arm_feedback=lambda *_: None))
        with self.assertRaises(ArmExecutionError):
            HarvestMission(node, self.goal).run()
        self.assertEqual(self.calls, ['arrival', 'server', 'existing_cleanup'])
        self.assertFalse(arm.has_goal)

    def test_wait_can_receive_ready_without_auto_request(self) -> None:
        checks = []
        def check() -> None:
            checks.append(True)
            if len(checks) == 2:
                self.receive()
        self.connection.wait_before_send(check, .1)
        self.assertEqual(len(checks), 2)
        self.assertEqual(self.calls, [])

    def test_existing_cancel_interrupts_preparation(self) -> None:
        def check() -> None:
            raise RuntimeError('existing cancellation')
        with self.assertRaisesRegex(RuntimeError, 'existing cancellation'):
            self.connection.wait_before_send(check, .1)
        self.assertEqual(self.calls, [])
