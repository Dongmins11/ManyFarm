"""실물 복귀의 직선·원호 실행 조립. 미션·태그·Action 소유권은 기존 컴포넌트가 맡는다."""
from __future__ import annotations
import json
import math
import threading
import time
from typing import Any, Callable
from geometry_msgs.msg import PolygonStamped, Twist
from nav2_msgs.msg import Costmap
from rclpy.qos import qos_profile_sensor_data
from rosidl_runtime_py.convert import message_to_ordereddict
from farm_navigation.arc_clearance import check_grid, ObstacleBlocked
from farm_navigation.collision_recovery import Nav2ControlUnavailable, run_with_collision_recovery
from farm_navigation.nav2_client import Nav2Client
from farm_navigation.navigator import Navigator
from farm_navigation.spin_client import SpinClient
from farm_navigation.transfer_arc import ArcSpec, wrap
from .station_corner_config import navigation_settings
from .station_corner_plan import anchored_arc, split_graph_corners, subroute
from .station_return_mission import reverse_control_error


def corner_control_error(message: str) -> bool:
    """기존 후진 충돌과 원호 충돌만 재시도한다. 경로 이탈은 성공으로 바꾸지 않는다."""
    return reverse_control_error(message) or message.strip().lower() == 'collision on transfer arc'


def pose_tuple(matrix: Any) -> tuple[float, float, float]:
    return float(matrix[0, 3]), float(matrix[1, 3]), math.atan2(matrix[1, 0], matrix[0, 0])


