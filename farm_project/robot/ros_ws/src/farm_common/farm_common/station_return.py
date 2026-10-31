"""환경별 스테이션으로 향하는 공통 Action. 작업 의미는 로봇의 준비 콜백에 둔다."""
from __future__ import annotations
from farm_navigation.operation_clock import operation_time

from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import datetime, timezone
import math
import json
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
from farm_navigation.navigation_types import NavigationSettings, RoutePlan
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


def plan_station_return(graph: RouteGraph, station: Station, xy: tuple[float, float],
                        yaw: float, settings: NavigationSettings) -> tuple[RoutePlan, bool, dict]:
    """방향 그래프의 전진/역순 후진 경로 중 짧은 것을 선택한다. 장애물 검사는 Nav2가 한다."""
    if not all(math.isfinite(v) for v in (*xy, yaw)):
        raise ValueError('복귀 출발 위치·방향이 유효하지 않습니다.')
    candidates, audit = [], {}
    for reverse in (False, True):
        name = 'reverse' if reverse else 'forward'
        try:
            if reverse:
                outward = graph.plan(station.xy, xy, settings.max_goal_distance_m,
                                     settings.max_start_distance_m)
                plan = replace(outward, plan_id=uuid.uuid4().hex,
                               points=tuple(reversed(outward.points)),
                               edge_ids=tuple(reversed(outward.edge_ids)))
            else:
                plan = graph.plan(xy, station.xy, settings.max_start_distance_m,
                                  settings.max_goal_distance_m)
        except ValueError as error:
            audit[name] = dict(available=False, reason=str(error))
            continue
        # 현재 위치에서 그래프까지의 짧은 횡방향 투영선을 주행 방향으로 오인하지 않는다.
        ahead = next((p for p in plan.points[1:] if math.dist(xy, p) > settings.max_start_distance_m),
                     plan.points[-1])
        heading = (math.atan2(ahead[1]-xy[1], ahead[0]-xy[0]) + (math.pi if reverse else 0.)
                   if math.dist(xy, ahead) > settings.arrival_tolerance_m else station.yaw)
        error = abs(math.remainder(heading-yaw, 2*math.pi))
        audit[name] = dict(available=True, distance_m=plan.distance_m, start_heading_error_rad=error)
        # 기존 StationReverse가 거절하는 앞쪽 경로를 짧다는 이유로 선택하지 않는다.
        # 제어기의 pi/2+0.1 조건과 동일하며 그 조건을 완화하지 않는다.
        if reverse and error > math.pi/2 + .1:
            audit[name].update(available=False, reason='reverse_start_heading_incompatible')
            continue
        candidates.append((plan, reverse, error))
    if not candidates:
        raise ValueError('실행 가능한 스테이션 복귀 경로 없음: '+json.dumps(audit, ensure_ascii=False))
    # 거리 동률(부동소수점 잡음 제외)은 초기 방향 정렬량으로 결정한다.
    plan, reverse, _ = min(candidates, key=lambda c: (round(c[0].distance_m, 6), c[2], c[1]))
    audit.update(selected='reverse' if reverse else 'forward', points=plan.points,
                 final_yaw_rad=station.yaw)
    return plan, reverse, audit


