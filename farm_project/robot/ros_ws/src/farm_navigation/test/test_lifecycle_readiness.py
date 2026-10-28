import unittest
from unittest.mock import Mock, patch
from types import SimpleNamespace
from farm_navigation.nav2_client import Nav2Client


def future(state):
    f = Mock()
    f.done.return_value = True
    f.exception.return_value = None
    f.result.return_value = SimpleNamespace(current_state=SimpleNamespace(id=state))
    return f


class ReadinessTests(unittest.TestCase):
    def client(self, states):
        c = Nav2Client.__new__(Nav2Client)
        c._node = Mock()
        service = Mock()
        service.service_is_ready.return_value = True
        service.call_async.side_effect = [future(s) for s in states]
        c._lifecycle_clients = [service]
        return c, service

    @patch('farm_navigation.nav2_client.time.sleep')
    def test_inactive_waits_then_active_returns(self, sleep):
        c, service = self.client([2, 3])
        c._wait_active_nav2(lambda: None)
        self.assertEqual(service.call_async.call_count, 2)
        c._node.get_logger().warning.assert_called_once()

    def test_disabled_is_noop(self):
        c = Nav2Client.__new__(Nav2Client)
        c._wait_active_nav2(Mock())

    def test_cancel_still_interrupts(self):
        c, service = self.client([2])
        def cancel():
            raise RuntimeError('cancelled')
        with self.assertRaisesRegex(RuntimeError, 'cancelled'):
            c._wait_active_nav2(cancel)
        service.call_async.assert_not_called()

    @patch('farm_navigation.nav2_client.time.sleep')
    def test_all_nodes_must_be_active(self, sleep):
        c, first = self.client([3, 3])
        second = Mock()
        second.service_is_ready.return_value = True
        second.call_async.side_effect = [future(2), future(3)]
        c._lifecycle_clients.append(second)
        c._wait_active_nav2(lambda: None)
        self.assertEqual(first.call_async.call_count, 2)
