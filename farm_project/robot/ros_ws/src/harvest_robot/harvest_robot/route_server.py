"""ComputeRoute 결과를 공통 Navigator에 전달. 실패 시 자체 경로로 대체하지 않는다."""
from farm_navigation.operation_clock import operation_time
import math
import time
import uuid
from typing import Any, Callable
from rclpy.action import ActionClient
from nav2_msgs.action import ComputeRoute
from action_msgs.msg import GoalStatus
from farm_navigation.navigation_types import RoutePlan


def route_plan(path: Any, start: tuple, goal: tuple, frame: str, revision: str,
               start_tolerance: float, goal_tolerance: float) -> RoutePlan:
    """서버 경로의 순서/형상을 보존하고 허용 범위 내 끝점만 연결한다."""
    if path.header.frame_id != frame or not path.poses:
        raise ValueError('Route Server 경로가 비었거나 좌표계 불일치')
    points = []
    for pose in path.poses:
        if pose.header.frame_id not in ('', frame):
            raise ValueError('Route Server pose 좌표계 불일치')
        p = pose.pose.position
        if not all(math.isfinite(v) for v in (p.x, p.y, p.z)) or abs(p.z) > .1:
            raise ValueError('Route Server 경로 좌표 오류')
        xy = (p.x, p.y)
        if not points or math.dist(xy, points[-1]) > 1e-7:
            points.append(xy)
    if math.dist(start, points[0]) > start_tolerance or math.dist(goal, points[-1]) > goal_tolerance:
        raise ValueError('Route Server 경로와 실제 시작/진입점 간격 초과; 임의 직선 연결하지 않음')
    if math.dist(start, points[0]) > 1e-7:
        points.insert(0, start)
    if math.dist(goal, points[-1]) > 1e-7:
        points.append(goal)
    return RoutePlan(uuid.uuid4().hex, revision, frame, tuple(points), (),
                     sum(math.dist(a,b) for a,b in zip(points,points[1:])))


class RouteServerPlanner:
    def __init__(self, node: Any, settings: Any, callbacks: Any, revision: str) -> None:
        self.node, self.settings, self.revision = node, settings, revision
        self.client = ActionClient(node, ComputeRoute, 'compute_route', callback_group=callbacks)
        self.pending = self.handle = self.result = None

    def _wait(self, future: Any, timeout: float, check: Callable) -> Any:
        end = operation_time(self.node) + timeout
        while not future.done():
            check()
            if operation_time(self.node) >= end:
                raise TimeoutError('ComputeRoute 응답 시간 초과')
            time.sleep(.02)
        check()
        return future.result()

    def plan(self, start: tuple, goal: tuple, check: Callable) -> RoutePlan:
        if self.pending is not None:
            raise RuntimeError('이전 ComputeRoute 종료 확인 필요')
        s = self.settings
        end = operation_time(self.node) + s.readiness_timeout_s
        while not self.client.server_is_ready():
            check()
            if operation_time(self.node) >= end:
                raise TimeoutError('ComputeRoute 서버 준비 시간 초과')
            time.sleep(.05)
        request = ComputeRoute.Goal()
        request.use_start = request.use_poses = True
        stamp = self.node.get_clock().now().to_msg()
        for pose, xy in ((request.start, start), (request.goal, goal)):
            pose.header.frame_id = s.map_frame
            pose.header.stamp = stamp
            pose.pose.position.x, pose.pose.position.y = map(float, xy)
            pose.pose.orientation.w = 1.0
        self.pending = self.client.send_goal_async(request)
        self.handle = self._wait(self.pending, s.response_timeout_s, check)
        if not self.handle.accepted:
            self._clear()
            raise RuntimeError('ComputeRoute Goal 거절')
        self.result = self.handle.get_result_async()
        response = self._wait(self.result, s.response_timeout_s, check)
        self._clear()
        if response.status != GoalStatus.STATUS_SUCCEEDED or response.result.error_code != 0:
            # 설치된 Jazzy 결과는 error_code만 제공한다. 문구는 있는 버전에서만 읽는다.
            detail = getattr(response.result, 'error_msg', '')
            raise RuntimeError(f'ComputeRoute 실패: status={response.status}, '
                               f'error_code={response.result.error_code}' + (f', {detail}' if detail else ''))
        return route_plan(response.result.path, start, goal, s.map_frame, self.revision,
                          s.max_start_distance_m, s.max_goal_distance_m)

    def cancel(self) -> None:
        check = lambda: None
        timeout = self.settings.cancel_timeout_s
        if self.handle is None and self.pending is not None:
            self.handle = self._wait(self.pending, timeout, check)
        if self.handle is not None and self.handle.accepted:
            future = self.result or self.handle.get_result_async()
            if not future.done():
                self._wait(self.handle.cancel_goal_async(), timeout, check)
            result = self._wait(future, timeout, check)
            if result.status not in (GoalStatus.STATUS_SUCCEEDED, GoalStatus.STATUS_ABORTED, GoalStatus.STATUS_CANCELED):
                raise RuntimeError('ComputeRoute 종료 미확인')
        self._clear()

    def _clear(self) -> None:
        self.pending = self.handle = self.result = None

    def close(self) -> None:
        self.client.destroy()