class StationReturn:
    def __init__(self, node: Any, *, root: Path, profile: dict, settings: Any,
                 poses: Any, motion: Any, callbacks: Any, handoff: ActionHandoff,
                 unavailable: Callable[[], bool], block: Callable[[], None],
                 prepare: Callable[[Callable[[], None]], None] | None = None,
                 tag_control: Any = None,
                 client_factory: Callable[..., Any] | None = None) -> None:
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
        # 기존 후진 제어는 보존하고 전진은 일반 RPP의 도착 후 방향 정렬까지 사용한다.
        reverse_settings = replace(settings, mode='follow_path', parallel_approach=False, controller_id='StationReverse')
        forward_settings = replace(settings, mode='follow_path', parallel_approach=False, controller_id='RPP')
        self._client = (client_factory or Nav2Client)(node, reverse_settings, callbacks) if self._graph else None
        self._navigator = (Navigator(node, reverse_settings, self._client, poses, motion, self._check,
                                    self._graph) if self._graph else None)
        self._forward_client = (client_factory or Nav2Client)(node, forward_settings, callbacks) if self._graph else None
        self._forward_navigator = (Navigator(node, forward_settings, self._forward_client, poses, motion,
                                            self._check, self._graph) if self._graph else None)
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
        if not self._tag_active or self._tag_control is None or operation_time(self._node) < self._next_tag_update:
            return
        self._next_tag_update = operation_time(self._node) + .2
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

    def _run_mission(self) -> None:
        """기존 복귀 경로는 유지하며 수확 업무 컴포넌트의 조립 경계를 제공한다."""
        if self._prepare is not None:
            # 수확 인계·운송 분류장 완료 등 로봇별 조건은 이 경계에서 구현한다.
            self._prepare(self._check)
        self._check()
        current = self._poses.current(self._check)
        plan, reverse, audit = plan_station_return(self._graph, self._station,
            (float(current[0,3]), float(current[1,3])),
            math.atan2(current[1,0], current[0,0]), self._settings)
        self._node.get_logger().info('STATION_RETURN_PLAN: '+json.dumps(audit, ensure_ascii=False))
        navigator = self._navigator if reverse else self._forward_navigator
        self._active_navigator = navigator
        navigator.preflight_navigation()
        if self._tag_control is not None:
            self._tag_control.begin()
            self._tag_section = None
            self._tag_active = True
            self._next_tag_update = 0.0
        # 전진도 위치 도착만으로 성공하지 않는다. 스테이션 yaw(통상180도 회전)까지
        # RPP가 충돌 검사하며 정렬한 뒤 기존 Navigator의 정지 확인을 통과해야 한다.
        navigator.navigate(self._station.xy, self._station.yaw,
            route_plan=plan, reverse=reverse)
        self._check()

    def _cleanup_mission(self) -> None:
        """태그 종료가 실패해도 선택한 주행 Goal의 정리를 반드시 시도한다."""
        self._tag_active = False
        try:
            if self._tag_control is not None:
                self._tag_control.end()
        finally:
            getattr(self, '_active_navigator', self._navigator).cancel_nav()

    def _mission_docked(self) -> bool:
        """기존 시뮬 스테이션 위치·방향·정지 완료 계약을 유지한다."""
        return self._profile.get('mode') == 'sim'

    def execute(self, handle: Any) -> Any:
        goal = handle.request
        result = ReturnToStation.Result()
        for name in ('robot_id', 'task_id', 'station_id'):
            setattr(result, name, getattr(goal, name))
        result.docked = False  # 실패·취소 및 실물의 별도 도킹 미완료 상태.
        result.result_code, result.error_code = 'FAILED', 'RETURN_FAILED'
        acquired = False
        timer = None
        self._active_navigator = self._navigator
        try:
            token = self._handoff.acquire('return', goal.task_id, lambda: self._external_check(handle))
            self._handle, self._token, acquired = handle, token, True
            self._check()
            self._node.get_logger().info(
                f'스테이션 복귀 시작: task_id={goal.task_id}, station_id={goal.station_id}')
            self._feedback(handle)
            timer = self._node.create_timer(1., lambda: self._feedback(handle))
            self._run_mission()
            result.result_code, result.error_code = 'SUCCESS', 'NONE'
        except ActionInterrupted as error:
            result.result_code, result.error_code, result.error_message = 'CANCELED', 'NONE', str(error)
        except Exception as error:
            result.error_message = str(error)
        finally:
            if timer is not None:
                self._node.destroy_timer(timer)
            if acquired:
                try:
                    self._cleanup_mission()
                except Exception as error:
                    self._block()
                    result.result_code, result.error_code = 'FAILED', 'CANCEL_UNCONFIRMED'
                    result.error_message = str(error)
            result.timestamp = timestamp()
            # 서버 선점에는 ROS CANCELING 전이가 없으므로 ABORTED + CANCELED payload를 쓴다.
            if result.result_code == 'SUCCESS':
                # 시뮬은 별도 도킹 없이 스테이션 복귀 성공을 도킹 완료로 처리한다.
                result.docked = self._mission_docked()
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
        if self._forward_client is not None:
            self._forward_client.close()
