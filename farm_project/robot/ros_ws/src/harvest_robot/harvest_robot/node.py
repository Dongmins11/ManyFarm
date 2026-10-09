"""환경 설정에 따라 이동 전용 또는 도착 후 팔 Action 연결을 조립합니다."""
from pathlib import Path
import signal
import threading
import json
from dataclasses import replace
from .staged_navigation import StagedNavigation, load_sections
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
from .tag_control import TagControl
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
        self.declare_parameter('tag_correction', False)
        self.tag_control = (TagControl(self, profile['robot_id'], profile['map_id'])
                            if self.get_parameter('tag_correction').value else None)
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
        self.staged_navigation = None
        self.route_planner = None
        self.work_client = None
        movement_mode = self.config.get('movement_mode', 'graph_only')
        if movement_mode not in ('graph_only', 'route_then_pose', 'route_then_follow'):
            raise ValueError('알 수 없는 movement_mode')
        if movement_mode in ('route_then_pose', 'route_then_follow'):
            graph = RouteGraph(profile['route_graph'])
            sections = load_sections(self.config, graph)
            approach_planner = self.config.get('approach_planner', 'route_server')
            if approach_planner not in ('graph', 'route_server'):
                raise ValueError('알 수 없는 approach_planner')
            # graph는 scout_new와 같은 선분 투영·다익스트라를 사용한다.
            # Route Server를 명시한 기존 환경만 외부 계획기를 연결한다.
            if approach_planner == 'route_server':
                from .route_server import RouteServerPlanner
                self.route_planner = RouteServerPlanner(self, settings, self.callbacks, graph.revision)
                self.navigator = Navigator(self, settings, self.client, self.poses, self.motion,
                    self.check, record=lambda item: self.navigation_log.append(item),
                    route_planner=self.route_planner)
            # scout_new와 같은 그래프 Dijkstra → Path → FollowPath 연결을 재사용한다.
            # 기존 pose 모드는 명시적으로 선택한 환경에서만 호환 유지한다.
            work_settings = (settings if movement_mode == 'route_then_follow'
                             else replace(settings, mode='navigate_to_pose'))
            self.work_client = Nav2Client(self, work_settings, self.callbacks)
            work = Navigator(self, work_settings, self.work_client, self.poses, self.motion,
                self.check, graph=graph if movement_mode == 'route_then_follow' else None,
                record=lambda item: self.navigation_log.append(item))
            def current_xy() -> tuple[float, float]:
                transform = self.poses.current(self.check)
                return float(transform[0,3]), float(transform[1,3])
            self.staged_navigation = StagedNavigation(self.navigator, work, sections,
                current_xy, self.check, lambda item: self.navigation_log.append(item),
                settings.max_start_distance_m)
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
        if node.tag_control is not None:
            node.tag_control.end()
        executor.shutdown()
        if node.route_planner is not None:
            node.route_planner.close()
        if node.work_client is not None:
            node.work_client.close()
        node.client.close()
        if node.arm_client is not None:
            node.arm_client.close()
        node.motion.close()
        node.poses.close()
        node.destroy_node()
        if rclpy.ok(): rclpy.shutdown()
