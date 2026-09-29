"""Explicit waypoint navigation client, not the ScoutArea/YOLO mission server."""
import math
import signal
import time
import uuid

import rclpy
from rclpy.action import ActionClient
from rclpy.node import Node
from rclpy.signals import SignalHandlerOptions
from rclpy.time import Time
from action_msgs.msg import GoalStatus
from nav2_msgs.action import NavigateToPose
from tf2_ros import Buffer, TransformListener
from unique_identifier_msgs.msg import UUID
from scout_robot.route import load_route


class DriveRoute(Node):
    def __init__(self):
        super().__init__('drive_route')
        self.declare_parameter('route_file', '')
        self.declare_parameter('node_ids', list(range(1, 9)))
        self.declare_parameter('goal_timeout_s', 300.0)
        self.route = load_route(self.get_parameter('route_file').value,
                                self.get_parameter('node_ids').value)
        self.timeout = float(self.get_parameter('goal_timeout_s').value)
        if not math.isfinite(self.timeout) or self.timeout <= 0:
            raise ValueError('goal_timeout_s는 양수여야 합니다.')
        self.client = ActionClient(self, NavigateToPose, 'navigate_to_pose')
        self.tf = Buffer(); self.listener = TransformListener(self.tf, self)
        self.stop_requested = False
        self.pending = None
        # Node.handle belongs to rclpy; keep the navigation goal separate.
        self.nav_goal_handle = None

    def pump_until(self, predicate, timeout):
        end = time.monotonic() + timeout
        while rclpy.ok() and not predicate() and time.monotonic() < end:
            rclpy.spin_once(self, timeout_sec=0.1)
        return predicate()

    def cancel_own_goal(self):
        # Do not cancel other clients' goals, and do not race Nav2 with a zero cmd_vel publisher.
        if self.nav_goal_handle is None and self.pending is not None:
            if not self.pump_until(self.pending.done, 15.0):
                self.get_logger().error('목표 접수 응답 없음: 취소를 확인하지 못했습니다. bringup을 종료하세요.')
                return False
            self.nav_goal_handle = self.pending.result()
        if self.nav_goal_handle is None or not self.nav_goal_handle.accepted:
            return True
        result = self.nav_goal_handle.get_result_async()
        request = self.nav_goal_handle.cancel_goal_async()
        if not self.pump_until(lambda: request.done() and result.done(), 15.0):
            self.get_logger().error('취소 완료를 확인하지 못했습니다. bringup을 종료하세요.')
            return False
        status = result.result().status
        terminal = status in (GoalStatus.STATUS_CANCELED, GoalStatus.STATUS_ABORTED, GoalStatus.STATUS_SUCCEEDED)
        if terminal:
            self.get_logger().info('진행 중인 주행 목표가 종료되었습니다.')
        return terminal

    def run(self):
        self.get_logger().info('Nav2와 map→base_footprint 좌표 연결을 기다립니다 (최대 60초).')
        def ready():
            return (self.stop_requested or (self.client.server_is_ready()
                    and self.get_clock().now().nanoseconds > 0
                    and self.tf.can_transform('map', 'scout_01/base_footprint', Time())))
        if not self.pump_until(ready, 60.0):
            self.get_logger().error('위치 추정 또는 Nav2 준비가 완료되지 않았습니다. 주행하지 않습니다.')
            return 1
        for index, (node_id, x, y, yaw) in enumerate(self.route):
            if self.stop_requested: return 130
            goal = NavigateToPose.Goal()
            goal.pose.header.frame_id = 'map'
            goal.pose.header.stamp = self.get_clock().now().to_msg()
            goal.pose.pose.position.x = x; goal.pose.pose.position.y = y
            goal.pose.pose.orientation.z = math.sin(yaw/2)
            goal.pose.pose.orientation.w = math.cos(yaw/2)
            self.get_logger().info(f'경로점 {node_id}로 이동 ({index+1}/{len(self.route)}). Ctrl+C로 취소.')
            self.nav_goal_handle = None
            self.pending = self.client.send_goal_async(goal, goal_uuid=UUID(uuid=list(uuid.uuid4().bytes)))
            if not self.pump_until(lambda: self.pending.done() or self.stop_requested, 15.0):
                self.get_logger().error('목표 접수 지연. 취소를 시도합니다.')
                self.cancel_own_goal(); return 1
            if self.stop_requested:
                self.cancel_own_goal(); return 130
            self.nav_goal_handle = self.pending.result()
            if not self.nav_goal_handle.accepted:
                self.get_logger().error('Nav2가 목표를 거절했습니다. 다음 점으로 넘어가지 않습니다.')
                return 1
            result = self.nav_goal_handle.get_result_async()
            completed = self.pump_until(lambda: result.done() or self.stop_requested, self.timeout)
            if self.stop_requested or not completed:
                self.get_logger().warning('주행 취소 요청 또는 목표 제한 시간 초과.')
                self.cancel_own_goal(); return 130 if self.stop_requested else 1
            response = result.result()
            if response.status != GoalStatus.STATUS_SUCCEEDED:
                self.get_logger().error(f'경로점 {node_id} 주행 실패: status={response.status}, result={response.result}')
                return 1
            self.pending = None; self.nav_goal_handle = None
        self.get_logger().info('1번 베드 경로 주행 완료. 열매 검출과 ScoutArea 결과 전송은 아직 구현하지 않았습니다.')
        return 0


def main(args=None):
    # Keep the ROS context alive on Ctrl+C so this client's action can be canceled first.
    rclpy.init(args=args, signal_handler_options=SignalHandlerOptions.NO)
    node = None; previous = {}; exit_code = 1
    try:
        node = DriveRoute()
        def stop(signum, frame): node.stop_requested = True
        for sig in (signal.SIGINT, signal.SIGTERM):
            previous[sig] = signal.signal(sig, stop)
        exit_code = node.run()
    except Exception as error:
        if node is not None:
            node.get_logger().error(str(error))
            try: node.cancel_own_goal()
            except Exception: node.get_logger().error('취소 확인 실패. bringup을 종료하세요.')
        else:
            print(f'주행 시작 실패: {error}')
    finally:
        for sig, handler in previous.items(): signal.signal(sig, handler)
        if node is not None: node.destroy_node()
        if rclpy.ok(): rclpy.shutdown()
    raise SystemExit(exit_code)