class CornerNavigation:
    """기존 Navigator/SpinClient로 위치 접근·방향 정렬·원호를 실행하고 마지막 직선은 원래 Navigator에 넘긴다."""

    def __init__(self, node: Any, *, straight: Any, settings: Any, radius: float, graph: Any,
                 robot_id: str, poses: Any, motion: Any, callbacks: Any,
                 check: Callable[[], None], owns_output: Callable[[], bool],
                 recovery_stop: Callable[[], None]) -> None:
        self._node, self._straight, self._poses = node, straight, poses
        self._settings, self._radius, self._check = settings, radius, check
        self._graph = graph
        self._owns_output = owns_output
        self._motion, self._recovery_stop = motion, recovery_stop
        self._lock = threading.RLock()
        self._enabled = False
        self._alignment_needs_stop = False
        self._costmap = self._footprint = None
        self._publisher = node.create_publisher(Twist, 'cmd_vel_normal', 10)
        prefix = '/'+robot_id+'/station_corner'
        self._subscriptions = [
            node.create_subscription(Twist, prefix+'/raw_nav', self._relay, 10, callback_group=callbacks),
            node.create_subscription(Costmap, prefix+'/local_costmap/costmap_raw',
                self._receive_costmap, qos_profile_sensor_data, callback_group=callbacks),
            node.create_subscription(PolygonStamped, prefix+'/local_costmap/published_footprint',
                self._receive_footprint, qos_profile_sensor_data, callback_group=callbacks)]
        self._spin = SpinClient(node, prefix+'/spin', settings, callbacks)
        self._clients, self._navigators = [], []
        for arc in (False, True):
            selected = navigation_settings(settings, robot_id, arc=arc)
            client = Nav2Client(node, selected, callbacks, retryable_control_error=corner_control_error)
            client.set_recovery_stop(recovery_stop)
            navigator = Navigator(node, selected, client, poses, motion, check,
                explicit_routes=True, stop_output=self._disable, record=self._record)
            self._clients.append(client)
            self._navigators.append(navigator)
        self._approach, self._arc = self._navigators

    def _record(self, value: dict) -> None:
        self._node.get_logger().info('STATION_CORNER '+json.dumps(value, ensure_ascii=False))

    def _receive_costmap(self, message: Costmap) -> None:
        with self._lock:
            self._costmap = message

    def _receive_footprint(self, message: PolygonStamped) -> None:
        with self._lock:
            self._footprint = message

    def _relay(self, message: Twist) -> None:
        with self._lock:
            if self._enabled and self._owns_output():
                self._publisher.publish(message)

    def _enable(self) -> None:
        self._check()
        with self._lock:
            if not self._owns_output():
                raise RuntimeError('복귀 코너 출력 소유권 상실')
            self._enabled = True

    def _disable(self) -> None:
        with self._lock:
            self._enabled = False
            if self._owns_output():
                self._publisher.publish(Twist())

    def preflight_navigation(self) -> None:
        self._straight.preflight_navigation()
        for navigator in self._navigators:
            navigator.preflight_navigation()
        deadline = time.monotonic()+self._settings.readiness_timeout_s
        while not self._spin.ready():
            self._check()
            if time.monotonic() >= deadline:
                raise RuntimeError('복귀 방향 정렬 Spin 서버 미연결')
            time.sleep(.02)

    def _align(self, arrival: Any, entry_yaw: float, template: Any) -> tuple:
        """위치 완료 후 동일 정지 시각의 map/odom으로 회전량을 고정한다(m/rad)."""
        origin = pose_tuple(self._poses.lookup('odom', self._settings.base_frame,
            arrival.stamp_ns, self._check))
        stopped_map = pose_tuple(self._poses.lookup(self._settings.map_frame,
            self._settings.base_frame, arrival.stamp_ns, self._check))
        delta = wrap(entry_yaw-stopped_map[2])
        target = wrap(origin[2]+delta)
        if abs(delta) <= ArcSpec().yaw_tolerance:
            return origin
        # 기존 연속 footprint 검사가 각 구간의 중간 회전까지 재귀 검사한다.
        # 인계 재진입의 15도 제한을 다른 위치인 스테이션 접근에 복사하지 않는다.
        poses = [(*origin[:2], wrap(origin[2]+delta*fraction)) for fraction in (0., .5, 1.)]
        plan = subroute(template, [p[:2] for p in poses],
            headings=tuple(p[2] for p in poses), frame='odom')
        self._clearance_with_retry(plan)
        self._record(dict(stage='align', origin_odom=origin, delta_rad=delta))
        self._enable()
        self._alignment_needs_stop = True
        try:
            self._spin.execute(delta, self._settings.goal_timeout_s, self._check)
        finally:
            self._disable()
        stamp = self._motion.wait_stopped(self._check)
        self._alignment_needs_stop = False
        measured = pose_tuple(self._poses.lookup('odom', self._settings.base_frame, stamp, self._check))
        if abs(wrap(measured[2]-target)) > ArcSpec().yaw_tolerance:
            raise RuntimeError('복귀 진입 방향 정렬 후 오차 초과')
        self._record(dict(stage='align_complete', stamp_ns=stamp, pose_odom=measured))
        return measured

    def _clearance(self, plan: Any) -> float:
        """실제 정지 자세로 만든 odom 원호를 최신 발행 footprint/costmap에 검사한다."""
        deadline = time.monotonic()+self._settings.response_timeout_s
        while True:
            self._check()
            with self._lock:
                grid, footprint = self._costmap, self._footprint
            now = self._node.get_clock().now().nanoseconds
            def fresh(message: Any) -> bool:
                if message is None or message.header.frame_id != plan.frame_id:
                    return False
                stamp = message.header.stamp.sec*1_000_000_000+message.header.stamp.nanosec
                return 0 <= now-stamp <= self._settings.tf_max_age_s*1e9
            if fresh(grid) and fresh(footprint):
                break
            if time.monotonic() >= deadline:
                raise RuntimeError('복귀 코너의 최신 odom costmap/footprint 수신 실패')
            time.sleep(.02)
        stamp = footprint.header.stamp.sec*1_000_000_000+footprint.header.stamp.nanosec
        current = pose_tuple(self._poses.lookup(plan.frame_id, self._settings.base_frame, stamp, self._check))
        path = [(*point, yaw) for point, yaw in zip(plan.points, plan.headings)]
        return check_grid(path, [(p.x, p.y) for p in footprint.polygon.points],
                          current, message_to_ordereddict(grid))

    def navigate(self, xy: tuple, yaw: float, *, route_plan: Any, reverse: bool) -> Any:
        if not reverse:
            raise ValueError('실물 복귀 코너 조립은 후진 경로 전용입니다.')
        corners, tail = split_graph_corners(route_plan, self._radius, self._graph)
        for corner in corners:
            self._enable()
            try:
                arrival = self._approach.navigate(corner.approach.points[-1], corner.entry_yaw,
                    route_plan=corner.approach, reverse=True)
            finally:
                self._disable()
            self._record(dict(stage='approach_complete', stamp_ns=arrival.stamp_ns,
                              measurement=arrival.measurement))
            origin = self._align(arrival, corner.entry_yaw, route_plan)
            plan = anchored_arc(route_plan, origin, corner.spec, 'odom')
            clearance = self._clearance_with_retry(plan)
            self._record(dict(stage='arc', origin_odom=origin, radius_m=corner.spec.radius,
                clearance_lower_bound_m=clearance, points_odom=plan.points, headings=plan.headings))
            self._enable()
            try:
                result = self._arc.navigate(plan.points[-1], plan.headings[-1], route_plan=plan)
            finally:
                self._disable()
            self._record(dict(stage='arc_complete', stamp_ns=result.stamp_ns,
                              measurement=result.measurement))
        if corners:
            # 실제 원호 종점에서 원래 그래프 종점으로 연결한다. 목표 노드/방향은 바꾸지 않는다.
            current = pose_tuple(self._poses.current(self._check))
            tail = subroute(tail, [current[:2], *tail.points[1:]])
        return self._straight.navigate(xy, yaw, route_plan=tail, reverse=True)

    def _clearance_with_retry(self, plan: Any) -> float:
        """진입 전 일시 장애물도 기존 정지·TF 확인과 재시도 횟수를 재사용한다."""
        def inspect() -> float:
            try:
                return self._clearance(plan)
            except ObstacleBlocked as error:
                raise Nav2ControlUnavailable(str(error)) from error
        return run_with_collision_recovery(inspect,
            lambda: self._poses.recovery_ready() and self._motion.stationary_now(),
            self._recovery_stop, self._check, self._settings.collision_retry_count,
            self._node.get_logger().warning)

    def cancel_nav(self) -> None:
        self._disable()
        errors = []
        # 한 취소가 실패해도 나머지 Goal 정리는 계속한다. 실패는 기존 Action 정리로 전달한다.
        for navigator in (*self._navigators, self._straight):
            try:
                navigator.cancel_nav()
            except Exception as error:
                errors.append(error)
        try:
            self._spin.cancel()
            if self._alignment_needs_stop:
                self._motion.wait_stopped(lambda: None)
                self._alignment_needs_stop = False
        except Exception as error:
            errors.append(error)
        if errors:
            raise errors[0]

    def close(self) -> None:
        self._disable()
        self._spin.close()
        for client in self._clients:
            client.close()
        for subscription in self._subscriptions:
            self._node.destroy_subscription(subscription)
        self._node.destroy_publisher(self._publisher)
