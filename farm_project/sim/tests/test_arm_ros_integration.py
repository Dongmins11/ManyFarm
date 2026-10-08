"""실제 ROS Action/UDP 시험 장치 연결. Isaac·물리 수확 성공 검증은 아닙니다.

/opt/ros/jazzy 및 robot/ros_ws/install 환경을 source한 시스템 Python으로 실행합니다.
FARM_RUN_ROS_ARM_TESTS=1로 명시한 경우에만 실행하며 고유 namespace를 사용합니다.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import socket
import sys
import tempfile
import threading
import time
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT/'sim/ros_ws/src/farm_sim_devices'), str(ROOT/'robot/ros_ws/src/harvest_robot')]
try:
    import rclpy
    from rclpy.executors import MultiThreadedExecutor
    from rclpy.node import Node
    from farm_interfaces.action import HarvestTask
    from geometry_msgs.msg import Twist
    from sensor_msgs.msg import JointState
    from farm_sim_devices.ros_adapter import SimRosAdapter
    from farm_sim_devices.wire import LocalDatagrams
    from harvest_robot.arm_client import ArmActionClient, ArmActionSettings
    ROS_AVAILABLE = True
except ImportError:
    ROS_AVAILABLE = False


def free_ports() -> tuple[int, int]:
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as a, socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as b:
        a.bind(('127.0.0.1', 0)); b.bind(('127.0.0.1', 0))
        return a.getsockname()[1], b.getsockname()[1]


@unittest.skipUnless(ROS_AVAILABLE and os.environ.get('FARM_RUN_ROS_ARM_TESTS') == '1',
                     '실제 ROS 시험은 FARM_RUN_ROS_ARM_TESTS=1과 ROS 환경이 필요합니다.')
class ArmRosIntegration(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory(prefix='farm-arm-ros-')
        self.config = json.loads((ROOT/'sim/ros_ws/src/farm_sim_config/config/harvest.json').read_text())
        command_port, telemetry_port = free_ports()
        rt = self.config['runtime']
        rt.update(command_port=command_port, telemetry_port=telemetry_port)
        rt['harvest_arm'] = dict(enabled=True, endpoint='sim/harvest_arm', start_retry_s=.05,
            keepalive_hz=10., status_timeout_s=1., execution_timeout_s=4., cancel_timeout_s=.4)
        self.config['publish_clock'] = False
        path = Path(self.tmp.name)/'devices.json'; path.write_text(json.dumps(self.config))
        namespace = '/arm_bridge_test_'+str(os.getpid())+'_'+str(time.monotonic_ns())
        rclpy.init(args=['--ros-args', '-p', 'config_file:='+str(path), '-r', '__ns:='+namespace])
        self.adapter, self.client_node = SimRosAdapter(), Node('arm_test_client')
        self.client = ArmActionClient(self.client_node, ArmActionSettings('sim/harvest_arm', 5., 3., 5., 2.))
        self.peer = LocalDatagrams(command_port, telemetry_port)
        self.stop = threading.Event()
        self.commands, self.joints = [], []
        self.mode, self.arm, self.first_start, self.started_at, self.cancel_at = 'success', None, True, None, None
        self.publisher = self.client_node.create_publisher(Twist, 'cmd_vel', 10)
        self.subscription = self.client_node.create_subscription(JointState, 'joint_states', self.joints.append, 10)
        self.executor = MultiThreadedExecutor(num_threads=4)
        self.executor.add_node(self.adapter); self.executor.add_node(self.client_node)
        self.spin_thread = threading.Thread(target=self.executor.spin, daemon=True)
        self.peer_thread = threading.Thread(target=self.run_peer, daemon=True)
        self.spin_thread.start(); self.peer_thread.start()
        deadline = time.monotonic()+3.
        while (self.adapter.session is None or not self.joints or not self.publisher.get_subscription_count()) and time.monotonic() < deadline:
            time.sleep(.01)
        self.assertEqual(self.adapter.session, 'ros-fixture')
        self.assertTrue(self.joints)
        self.assertGreater(self.publisher.get_subscription_count(), 0)
        self.initial_joint_count = len(self.joints)

    def tearDown(self) -> None:
        self.adapter.arm_server.request_stop()
        self.executor.shutdown()
        self.stop.set(); self.peer_thread.join(2.); self.spin_thread.join(2.)
        self.client.close(); self.client_node.destroy_node(); self.adapter.close(); self.peer.close()
        rclpy.shutdown(); self.tmp.cleanup()

    def run_peer(self) -> None:
        sequence = 0
        frames = self.config['frames']
        transforms = [dict(parent=frames[a], child=frames[b], translation=[0.,0.,0.], rotation_xyzw=[0.,0.,0.,1.])
            for a,b in [('base_footprint','base_link'), ('base_link','scan')]]
        while not self.stop.wait(.01):
            now = time.monotonic()
            for message in self.peer.receive():
                self.commands.append(message)
                if message['kind'] != 'harvest_arm':
                    continue
                if message['op'] == 'start' and self.arm is None:
                    # 최초 start 한 개를 의도적으로 버려 UDP 재전송을 검증합니다.
                    if self.first_start:
                        self.first_start = False; continue
                    self.started_at = now
                    self.arm = dict(job_id=message['job_id'], status='RUNNING', stage='POLICY',
                        success_count=0, failed_count=0, event_seq=0, error_code='', error_message='', safe_stopped=False)
                elif message['op'] == 'cancel' and self.cancel_at is None:
                    self.cancel_at = now
            if self.arm is not None:
                age = now-self.started_at
                if age > .15:
                    self.arm.update(success_count=1, event_seq=1)
                # ROS 검색 및 실행 스레드 스케줄링 이후에도 중간 누적값을 관측할 시간을 둡니다.
                if self.mode == 'success' and age > 2.:
                    self.arm.update(status='SUCCESS', success_count=2, failed_count=1, event_seq=3, safe_stopped=True)
                elif self.mode == 'cancel' and self.cancel_at is not None and now-self.cancel_at > .15:
                    self.arm.update(status='CANCELED', safe_stopped=True, event_seq=2)
            sequence += 1
            self.peer.send(dict(kind='state', session='ros-fixture', seq=sequence, stamp_ns=sequence*10000000,
                sent=now, odom=[0.,0.,0.,0.,0.], joint_positions=[0.,0.], joint_velocities=[0.,0.],
                scan=None, static_tf=transforms, arm=self.arm))

    def goal(self) -> HarvestTask.Goal:
        request = HarvestTask.Goal()
        request.robot_id, request.map_id = self.config['robot_id'], self.config['map_id']
        request.harvest_task.task_id, request.harvest_task.window_id = 'ros-task', 'ros-window'
        request.harvest_task.expected_count = 9
        request.harvest_task.goal_pose.frame_id = 'map'
        return request

    def check_and_drive(self) -> None:
        command = Twist(); command.linear.x = .07
        self.publisher.publish(command)

    def test_actual_action_success_and_parallel_sensor_velocity_callbacks(self) -> None:
        feedback = []
        result = self.client.execute(self.goal(), self.check_and_drive, lambda a,b: feedback.append((a,b)))
        self.assertEqual((result['result_code'], result['harvested_count'], result['failed_count']), ('SUCCESS',2,1))
        self.assertIn((1,0), feedback)
        self.assertGreater(len(self.joints)-self.initial_joint_count, 15)
        self.assertGreater(sum(m['kind']=='cmd' and m['linear']==.07 for m in self.commands), 5)
        self.assertGreaterEqual(sum(m.get('op')=='start' for m in self.commands), 2)
        self.assertTrue(any(m.get('op')=='keepalive' for m in self.commands))

    def test_actual_cancel_ack_matches_uuid_and_waits_stop(self) -> None:
        self.mode = 'cancel'
        counts = []
        class RequestedCancel(Exception):
            pass
        def check() -> None:
            self.check_and_drive()
            if counts and counts[-1][0] == 1:
                raise RequestedCancel()
        with self.assertRaises(RequestedCancel):
            self.client.execute(self.goal(), check, lambda a,b: counts.append((a,b)))
        started = time.monotonic()
        result = self.client.cancel()
        self.assertEqual((result['result_code'], result['harvested_count']), ('CANCELED',1))
        self.assertGreater(time.monotonic()-started, .1)
        self.assertFalse(self.client.has_goal)
        self.assertTrue(any(m.get('op')=='cancel' for m in self.commands))


if __name__ == '__main__':
    unittest.main()
