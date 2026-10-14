"""실제 rclpy.Node. ROS 자원·설정을 준비하고 역할별 객체를 연결합니다."""
from __future__ import annotations

import numpy as np
from numpy.typing import NDArray
from pathlib import Path
import signal
import threading
import rclpy
from _thread import LockType
from rclpy.publisher import Publisher
from rclpy.action.server import ServerGoalHandle
from rclpy.callback_groups import ReentrantCallbackGroup, MutuallyExclusiveCallbackGroup
from rclpy.clock import Clock, ClockType
from rclpy.executors import MultiThreadedExecutor
from rclpy.node import Node
from rclpy.signals import SignalHandlerOptions
from rclpy.timer import Timer
from geometry_msgs.msg import Point
from visualization_msgs.msg import Marker, MarkerArray
from farm_navigation.configuration import read_mapping, load_environment, resolve_file
from farm_navigation.navigation_types import NavigationSettings
from farm_navigation.route import RouteGraph, load_route
from farm_navigation.navigator import Navigator
from farm_navigation.nav2_client import Nav2Client
from farm_navigation.pose_provider import PoseProvider
from farm_navigation.motion_monitor import MotionMonitor
from farm_navigation.tag_control import TagControl
from scout_robot.survey_core import StraightBed, Survey
from .runtime import MissionCanceled
from .scout_mission import ScoutMission
from .scout_state_controller import ScoutStateController
from .mission_types import JsonObject
from .scout_communication import ScoutCommunication

