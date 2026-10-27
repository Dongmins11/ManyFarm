"""명시적 PC 검증 전용. 격리 domain231/loopback과 시험 토픽만 사용하는 실제 ROS 왕복.

MANYFARM_JETSON_ROS_TEST=1일 때만 실행한다. Action/서비스/속도 명령은 생성하지 않는다.
"""
import os
from pathlib import Path
import sys
import time
import threading
from collections.abc import Callable
from types import SimpleNamespace as S
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


@unittest.skipUnless(os.environ.get('MANYFARM_JETSON_ROS_TEST') == '1', '명시적인 격리 ROS 시험만 실행')
class JetsonRosTests(unittest.TestCase):
    def setUp(self) -> None:
        if (os.environ.get('ROS_DOMAIN_ID') != '231'
                or os.environ.get('ROS_AUTOMATIC_DISCOVERY_RANGE') != 'LOCALHOST'
                or '127.0.0.1' not in os.environ.get('CYCLONEDDS_URI', '')):
            raise RuntimeError('시험 domain231/LOCALHOST/loopback 환경이 필요합니다.')
        import rclpy
        from rclpy.executors import SingleThreadedExecutor
        from rclpy.node import Node
        from rclpy.qos import QoSProfile, ReliabilityPolicy, DurabilityPolicy
        from std_srvs.srv import SetBool
        from nav_msgs.msg import Odometry
        from jetson_harvest_interfaces.msg import RuntimeStatus, ControlState
        from harvest_robot.jetson_connection import JetsonConnection
        from harvest_robot.jetson_state import JetsonSettings
        self.rclpy, self.Odometry, self.RuntimeStatus = rclpy, Odometry, RuntimeStatus
        rclpy.init()
        self.node = Node('jetson_link_test', namespace='/test_only_jetson')
        self.node.config = {'robot_id': 'test_robot'}
        self.node.lock = threading.Lock()
        self.node.active_goal = None
        self.node.busy = self.node.blocked = self.node.stopping = False
        self.node.handoff = S(current=None, busy=False)
        self.node.client = S(has_goal=False)
        self.node.transfer = None
        self.node.arm_client = S(settings=S(readiness_timeout_s=.1))
        self.node.check = lambda: None
        self.navigation = S(odom_topic='/test_only_jetson/odom', base_frame='base_test',
            odom_max_age_s=.3, settle_s=.1, stopped_linear_mps=.005, stopped_angular_rps=.02)
        self.settings = JetsonSettings('/test_only_jetson/control', '/test_only_jetson/status',
            runtime_mode='test_hardware',
            runtime_status_timeout_s=.3)
        self.connection = JetsonConnection(self.node, self.navigation, self.settings)
        self.SetBool = SetBool
        self.test_client = self.node.create_client(SetBool, '/test_robot/transfer_test_mode/set_enabled')
        self.velocity = 0.
        qos = QoSProfile(depth=1, reliability=ReliabilityPolicy.RELIABLE, durability=DurabilityPolicy.VOLATILE)
        self.odom = self.node.create_publisher(Odometry, self.navigation.odom_topic, qos)
        self.status = self.node.create_publisher(RuntimeStatus, self.settings.runtime_status_topic, qos)
        self.messages = []
        self.node.create_subscription(ControlState, self.settings.control_state_topic, self.messages.append, qos)
        self.executor = SingleThreadedExecutor()
        self.executor.add_node(self.node)
        self.sequence = 0
        self.boot = 'jetson_test_boot'
        self.ready = True

    def tearDown(self) -> None:
        self.connection.close()
        self.executor.shutdown()
        self.node.destroy_node()
        self.rclpy.shutdown()

    def pump(self, seconds: float = .5, publish: bool = True) -> None:
        end = time.monotonic()+seconds
        while time.monotonic() < end:
            if publish:
                stamp = self.node.get_clock().now().to_msg()
                odom = self.Odometry()
                odom.header.stamp, odom.header.frame_id, odom.child_frame_id = stamp, 'odom', 'base_test'
                odom.twist.twist.linear.x = self.velocity
                self.odom.publish(odom)
                self.sequence += 1
                status = self.RuntimeStatus(robot_id='test_robot', boot_id=self.boot,
                    sequence=self.sequence, stamp=stamp, mode='test_hardware', ready=self.ready,
                    device_state_valid=True, arm_stowed=self.ready, arm_stopped=self.ready,
                    box_stopped=True, box_state='CLOSED', recovery_required=False, error_code='NONE')
                self.status.publish(status)
            self.executor.spin_once(timeout_sec=.005)
            time.sleep(.005)

    def wait_for(self, predicate: Callable[[], bool], timeout_s: float = 1.5) -> None:
        """타이머 발행·DDS 수신까지 기다린다. 고정 sleep으로 콜백 완료를 가정하지 않는다."""
        deadline = time.monotonic()+timeout_s
        while not predicate() and time.monotonic() < deadline:
            self.executor.spin_once(timeout_sec=.01)
        self.assertTrue(predicate(), '제한시간 내 상태 메시지 수신 실패')

    def toggle_test(self, enabled: bool) -> object:
        """실물과 격리한 시험 서비스에 요청한다."""
        self.assertTrue(self.test_client.wait_for_service(timeout_sec=1.))
        future = self.test_client.call_async(self.SetBool.Request(data=enabled))
        self.wait_for(future.done)
        return future.result()

    def test_transfer_test_changes_only_transfer_and_keeps_measured_stop(self) -> None:
        self.pump()
        self.assertFalse(self.messages[-1].transfer_active)
        self.assertTrue(self.toggle_test(True).success)
        self.pump(.2)
        self.assertTrue(self.messages[-1].transfer_active)
        self.assertTrue(self.messages[-1].base_stopped)
        self.assertEqual(self.node.count_publishers(self.settings.control_state_topic), 1)
        self.velocity = .1
        self.pump(.2)
        self.assertTrue(self.messages[-1].transfer_active)
        self.assertFalse(self.messages[-1].base_stopped)
        self.pump(.4, publish=False)
        count = len(self.messages)
        self.pump(.2, publish=False)
        self.assertEqual(len(self.messages), count)
        self.assertTrue(self.toggle_test(False).success)
        self.velocity = 0.
        self.pump(.3)
        self.assertFalse(self.messages[-1].transfer_active)
        self.assertTrue(self.messages[-1].base_stopped)

    def test_real_work_disables_override_without_altering_operational_state(self) -> None:
        self.pump()
        self.assertTrue(self.toggle_test(True).success)
        self.node.busy = True
        self.node.client.has_goal = True
        self.pump(.2)
        self.assertFalse(self.connection._test_enabled)
        self.assertFalse(self.messages[-1].transfer_active)
        self.assertFalse(self.toggle_test(True).success)
        self.assertTrue(self.node.busy)
        self.assertTrue(self.node.client.has_goal)
        self.node.client.has_goal = False
        self.node.transfer = S(snapshot=lambda:dict(task_id='real-transfer',phase='TRANSFERRING'))
        self.pump(.2)
        self.assertFalse(self.toggle_test(True).success)
        self.assertTrue(self.toggle_test(False).success)
        self.pump(.2)
        self.assertTrue(self.messages[-1].transfer_active)
        self.assertTrue(self.messages[-1].base_stopped)

    def test_wire_control_motion_and_transfer_state(self) -> None:
        self.pump()
        self.assertTrue(self.messages)
        self.connection.wait_before_send(lambda: None, .1)
        self.assertTrue(self.messages[-1].base_stopped)
        self.assertEqual(set(self.messages[-1].get_fields_and_field_types()),
            {'stamp', 'robot_id', 'boot_id', 'sequence', 'base_stopped', 'transfer_active'})
        self.assertFalse(self.connection.snapshot()['stale'])
        sequences = [m.sequence for m in self.messages]
        self.assertEqual(sequences, sorted(set(sequences)))
        self.assertEqual(len({m.boot_id for m in self.messages}), 1)
        self.node.client.has_goal = True
        self.pump(.2)
        self.assertFalse(self.messages[-1].base_stopped)
        self.node.client.has_goal = False
        self.node.transfer = S(snapshot=lambda: dict(task_id='transfer_test', phase='TRANSFERRING'),
                               cancel_requested=False, active=None)
        self.node.busy = True
        self.ready = False
        self.pump(.2)
        self.assertTrue(self.messages[-1].transfer_active)
        self.assertTrue(self.messages[-1].base_stopped)
        self.assertFalse(self.connection.snapshot()['status']['ready'])
        self.assertFalse(self.connection.snapshot()['stale'])

    def test_wire_other_task_is_observed_without_rejection(self) -> None:
        self.pump()
        self.node.active_goal = S(request=S(harvest_task=S(task_id='expected_task', window_id='expected_window')))
        self.node.mission_stage = 'ARM'
        self.node.busy = True
        self.ready = False
        status = self.RuntimeStatus(robot_id='test_robot', boot_id=self.boot,
            sequence=self.sequence+1, stamp=self.node.get_clock().now().to_msg(), mode='test_hardware',
            ready=False, device_state_valid=True, arm_stowed=False, arm_stopped=False,
            box_stopped=True, box_state='CLOSED', error_code='NONE', task_id='other_task')
        self.status.publish(status)
        self.pump(.1, publish=False)
        self.assertEqual(self.connection.snapshot()['status']['task_id'], 'other_task')

    def test_wire_timeout_and_active_restart(self) -> None:
        self.pump()
        self.pump(.4, publish=False)
        count = len(self.messages)
        self.pump(.3, publish=False)
        self.assertEqual(len(self.messages), count)
        self.wait_for(lambda: self.connection.snapshot()['stale'])
        self.pump(.4)
        self.assertGreater(len(self.messages), count)
        self.node.busy = True
        self.boot = 'jetson_restarted'
        self.pump(.2)
        self.assertEqual(self.connection.snapshot()['status']['boot_id'], 'jetson_restarted')
        self.assertFalse(self.connection.snapshot()['stale'])


if __name__ == '__main__':
    unittest.main()
