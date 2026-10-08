"""ROS 없이 활동 lease·세션 격리와 실제 어댑터 전달 메서드를 검사합니다."""
import ast
from copy import deepcopy
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'sim/ros_ws/src/farm_sim_devices'))
from farm_sim_devices.harvest_activity import ActivityGate
from farm_sim_devices.wire import CommandGate


def request(**changes: object) -> dict:
    """같은 PC의 monotonic 시각 10초에 보낸 명시적인 활동 요청입니다."""
    return dict(dict(kind='harvest_activity', session='session-a', robot_id='harvest_01',
                     seq=1, sent=10., active=True), **changes)


class ActivityGateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.gate = ActivityGate('session-a', 'harvest_01', 2.)

    def test_default_inactive_and_expiry_uses_send_time(self) -> None:
        self.assertFalse(self.gate.value(10.))
        self.assertTrue(self.gate.accept(request(), now=11.5))
        self.assertTrue(self.gate.value(12.))
        self.assertFalse(self.gate.value(12.000001))
        self.assertFalse(self.gate.value(9.9))

    def test_explicit_false_stops_and_older_true_cannot_reactivate(self) -> None:
        self.assertTrue(self.gate.accept(request(), now=10.))
        self.assertTrue(self.gate.accept(request(seq=2, sent=10.5, active=False), now=10.5))
        self.assertFalse(self.gate.value(10.5))
        self.assertFalse(self.gate.accept(request(), now=10.6))
        self.assertFalse(self.gate.value(10.6))

    def test_each_fresh_true_renews_only_its_own_lease(self) -> None:
        self.assertTrue(self.gate.accept(request(), now=10.))
        self.assertTrue(self.gate.accept(request(seq=2, sent=11.5), now=11.5))
        self.assertTrue(self.gate.value(13.5))
        self.assertFalse(self.gate.value(13.500001))

    def test_wrong_robot_session_kind_and_missing_fields_are_rejected(self) -> None:
        messages = [request(robot_id='scout_01'), request(session='old-session'),
                    request(kind='cmd'), None, [], True]
        for key in request():
            message = request()
            del message[key]
            messages.append(message)
        for message in messages:
            with self.subTest(message=message):
                self.assertFalse(self.gate.accept(message, now=10.))
        self.assertFalse(self.gate.value(10.))
        self.assertTrue(self.gate.accept(request(), now=10.))

    def test_sequence_requires_nonnegative_integer_and_strict_increase(self) -> None:
        for sequence in [True, False, '1', 1., -1, None, float('nan')]:
            with self.subTest(sequence=sequence):
                self.assertFalse(self.gate.accept(request(seq=sequence), now=10.))
        self.assertTrue(self.gate.accept(request(seq=5), now=10.))
        for sequence in [4, 5]:
            self.assertFalse(self.gate.accept(request(seq=sequence, active=False), now=10.1))
        self.assertTrue(self.gate.value(10.1))

    def test_active_requires_json_boolean(self) -> None:
        for active in [0, 1, 'true', 'false', None, [], {}]:
            with self.subTest(active=active):
                self.assertFalse(self.gate.accept(request(active=active), now=10.))
        self.assertTrue(self.gate.accept(request(active=False), now=10.))

    def test_time_requires_finite_number_and_not_boolean(self) -> None:
        for value in [True, '10', None, float('nan'), float('inf'), -float('inf'), 10**1000]:
            with self.subTest(value=repr(value)[:30]):
                self.assertFalse(self.gate.accept(request(sent=value), now=10.))
                if value is not None:
                    self.assertFalse(self.gate.accept(request(), now=value))
        self.assertTrue(self.gate.accept(request(), now=10.))
        for value in [True, '10', float('nan'), float('inf')]:
            self.assertFalse(self.gate.value(value))

    def test_stale_or_future_message_does_not_consume_sequence_or_extend_lease(self) -> None:
        self.assertTrue(self.gate.accept(request(), now=10.))
        self.assertFalse(self.gate.accept(request(seq=100, sent=10.), now=12.1))
        self.assertFalse(self.gate.accept(request(seq=100, sent=13.), now=12.1))
        self.assertFalse(self.gate.value(12.1))
        self.assertTrue(self.gate.accept(request(seq=2, sent=12.1), now=12.1))

    def test_new_session_never_replays_previous_activity(self) -> None:
        self.assertTrue(self.gate.accept(request(), now=10.))
        replacement = ActivityGate('session-b', 'harvest_01', 2.)
        self.assertFalse(replacement.value(10.))
        self.assertFalse(replacement.accept(request(seq=2), now=10.))
        self.assertTrue(replacement.accept(request(session='session-b'), now=10.))

    def test_gate_is_independent_of_velocity_commands(self) -> None:
        velocity = CommandGate('session-a', .5)
        command = dict(kind='cmd', session='session-a', seq=100, sent=10., linear=.1, angular=.2)
        self.assertTrue(velocity.accept(command, now=10.))
        self.assertFalse(self.gate.accept(command, now=10.))
        self.assertTrue(self.gate.accept(request(), now=10.))
        self.assertFalse(velocity.accept(request(), now=10.))
        self.assertEqual(velocity.value(10.1), (.1, .2))
        self.assertEqual(velocity.value(10.6), (0., 0.))
        self.assertTrue(self.gate.value(10.6))
        self.assertFalse(self.gate.value(12.1))

    def test_implicit_clock_uses_monotonic_seconds(self) -> None:
        with patch('farm_sim_devices.harvest_activity.time.monotonic', return_value=10.):
            self.assertTrue(self.gate.accept(request()))
            self.assertTrue(self.gate.value())
        with patch('farm_sim_devices.harvest_activity.time.monotonic', return_value=12.1):
            self.assertFalse(self.gate.value())

    def test_invalid_gate_configuration_is_rejected(self) -> None:
        for session, robot, lease in [('', 'harvest_01', 2.), ('session', '', 2.),
                (None, 'harvest_01', 2.), ('session', 1, 2.), ('session', 'harvest_01', 0),
                ('session', 'harvest_01', -1), ('session', 'harvest_01', True),
                ('session', 'harvest_01', '2'), ('session', 'harvest_01', float('nan'))]:
            with self.subTest(session=session, robot=robot, lease=lease), self.assertRaises(ValueError):
                ActivityGate(session, robot, lease)


class AdapterActivityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        """운영 어댑터의 콜백만 AST로 읽어 ROS 설치 없는 환경에서도 동일 코드를 검사합니다."""
        source = ROOT / 'sim/ros_ws/src/farm_sim_devices/farm_sim_devices/ros_adapter.py'
        module = ast.parse(source.read_text())
        adapter = next(node for node in module.body if isinstance(node, ast.ClassDef) and node.name == 'SimRosAdapter')
        callback = next(node for node in adapter.body if isinstance(node, ast.FunctionDef) and node.name == 'harvest_activity')
        cls.clock = SimpleNamespace(monotonic=lambda: 10., monotonic_ns=lambda: 10_000_000_000)
        namespace = dict(Bool=object, time=cls.clock)
        exec(compile(ast.Module(body=[callback], type_ignores=[]), str(source), 'exec'), namespace)
        cls.callback = staticmethod(namespace['harvest_activity'])

    def setUp(self) -> None:
        self.messages = []
        self.adapter = SimpleNamespace(harvest_activity_enabled=True, session='session-a', last_seen=9.9,
            config=dict(robot_id='harvest_01', runtime=dict(transport_timeout_s=2.)),
            transport=SimpleNamespace(send=self.messages.append))

    def test_receipt_sends_one_explicit_activity_with_current_robot_and_session(self) -> None:
        self.callback(self.adapter, SimpleNamespace(data=True))
        self.assertEqual(self.messages, [dict(kind='harvest_activity', session='session-a',
            seq=10_000_000_000, sent=10., robot_id='harvest_01', active=True)])
        self.adapter.session = 'session-b'
        self.assertEqual(len(self.messages), 1)
        self.callback(self.adapter, SimpleNamespace(data=False))
        self.assertEqual(len(self.messages), 2)
        self.assertEqual(self.messages[-1]['session'], 'session-b')
        self.assertIs(self.messages[-1]['active'], False)

    def test_disabled_disconnected_stale_or_invalid_request_is_ignored(self) -> None:
        cases = [dict(harvest_activity_enabled=False), dict(session=None), dict(last_seen=7.9),
                 dict(last_seen=10.1)]
        for changes in cases:
            with self.subTest(changes=changes):
                adapter = deepcopy(self.adapter)
                adapter.transport = self.adapter.transport
                for key, value in changes.items():
                    setattr(adapter, key, value)
                self.callback(adapter, SimpleNamespace(data=True))
        self.callback(self.adapter, SimpleNamespace(data=1))
        self.assertEqual(self.messages, [])


if __name__ == '__main__':
    unittest.main()