class ScoutNode(Node):

    def __init__(self) -> None:
        super().__init__('scout_survey')
        self._initialize_settings()
        self._initialize_ros()
        self._initialize_components()

    def _initialize_settings(self) -> None:
        for key, value in [('project_root', ''), ('survey_config', ''), ('environment_config',''),
                           ('mode','sim'), ('tag_correction', False), ('vision_python', ''), ('device', '0'), ('headless', False)]:
            self.declare_parameter(key, value)
        self._root: Path = Path(self.get_parameter('project_root').value).expanduser().resolve()
        env_file = str(self.get_parameter('environment_config').value)
        self._environment: JsonObject = {}
        self._readiness_error = ''
        if env_file:
            self._environment = load_environment(resolve_file(self._root,env_file),self._root,str(self.get_parameter('mode').value),require_survey=False)
            if self._environment.get('survey_configured', True):
                self._environment = load_environment(resolve_file(self._root,env_file),self._root,str(self.get_parameter('mode').value))
            config = self._root / self._environment['survey_config']
            if self._environment.get('survey_configured', True) is False:
                self._readiness_error = '실물 예찰 설정이 미완성입니다. survey_configured와 베드·카메라 설정을 확인하세요.'
            explicit = str(self.get_parameter('survey_config').value)
            if explicit and resolve_file(self._root,explicit)!=config:
                raise ValueError('환경 선택과 다른 survey_config를 동시에 지정할 수 없습니다.')
        else:
            config = resolve_file(self._root,str(self.get_parameter('survey_config').value))
        if self._readiness_error:
            self._cfg = {key:self._environment[key] for key in ('robot_id','map_id')}
            self._cfg.update(base_frame=self._environment['navigation']['base_frame'], sections={})
            self._vcfg = {}
        else:
            self._cfg = read_mapping(config)
            self._vcfg = read_mapping(resolve_file(self._root,self._cfg['vision_config']))
        self._python: Path = Path(self.get_parameter('vision_python').value or self._vcfg.get('worker_python','')).expanduser()
        if not self._python.is_file():
            self._readiness_error = self._readiness_error or 'vision_python에 실제 영상 환경 Python 경로를 지정하세요.'
        # 이전 직접 실행도 지원하되 새 통합 런치는 환경 파일을 유일한 선택점으로 사용합니다.
        settings = {key:self._cfg[key] for key in ('base_frame','goal_timeout_s',
                    'arrival_tolerance_m','heading_tolerance_rad','settle_s','controller_node') if key in self._cfg}
        settings.update(self._environment.get('navigation',{}))
        if settings.get('base_frame') != self._cfg['base_frame']:
            raise ValueError('예찰과 주행 base_frame 불일치')
        self._navigation_settings = NavigationSettings.from_mapping(settings)
        if self._navigation_settings.map_frame != 'map':
            raise ValueError('현재 ScoutArea 계약의 좌표계는 map입니다.')
        self._route_graph = (RouteGraph(self._environment['route_graph'],self._navigation_settings.map_frame)
                             if self._environment else None)
        if self._environment.get('patrol_config') and not self._readiness_error:
            from .patrol_config import apply_patrol
            patrol = read_mapping(resolve_file(self._root,self._environment['patrol_config']))
            if resolve_file(self._root,patrol['route_graph']) != Path(self._environment['route_graph']):
                raise ValueError('순찰과 주행 그래프가 다릅니다.')
            self._cfg = apply_patrol(self._cfg,patrol,self._route_graph)
        self._beds: dict[str, StraightBed] = {}
        for key, c in self._cfg['sections'].items():
            self._beds[key] = StraightBed(load_route(self._root / c['route_file'], c['node_ids']), c)
            if c.get('patrol_segments'):
                from .patrol_config import patrol_design
                patrol_design(self._beds[key],self._route_graph)

    def _initialize_ros(self) -> None:
        # 작업이 기다리는 동안 다른 스레드가 odom·TF·액션 응답을 처리합니다.
        self._cb: ReentrantCallbackGroup = ReentrantCallbackGroup()
        self._lock: LockType = threading.Lock()
        self._busy: bool = False
        self._motion_uncertain: bool = False
        self._shutdown_requested: bool = False
        self._active_goal: ServerGoalHandle | None = None
        self._navigation_log: list[JsonObject] = []
        self._markers: Publisher = self.create_publisher(MarkerArray, 'survey_markers', 10)
        self._last_markers: MarkerArray | None = None
        self.create_timer(1.0, self.repeat_markers, callback_group=self._cb)

    def _initialize_components(self) -> None:
        # 역할을 각각 만들고 명시적으로 연결합니다. Mission이 Controller를 소유하지 않습니다.
        self._tag_control = (TagControl(self, self._cfg['robot_id'], self._cfg['map_id'])
                             if self.get_parameter('tag_correction').value else None)
        self._poses = PoseProvider(self,self._navigation_settings)
        self._motion = MotionMonitor(self,self._navigation_settings,self._cb)
        self._nav2 = Nav2Client(self,self._navigation_settings,self._cb)
        self._navigator = Navigator(self,self._navigation_settings,self._nav2,self._poses,self._motion,
                                    self.check,self._route_graph,
                                    record=lambda entry:self._navigation_log.append(entry))
        self._mission: ScoutMission = ScoutMission(self)
        self._state_controller: ScoutStateController = ScoutStateController(self._mission)
        from .vision_runtime import VisionRuntime
        self._vision = VisionRuntime(self) if not self._readiness_error else None
        self._communication: ScoutCommunication = ScoutCommunication(self, self._state_controller)
        self._state_group: MutuallyExclusiveCallbackGroup = MutuallyExclusiveCallbackGroup()
        self._state_clock: Clock = Clock(clock_type=ClockType.STEADY_TIME)
        self._state_timer: Timer = self.create_timer(
            0.02, self._state_controller.update,
            callback_group=self._state_group, clock=self._state_clock,
        )
        # /clock이 멈춰도 취소·종료 처리는 진행되도록 상태 이벤트는 steady clock을 씁니다.
        if self._readiness_error:
            self.get_logger().warning('ScoutArea 명령 대기 (작업 수락 불가): ' + self._readiness_error)
        else:
            self.get_logger().info('ScoutArea 연결 완료: 영상 사전 준비 완료 후 Goal을 수락합니다.')

    def repeat_markers(self) -> None:
        if self._last_markers is not None:
            self._markers.publish(self._last_markers)

    def check(self) -> None:
        if self._state_controller.stop_requested or self._shutdown_requested or not rclpy.ok() or (self._active_goal and self._active_goal.is_cancel_requested):
            raise MissionCanceled('ScoutArea canceled')

    def lookup(self, target: str, source: str, stamp: int) -> NDArray[np.float64]:
        """예찰 코드의 기존 호출 형태를 유지하는 공통 TF 조회 연결입니다."""
        return self._poses.lookup(target,source,stamp,self.check)

    def show(self, survey: Survey) -> None:
        array = MarkerArray()
        clear = Marker()
        clear.action = Marker.DELETEALL
        array.markers.append(clear)
        for i, f in enumerate(survey.fruits):
            m = Marker()
            m.header.frame_id = 'map'
            m.ns = 'fruit'
            m.id = i
            m.type = Marker.SPHERE
            m.action = Marker.ADD
            m.pose.orientation.w = 1.0
            m.pose.position = Point(x=f['position_map_m'][0], y=f['position_map_m'][1], z=f['position_map_m'][2])
            m.scale.x = m.scale.y = m.scale.z = 0.04
            m.color.r = 1.0
            m.color.g = 0.0 if f['class_name'] == 'Red' else 1.0
            m.color.a = 1.0
            array.markers.append(m)
            t = Marker()
            t.header.frame_id = 'map'
            t.ns = 'fruit_id'
            t.id = i
            t.type = Marker.TEXT_VIEW_FACING
            t.action = Marker.ADD
            t.pose.orientation.w = 1.0
            t.pose.position = Point(x=m.pose.position.x, y=m.pose.position.y, z=m.pose.position.z + 0.05)
            t.text = f['id']
            t.scale.z = 0.045
            t.color.r = t.color.g = t.color.b = t.color.a = 1.0
            array.markers.append(t)
        edges = [(0, 1), (0, 2), (1, 3), (2, 3), (4, 5), (4, 6), (5, 7), (6, 7), (0, 4), (1, 5), (2, 6), (3, 7)]
        for i, w in enumerate(survey.windows()):
            m = Marker()
            m.header.frame_id = 'map'
            m.ns = 'window'
            m.id = i
            m.type = Marker.LINE_LIST
            m.action = Marker.ADD
            m.pose.orientation.w = 1.0
            m.scale.x = 0.008
            m.color.r = m.color.b = m.color.a = 1.0
            for a, b in edges:
                for j in [a, b]:
                    m.points.append(Point(x=w['corners_map_m'][j][0], y=w['corners_map_m'][j][1], z=w['corners_map_m'][j][2]))
            array.markers.append(m)
            if w.get('range_tolerance_m', 0) > 0:
                outer = Marker()
                outer.header.frame_id = 'map'
                outer.ns = 'window_tolerance'
                outer.id = i
                outer.type = Marker.LINE_LIST
                outer.action = Marker.ADD
                outer.pose.orientation.w = 1.0
                outer.scale.x = 0.004
                outer.color.g = outer.color.b = outer.color.a = 1.0
                for a, b in edges:
                    for j in [a, b]:
                        p = w['acceptance_corners_map_m'][j]
                        outer.points.append(Point(x=p[0], y=p[1], z=p[2]))
                array.markers.append(outer)
        self._last_markers = array
        self.repeat_markers()

def main(args: list[str] | None = None) -> None:
    rclpy.init(args=args, signal_handler_options=SignalHandlerOptions.NO)
    node = ScoutNode()
    # 액션 결과 대기 중에도 ROS 응답과 상태 타이머가 실행되도록 여러 스레드를 사용합니다.
    executor = MultiThreadedExecutor(num_threads=4)
    executor.add_node(node)

    def stop(*_: object) -> None:
        node._shutdown_requested = True
    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)
    try:
        while rclpy.ok() and (not node._shutdown_requested or node._busy):
            executor.spin_once(timeout_sec=0.1)
    finally:
        executor.shutdown()
        node._state_controller.close()
        if node._tag_control is not None:
            node._tag_control.end()
        if node._vision is not None:
            node._vision.close()
        node._communication.close()
        node._nav2.close()
        node._motion.close()
        node._poses.close()
        node.destroy_node()
        rclpy.shutdown()
if __name__ == '__main__':
    main()
