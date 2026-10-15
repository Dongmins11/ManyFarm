"""환경별 스테이션으로 향하는 공통 Action. 작업 의미는 로봇의 준비 콜백에 둔다."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import datetime, timezone
import math
import time
import uuid
from pathlib import Path
from typing import Any

import rclpy
from rclpy.action import ActionServer, CancelResponse, GoalResponse
from farm_interfaces.action import ReturnToStation
from farm_navigation.configuration import read_mapping, resolve_file
from farm_navigation.nav2_client import Nav2Client
from farm_navigation.navigator import Navigator
from farm_navigation.route import RouteGraph
from .action_handoff import ActionHandoff, ActionInterrupted


def timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class Station:
    station_id: str
    xy: tuple[float, float]
    yaw: float


def load_station(root: Path, profile: dict, graph: RouteGraph) -> Station | None:
    """직접 실행 등 기존 환경은 유지한다. 미설정 환경의 복귀 요청만 거절한다."""
    if not profile.get('station_config'):
        return None
    data = read_mapping(resolve_file(root, profile['station_config']))
    if data.get('map_id') != profile['map_id']:
        raise ValueError('스테이션과 환경 map_id 불일치')
    value = data['stations'][profile['robot_id']]
    name, xy, yaw = value['station_id'], tuple(value['xy_m']), value['yaw_rad']
    if (not isinstance(name, str) or not name.strip() or len(xy) != 2
            or any(isinstance(v, bool) or not isinstance(v, (float, int)) or not math.isfinite(v)
                   for v in (*xy, yaw))):
        raise ValueError('스테이션 ID·XY·yaw가 유효하지 않습니다.')
    if value['node_id'] not in graph.nodes or math.dist(graph.nodes[value['node_id']], xy) > 1e-6:
        raise ValueError('스테이션 위치와 경로 노드가 다릅니다.')
    if not any(edge.start == value['node_id'] for edge in graph.edges):
        raise ValueError('스테이션에서 출발하는 지정 경로가 없습니다.')
    return Station(name, xy, yaw)


class StationReturn:
    def __init__(self, node: Any, *, root: Path, profile: dict, settings: Any,
                 poses: Any, motion: Any, callbacks: Any, handoff: ActionHandoff,
                 unavailable: Callable[[], bool], block: Callable[[], None],
                 prepare: Callable[[Callable[[], None]], None] | None = None,
                 tag_control: Any = None) -> None:
        self._node, self._profile, self._handoff = node, profile, handoff
        self._unavailable, self._block, self._prepare = unavailable, block, prepare
        self._poses, self._tag_control = poses, tag_control
        self._tag_active = False
        self._tag_section = None
        self._next_tag_update = 0.0
        self._settings = settings
        self._handle = self._token = None
        self._graph = RouteGraph(profile['route_graph']) if profile.get('route_graph') else None
        self._station = load_station(root, profile, self._graph) if self._graph else None
        if self._station is None:
            node.get_logger().warning(
                'STATION_RETURN_NOT_CONFIGURED: 스테이션 위치·복귀 경로 추가 처리가 필요합니다. '
                '현재 환경의 복귀 요청은 거절합니다.')
        # 작업 구간 전용 평행 접근 대신 스테이션 출발 경로를 역순으로 후진한다.
        settings = replace(settings, mode='follow_path', parallel_approach=False, controller_id='StationReverse')
        self._client = Nav2Client(node, settings, callbacks) if self._graph else None
        self._navigator = (Navigator(node, settings, self._client, poses, motion, self._check,
                                    self._graph) if self._graph else None)
        self._server = ActionServer(node, ReturnToStation, 'return_to_station',
            execute_callback=self.execute, goal_callback=self.accept,
            cancel_callback=lambda _: CancelResponse.ACCEPT, callback_group=callbacks)

    def accept(self, goal: Any) -> GoalResponse:
        if (self._station is None or self._unavailable() or not goal.task_id.strip()
                or goal.robot_id != self._profile.get('robot_id')
                or goal.map_id != self._profile.get('map_id')
                or goal.station_id != self._station.station_id):
            self._node.get_logger().warning('ReturnToStation 거절: 환경·스테이션·로봇 상태 확인 필요')
            return GoalResponse.REJECT
        return (GoalResponse.ACCEPT if self._handoff.reserve('return', goal.task_id)
                else GoalResponse.REJECT)

    def _external_check(self, handle: Any) -> None:
        if handle.is_cancel_requested or not rclpy.ok():
            raise ActionInterrupted('복귀 취소/종료 요청')
        if self._unavailable():
            raise RuntimeError('이전 동작 종료 또는 로봇 주행 준비 확인 필요')

    def _cancel_check(self) -> None:
        self._external_check(self._handle)
        if self._token.interrupted.is_set():
            raise ActionInterrupted('새 작업 요청으로 복귀 중단')

    def _check(self) -> None:
        self._cancel_check()
        if not self._tag_active or self._tag_control is None or time.monotonic() < self._next_tag_update:
            return
        self._next_tag_update = time.monotonic() + .2
        current = self._poses.current(self._cancel_check)
        section = self._graph.section_at((float(current[0,3]), float(current[1,3])),
            math.atan2(current[1,0], current[0,0]), self._settings.max_start_distance_m,
            self._settings.heading_tolerance_rad)
        if section != self._tag_section:
            self._tag_control.begin(section)
            self._tag_section = section

    def _feedback(self, handle: Any) -> None:
        value = ReturnToStation.Feedback()
        for name in ('robot_id', 'task_id', 'station_id'):
            setattr(value, name, getattr(handle.request, name))
        value.phase, value.docked, value.timestamp = 'RETURNING', False, timestamp()
        handle.publish_feedback(value)

    def execute(self, handle: Any) -> Any:
        goal = handle.request
        result = ReturnToStation.Result()
        for name in ('robot_id', 'task_id', 'station_id'):
            setattr(result, name, getattr(goal, name))
        result.docked = False  # 실패·취소 및 실물의 별도 도킹 미완료 상태.
        result.result_code, result.error_code = 'FAILED', 'RETURN_FAILED'
        acquired = False
        timer = None
        try:
            token = self._handoff.acquire('return', goal.task_id, lambda: self._external_check(handle))
            self._handle, self._token, acquired = handle, token, True
            self._check()
            self._node.get_logger().info(
                f'스테이션 복귀 시작: task_id={goal.task_id}, station_id={goal.station_id}')
            self._feedback(handle)
            timer = self._node.create_timer(1., lambda: self._feedback(handle))
            if self._prepare is not None:
                # 수확 인계·운송 분류장 완료 등 로봇별 조건은 이 경계에서 구현한다.
                self._prepare(self._check)
            self._check()
            self._navigator.preflight_navigation()
            current = self._poses.current(self._check)
            # 가상 출발은 스테이션, 가상 목적지는 작업 목표가 아닌 현재 실측 위치다.
            forward = self._graph.plan(self._station.xy,
                (float(current[0,3]), float(current[1,3])),
                self._settings.max_goal_distance_m, self._settings.max_start_distance_m)
            backward = replace(forward, plan_id=uuid.uuid4().hex,
                points=tuple(reversed(forward.points)), edge_ids=tuple(reversed(forward.edge_ids)))
            if self._tag_control is not None:
                self._tag_control.begin()
                self._tag_section = None
                self._tag_active = True
                self._next_tag_update = 0.0
            self._navigator.navigate(self._station.xy, self._station.yaw,
                route_plan=backward, reverse=True)
            self._check()
            result.result_code, result.error_code = 'SUCCESS', 'NONE'
        except ActionInterrupted as error:
            result.result_code, result.error_code, result.error_message = 'CANCELED', 'NONE', str(error)
        except Exception as error:
            result.error_message = str(error)
        finally:
            if timer is not None:
                self._node.destroy_timer(timer)
            if acquired:
                self._tag_active = False
                if self._tag_control is not None:
                    self._tag_control.end()
                try:
                    self._navigator.cancel_nav()
                except Exception as error:
                    self._block()
                    result.result_code, result.error_code = 'FAILED', 'CANCEL_UNCONFIRMED'
                    result.error_message = str(error)
            result.timestamp = timestamp()
            # 서버 선점에는 ROS CANCELING 전이가 없으므로 ABORTED + CANCELED payload를 쓴다.
            if result.result_code == 'SUCCESS':
                # 시뮬은 별도 도킹 없이 스테이션 복귀 성공을 도킹 완료로 처리한다.
                result.docked = self._profile.get('mode') == 'sim'
                handle.succeed()
            elif result.result_code == 'CANCELED' and handle.is_cancel_requested:
                handle.canceled()
            else:
                handle.abort()
            self._node.get_logger().info(
                f'스테이션 복귀 종료: task_id={goal.task_id}, result={result.result_code}, '
                f'error={result.error_code}, detail={result.error_message}')
            self._handle = self._token = None
            self._handoff.release('return', goal.task_id)
        return result

    def close(self) -> None:
        self._server.destroy()
        if self._client is not None:
            self._client.close()
