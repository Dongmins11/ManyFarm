"""환경 설정에 따라 이동 전용 또는 도착 후 팔 Action 연결을 조립합니다."""
from pathlib import Path
from collections.abc import Callable
import signal
import threading
import json
from dataclasses import replace
from .staged_navigation import StagedNavigation, load_sections
from .corridor_navigation import CorridorNavigator, load_corridors
from .configuration import load_harvest_config, approach_navigation_settings
import rclpy
from rclpy.node import Node
import os
from .handoff_pose_context import HarvestPoseContext
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
from farm_common.action_handoff import ActionHandoff
from farm_common.station_return import StationReturn
from farm_navigation.tag_control import TagControl
from std_msgs.msg import String
from rclpy.qos import QoSProfile, ReliabilityPolicy, DurabilityPolicy
from .communication import HarvestCommunication
from .transfer_communication import TransferCommunication
from .arm_client import ArmActionClient, configured_arm_settings
from .harvest_load import HarvestLoad


class HarvestNode(Node):
    def __init__(self) -> None:
        super().__init__('harvest_motion_server')
        for key, default in [('project_root', ''), ('environment_config', ''), ('mode', 'sim'), ('handoff_config', '')]:
            self.declare_parameter(key, default)
        self.root = Path(self.get_parameter('project_root').value).expanduser().resolve()
        self.mode = self.get_parameter('mode').value
        environment = resolve_file(self.root, self.get_parameter('environment_config').value)
        profile = load_environment(environment, self.root, self.mode, require_survey=False)
        self.config = load_harvest_config(resolve_file(self.root, profile['harvest_config']), self.root)
        handoff_file = self.get_parameter('handoff_config').value
        if handoff_file:
            self.config['handoff_runtime'] = read_mapping(resolve_file(self.root, handoff_file))
            self.config.setdefault('transfer', {})['rotation_mode'] = 'components'
            self.config['transfer']['rotation'] = {}
        policy = self.config.get('completion_policy')
        if (self.config['robot_id'] != profile['robot_id'] or self.config['map_id'] != profile['map_id']
                or policy not in ('ARRIVAL_ONLY_NO_HARVEST', 'ARRIVAL_THEN_ARM')):
            raise ValueError('수확 환경 또는 완료 정책 불일치')
        arm_settings = configured_arm_settings(self.config)
        self.declare_parameter('tag_correction', False)
        self.tag_control = (TagControl(self, profile['robot_id'], profile['map_id'])
                            if self.get_parameter('tag_correction').value else None)
        self.callbacks = ReentrantCallbackGroup()
        self.lock = threading.Lock()
        self.handoff = ActionHandoff()
        self.active_goal = None
        self.busy = self.blocked = self.stopping = False
        self.completed_ids = set()
        self.harvest_load = HarvestLoad()
        self.arm_travel_ready = True
        self.navigation_log = []
        self.arm_client = (ArmActionClient(self, arm_settings, self.callbacks)
                           if arm_settings is not None else None)
        settings = NavigationSettings.from_mapping(profile['navigation'])
        if settings.mode != 'follow_path':
            raise ValueError('수확 이동 시험은 그래프 FollowPath를 사용합니다.')
        movement_mode = self.config.get('movement_mode', 'graph_only')
        if movement_mode not in ('graph_only', 'route_then_pose', 'route_then_follow'):
            raise ValueError('알 수 없는 movement_mode')
        # 진입 FollowPath만 별도 제어기·도착 검사를 선택한다. 작업·이탈은 기존 설정이다.
        approach_settings = settings
        if movement_mode in ('route_then_pose', 'route_then_follow'):
            controller_id = self.config.get('approach_controller_id', settings.controller_id)
            if not isinstance(controller_id, str) or not controller_id.strip():
                raise ValueError('approach_controller_id는 비어 있지 않은 문자열이어야 합니다.')
            goal_checker_id = self.config.get('approach_goal_checker_id', settings.goal_checker_id)
            if not isinstance(goal_checker_id, str) or not goal_checker_id.strip():
                raise ValueError('approach_goal_checker_id는 비어 있지 않은 문자열이어야 합니다.')
            approach_settings = approach_navigation_settings(
                settings, self.config, controller_id, goal_checker_id)
        # 수확 실물 인계 비교에서만 별도 TF executor를 명시 선택한다.
        isolate_tf = os.environ.get('HANDOFF_TF_EXECUTOR', '')
        if isolate_tf not in ('', 'dedicated'):
            raise ValueError('HANDOFF_TF_EXECUTOR는 dedicated 또는 빈 값이어야 합니다.')
        if isolate_tf and (self.mode != 'real' or not handoff_file):
            raise ValueError('전용 TF 문맥은 실물 handoff 설정에서만 선택할 수 있습니다.')
        self.pose_context = HarvestPoseContext(self, settings) if isolate_tf else None
        self.poses = self.pose_context.provider if self.pose_context else PoseProvider(self, settings)
        self.motion = MotionMonitor(self, settings, self.callbacks)
        self.client = Nav2Client(self, approach_settings, self.callbacks)
        self.navigator = Navigator(self, approach_settings, self.client, self.poses, self.motion, self.check,
            RouteGraph(profile['route_graph']), record=lambda item: self.navigation_log.append(item))
        self.staged_navigation = None
        self.section_resolution = {}
        self.route_planner = None
        self.work_client = None
        self.exit_client = None
        if movement_mode in ('route_then_pose', 'route_then_follow'):
            self.get_logger().info('수확 제어기: 진입=' + approach_settings.controller_id
                                   + ', 기본=' + settings.controller_id)
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
                self.navigator = Navigator(self, approach_settings, self.client, self.poses, self.motion,
                    self.check, record=lambda item: self.navigation_log.append(item),
                    route_planner=self.route_planner)
            # scout_new와 같은 그래프 Dijkstra → Path → FollowPath 연결을 재사용한다.
            # 기존 pose 모드는 명시적으로 선택한 환경에서만 호환 유지한다.
            work_settings = (settings if movement_mode == 'route_then_follow'
                             else replace(settings, mode='navigate_to_pose'))
            # 선택 키가 있는 FollowPath 작업에만 적용한다. 이탈 제어기는 원래 설정을 유지한다.
            if movement_mode == 'route_then_follow':
                work_id = self.config.get('work_controller_id', settings.controller_id)
                if not isinstance(work_id, str) or not work_id.strip():
                    raise ValueError('work_controller_id는 비어 있지 않은 문자열이어야 합니다.')
                work_settings = replace(work_settings, controller_id=work_id)
            self.get_logger().info('수확 작업 제어기=' + work_settings.controller_id
                                   + ', 이탈 제어기=' + settings.controller_id)
            self.work_client = Nav2Client(self, work_settings, self.callbacks)
            corridors = load_corridors(self.config, graph)
            self.section_resolution = dict(corridors=corridors,
                position_tolerance_m=settings.max_goal_distance_m,
                heading_tolerance_rad=settings.heading_tolerance_rad)
            if self.config.get('resolve_section_from_goal_pose', False) and set(corridors) != set(sections):
                raise ValueError('pose 기반 구역 선택에는 모든 Section의 작업 구간이 필요합니다.')
            if corridors and (movement_mode != 'route_then_follow' or work_settings.parallel_approach):
                raise ValueError('중간 시작은 일반 FollowPath 작업 모드에서만 사용합니다.')
            work_class = CorridorNavigator if corridors else Navigator
            work_options = {'corridors': corridors,
                'path_heading_limit': self.config.get('work_path_heading_limit_rad')} if corridors else {}
            work = work_class(self, work_settings, self.work_client, self.poses, self.motion,
                self.check, graph=graph if movement_mode == 'route_then_follow' else None,
                record=lambda item: self.navigation_log.append(item), **work_options)
            exit_navigator = work
            if corridors or work_settings.controller_id != settings.controller_id:
                self.exit_client = Nav2Client(self, settings, self.callbacks)
                exit_navigator = Navigator(self, settings, self.exit_client, self.poses, self.motion,
                    self.check, graph=graph, record=lambda item: self.navigation_log.append(item))
            def current_xy() -> tuple[float, float]:
                transform = self.poses.current(self.check)
                return float(transform[0,3]), float(transform[1,3])
            self.staged_navigation = StagedNavigation(self.navigator, work, sections,
                current_xy, self.check, lambda item: self.navigation_log.append(item),
                settings.max_start_distance_m, exit_navigator=exit_navigator,
                resume_current=work.resume_current if corridors else None,
                # 반복 태그는 진입·이탈 중에 구역을 추측하지 않고 작업 선분에서만 보정한다.
                before_move=(lambda phase, section: self.tag_control.begin(
                    section if phase == 'WINDOW_MOVE' else None))
                    if self.tag_control else None)
        self.events = self.create_publisher(String, 'task_events', QoSProfile(
            depth=100, reliability=ReliabilityPolicy.RELIABLE, durability=DurabilityPolicy.TRANSIENT_LOCAL))
        # 환경 데이터가 선택한 인계 장치만 연결한다. sim/real 업무 코드는 동일하다.
        transfer_config = self.config.get("transfer", {})
        self.declare_parameter("transfer_enabled", transfer_config.get("enabled", False))
        self.handoff_runtime = None
        if self.get_parameter("transfer_enabled").value and transfer_config.get('rotation_mode') == 'components':
            from .handoff_runtime import HandoffRuntime
            self.handoff_runtime = HandoffRuntime(self, profile, settings)
        self.transfer = (TransferCommunication(self, settings)
                         if self.get_parameter("transfer_enabled").value else None)
        self.body_trial = None
        trial_enabled = self.config.get('handoff_runtime', {}).get('body_trial_enabled', False)
        self.declare_parameter('handoff_body_trial_enabled', trial_enabled)
        if trial_enabled:
            if self.handoff_runtime is None:
                raise ValueError('차체 시험에는 handoff runtime이 필요합니다.')
            from .handoff_body_trial import BodyTrial
            self.body_trial = BodyTrial(self)
        self.station_return = StationReturn(self, root=self.root, profile=profile, settings=settings,
            poses=self.poses, motion=self.motion, callbacks=self.callbacks, handoff=self.handoff,
            unavailable=lambda: self.blocked or self.stopping,
            block=lambda: setattr(self, 'blocked', True), prepare=self.prepare_station_return,
            tag_control=self.tag_control)
        self.communication = HarvestCommunication(self)
        self.status_reporter = None
        status_config = self.config.get('status_reporting', {})
        if status_config.get('enabled', False):
            from .status import HarvestStatus
            self.status_reporter = HarvestStatus(self, settings, status_config)
        self.get_logger().info('HarvestTask 완료 정책: '+policy)

    def emit_record(self, record: dict) -> None:
        """환경 독립적인 작업 종료 진단 이벤트. 평가/팔 동작을 호출하지 않습니다."""
        message = String()
        message.data = json.dumps(record, ensure_ascii=False, allow_nan=False)
        self.events.publish(message)

    def prepare_station_return(self, check: Callable[[], None]) -> None:
        """인계 조건의 확장 지점. 팔이 중단된 경우 안전한 주행 준비를 먼저 확인한다."""
        check()
        if self.handoff_runtime is not None:
            self.handoff_runtime.invalidate_window()
        if self.arm_client is not None and getattr(self, 'mission_stage', '') == 'ARM':
            result = getattr(self, 'arm_result', None)
            if result is None or result['result_code'] != 'SUCCESS':
                raise RuntimeError('ARM_TRAVEL_NOT_READY: 중단된 팔의 접힘 확인이 필요합니다.')

    def check(self) -> None:
        if self.handoff.work_interrupted or self.stopping or not rclpy.ok() or (self.active_goal and self.active_goal.is_cancel_requested):
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
        while rclpy.ok() and (not node.stopping or node.busy or node.handoff.busy):
            executor.spin_once(timeout_sec=.1)
    finally:
        if node.tag_control is not None:
            node.tag_control.end()
        executor.shutdown()
        if node.status_reporter is not None:
            node.status_reporter.close()
        if node.route_planner is not None:
            node.route_planner.close()
        if node.work_client is not None:
            node.work_client.close()
        if node.exit_client is not None:
            node.exit_client.close()
        if node.body_trial is not None:
            node.body_trial.close()
        node.station_return.close()
        if node.transfer is not None:
            node.transfer.close()
        if node.handoff_runtime is not None:
            node.handoff_runtime.close()
        node.client.close()
        if node.arm_client is not None:
            node.arm_client.close()
        node.motion.close()
        if node.pose_context is not None:
            node.pose_context.close()
        else:
            node.poses.close()
        node.destroy_node()
        if rclpy.ok(): rclpy.shutdown()
