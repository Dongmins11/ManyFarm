"""환경 설정에 따라 이동 전용 또는 도착 후 팔 Action 연결을 조립합니다."""
from pathlib import Path
import signal
import threading
import json
import rclpy
from rclpy.node import Node
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.executors import MultiThreadedExecutor
from rclpy.signals import SignalHandlerOptions
from farm_navigation.configuration import load_environment, read_mapping, resolve_file
from farm_navigation.navigation_types import NavigationSettings
from farm_navigation.route import RouteGraph
from farm_navigation.pose_provider import PoseProvider
from farm_navigation.motion_monitor import MotionMonitor
from farm_navigation.nav2_client import Nav2Client
from farm_navigation.navigator import Navigator
from .mission import MissionCanceled
from std_msgs.msg import String
from rclpy.qos import QoSProfile, ReliabilityPolicy, DurabilityPolicy
from .communication import HarvestCommunication
from .arm_client import ArmActionClient, ArmActionSettings


class HarvestNode(Node):
    def __init__(self) -> None:
        super().__init__('harvest_motion_server')
        for key, default in [('project_root', ''), ('environment_config', ''), ('mode', 'sim')]:
            self.declare_parameter(key, default)
        self.root = Path(self.get_parameter('project_root').value).expanduser().resolve()
        self.mode = self.get_parameter('mode').value
        environment = resolve_file(self.root, self.get_parameter('environment_config').value)
        profile = load_environment(environment, self.root, self.mode, require_survey=False)
        self.config = read_mapping(resolve_file(self.root, profile['harvest_config']))
        policy = self.config.get('completion_policy')
        if (self.config['robot_id'] != profile['robot_id'] or self.config['map_id'] != profile['map_id']
                or policy not in ('ARRIVAL_ONLY_NO_HARVEST', 'ARRIVAL_THEN_ARM')):
            raise ValueError('수확 환경 또는 완료 정책 불일치')
        if policy == 'ARRIVAL_THEN_ARM' and self.mode != 'sim':
            raise ValueError('도착 후 팔 작업의 실물 장치 연결은 미구현입니다. 시뮬 장치로 대체하지 않습니다.')
        self.callbacks = ReentrantCallbackGroup()
        self.lock = threading.Lock()
        self.active_goal = None
        self.busy = self.blocked = self.stopping = False
        self.completed_ids = set()
        self.navigation_log = []
        self.arm_client = (ArmActionClient(self, ArmActionSettings.from_mapping(self.config.get('arm_action')),
                           self.callbacks) if policy == 'ARRIVAL_THEN_ARM' else None)
        settings = NavigationSettings.from_mapping(profile['navigation'])
        if settings.mode != 'follow_path':
            raise ValueError('수확 이동 시험은 그래프 FollowPath를 사용합니다.')
        self.poses = PoseProvider(self, settings)
        self.motion = MotionMonitor(self, settings, self.callbacks)
        self.client = Nav2Client(self, settings, self.callbacks)
        self.navigator = Navigator(self, settings, self.client, self.poses, self.motion, self.check,
            RouteGraph(profile['route_graph']), record=lambda item: self.navigation_log.append(item))
        self.events = self.create_publisher(String, 'task_events', QoSProfile(
            depth=100, reliability=ReliabilityPolicy.RELIABLE, durability=DurabilityPolicy.TRANSIENT_LOCAL))
        self.communication = HarvestCommunication(self)
        self.get_logger().info('HarvestTask 완료 정책: '+policy)

    def emit_record(self, record: dict) -> None:
        """환경 독립적인 작업 종료 진단 이벤트. 평가/팔 동작을 호출하지 않습니다."""
        message = String()
        message.data = json.dumps(record, ensure_ascii=False, allow_nan=False)
        self.events.publish(message)

    def check(self) -> None:
        if self.stopping or not rclpy.ok() or (self.active_goal and self.active_goal.is_cancel_requested):
            raise MissionCanceled('수확 작업 취소/종료 요청')


def main(args=None) -> None:
    rclpy.init(args=args, signal_handler_options=SignalHandlerOptions.NO)
    node = HarvestNode()
    executor = MultiThreadedExecutor(num_threads=4)
    executor.add_node(node)

    def stop(*_) -> None:
        node.stopping = True

    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)
    try:
        while rclpy.ok() and (not node.stopping or node.busy):
            executor.spin_once(timeout_sec=.1)
    finally:
        executor.shutdown()
        if node.arm_client is not None:
            node.arm_client.close()
        node.motion.close()
        node.poses.close()
        node.destroy_node()
        if rclpy.ok(): rclpy.shutdown()
