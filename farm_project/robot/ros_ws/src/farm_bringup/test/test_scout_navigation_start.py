import unittest
from unittest.mock import Mock, patch
from farm_bringup.scout_navigation_start import NavigationStart
from nav2_msgs.srv import ManageLifecycleNodes

class StartupTests(unittest.TestCase):
    @patch('farm_bringup.scout_navigation_start.rclpy.spin_once')
    @patch('farm_bringup.scout_navigation_start.rclpy.ok', return_value=True)
    def test_waits_for_tf_before_start(self, ok, spin):
        node = Mock()
        node.manager.service_is_ready.return_value = True
        node.ready.side_effect = [False, False, True]
        node.command.return_value = True
        NavigationStart.run(node)
        node.command.assert_called_once_with(ManageLifecycleNodes.Request.STARTUP)
        self.assertEqual(node.ready.call_count, 3)

    @patch('farm_bringup.scout_navigation_start.time.monotonic', side_effect=range(0, 1000, 10))
    @patch('farm_bringup.scout_navigation_start.rclpy.spin_once')
    @patch('farm_bringup.scout_navigation_start.rclpy.ok', return_value=True)
    def test_failed_start_resets_before_retry(self, ok, spin, clock):
        node = Mock()
        node.manager.service_is_ready.return_value = True
        node.ready.return_value = True
        node.command.side_effect = [False, True, True]
        NavigationStart.run(node)
        self.assertEqual([c.args[0] for c in node.command.call_args_list], [
            ManageLifecycleNodes.Request.STARTUP, ManageLifecycleNodes.Request.RESET,
            ManageLifecycleNodes.Request.STARTUP])
