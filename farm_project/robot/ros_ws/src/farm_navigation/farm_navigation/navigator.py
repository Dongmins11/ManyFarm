"""로봇 공통 이동 창구. 계획과 실행을 분리하며 미션이나 작업 상태를 소유하지 않습니다."""
from __future__ import annotations
from collections.abc import Callable, Sequence
from typing import Any
from dataclasses import asdict
from datetime import datetime, timezone
import threading
import uuid
import math
from rclpy.node import Node
from .navigation_types import NavigationSettings, NavigationStatus, NavigationResult, RoutePlan
from .nav2_client import Nav2Client
from .pose_provider import PoseProvider
from .motion_monitor import MotionMonitor
from .route import RouteGraph
from .path_builder import build_path
from .parallel_approach import select_corridor, inside_corridor, straight_plan
from .arrival import measure_arrival, arrival_description, ArrivalValidationError


class Navigator:
    def __init__(self, node: Node, settings: NavigationSettings, client: Nav2Client,
                 poses: PoseProvider | None, motion: MotionMonitor, check: Callable[[],None],
                 graph: RouteGraph | None = None,
                 record: Callable[[dict[str,Any]],None] | None = None,
                 route_planner: Any = None, *,
                 explicit_routes: bool = False,
                 stop_output: Callable[[], None] | None = None,
                 settling_check: Callable[[], None] | None = None,
                 arrival_validator: Callable[[int, Callable[[], None]], dict[str, Any]] | None = None) -> None:
        self._node=node
        self._settings=settings
        self._client=client
        self._poses=poses
        self._motion=motion
        self._check=check
        self._graph=graph
        self._route_planner=route_planner
        self._record=record
        self._explicit_routes=explicit_routes
        self._stop_output=stop_output
        self._settling_check=settling_check or check
        self._arrival_validator=arrival_validator
        if (stop_output is not None or arrival_validator is not None or settling_check is not None) and not explicit_routes:
            raise ValueError('출력 차단·별도 완료 판정은 명시적 경로 실행에서만 지정합니다.')
        if explicit_routes and (settings.mode != 'follow_path' or settings.parallel_approach
                                or graph is not None or route_planner is not None):
            raise ValueError('명시적 경로 실행에는 그래프·평행 접근을 함께 지정하지 않습니다.')
        if poses is None and (arrival_validator is None or settings.tf_recovery_enabled or settings.collision_retry_count):
            raise ValueError('TF 위치 조회 또는 명시적 완료 판정기가 필요합니다.')
        if settings.tf_recovery_enabled or settings.collision_retry_count:
            client.set_recovery_probe(lambda: poses.recovery_ready() and motion.stationary_now())
        self._lock=threading.Lock()
        self._status=NavigationStatus()
        self._needs_stop_confirmation=False
        if settings.mode=='follow_path' and graph is None and route_planner is None and not explicit_routes:
            raise ValueError('follow_path 모드에는 경로 그래프가 필요합니다.')

    @property
    def status(self) -> NavigationStatus:
        """읽기 전용 스냅샷. 교통 대기·진행 보고는 추후 이 경계에 연결합니다."""
        return self._status

    def preflight_navigation(self) -> dict[str,Any]:
        return self._client.preflight(self._check)

    def plan(self, xy: tuple[float,float]) -> RoutePlan | None:
        """명령을 보내지 않고 경로만 계산합니다. pose 모드는 Nav2가 계획합니다."""
        self._check()
        if self._settings.mode=='navigate_to_pose': return None
        if self._explicit_routes: raise ValueError('호출자가 계산한 RoutePlan이 필요합니다.')
        actual=self._poses.current(self._check)
        if self._route_planner is not None:
            return self._route_planner.plan((float(actual[0,3]),float(actual[1,3])),xy,self._check)
        assert self._graph is not None
        return self._graph.plan((float(actual[0,3]),float(actual[1,3])),xy,
                                self._settings.max_start_distance_m,self._settings.max_goal_distance_m)

    def navigate(self, xy: Sequence[float], yaw: float, *,
                 route_plan: RoutePlan | None = None, reverse: bool = False) -> NavigationResult:
        """I/O 작업 스레드에서 호출합니다. State enter에서 직접 기다리지 않습니다."""
        if not self._lock.acquire(blocking=False):
            raise RuntimeError('이미 이동 요청을 처리 중입니다.')
        request_id=uuid.uuid4().hex
        plan_id=''
        entry: dict[str,Any] = {}
        try:
            self._check()
            if self._needs_stop_confirmation or self._client.has_goal:
                raise RuntimeError('이전 이동의 종료·정지 확인이 필요합니다.')
            if len(xy)!=2 or not all(math.isfinite(float(v)) for v in (*xy,yaw)):
                raise ValueError('유효한 목표 XY·yaw가 필요합니다.')
            target=(float(xy[0]),float(xy[1]))
            self._status=NavigationStatus(request_id,'PLANNING')
            entry={'request_id':request_id,'goal_map':{'x':target[0],'y':target[1],'yaw':float(yaw)},
                   'mode':self._settings.mode,'status':'PLANNING','started_at':datetime.now(timezone.utc).isoformat()}
            if self._record is not None: self._record(entry)
            if reverse and (route_plan is None or self._settings.mode != 'follow_path'):
                raise ValueError('후진 실행에는 명시적 FollowPath 경로가 필요합니다.')
            if self._explicit_routes and route_plan is None:
                raise ValueError('명시적 RoutePlan 누락')
            plan = route_plan
            if route_plan is not None:
                if (route_plan.frame_id != self._settings.map_frame or not route_plan.points
                        or math.dist(route_plan.points[-1], target) > 1e-6):
                    raise ValueError('제공 경로의 좌표계·종점 불일치')
            elif self._settings.parallel_approach:
                if self._settings.mode != 'follow_path':
                    raise ValueError('평행 접근은 follow_path 모드에서만 지원합니다.')
                current = self._poses.current(self._check)
                measured = measure_arrival(current, target, yaw, self._settings.arrival_tolerance_m, self._settings.heading_tolerance_rad)
                if measured['accepted']:
                    self._needs_stop_confirmation = True
                    stamp = self._motion.wait_stopped(self._check)
                    current = self._poses.lookup(self._settings.map_frame, self._settings.base_frame, stamp, self._check)
                    measured = measure_arrival(current, target, yaw, self._settings.arrival_tolerance_m, self._settings.heading_tolerance_rad)
                    if not measured['accepted']:
                        self._node.get_logger().warning('정지 후 도착 오차 기록: '+arrival_description(measured))
                    entry.update(measured, status='ARRIVED', already_arrived=True, stamp_ns=stamp)
                    self._needs_stop_confirmation = False
                    self._status = NavigationStatus(request_id, 'ARRIVED')
                    return NavigationResult(request_id, '', stamp, measured)
                corridor = select_corridor(self._graph.parallel_corridors, target, yaw, self._settings.heading_tolerance_rad)
                xy = (float(current[0,3]), float(current[1,3]))
                # 다른 좁은 구간에서 방향을 바꾸는 자동 복구도 허용하지 않는다.
                occupied = [c for c in self._graph.parallel_corridors if inside_corridor(c, xy, self._settings.max_start_distance_m)]
                if occupied and corridor not in occupied:
                    if len(occupied) != 1:
                        raise RuntimeError('APPROACH_RECOVERY_REQUIRED: 작업 구간 중복')
                    old = occupied[0]
                    template = RoutePlan(uuid.uuid4().hex, self._graph.revision, self._graph.frame, (), (), 0.)
                    exit_plan = straight_plan(template, old, xy, math.atan2(current[1,0],current[0,0]), tuple(old['exit']),
                        self._settings.arrival_tolerance_m, self._settings.heading_tolerance_rad)
                    entry['exit_route'] = asdict(exit_plan)
                    self._needs_stop_confirmation = True
                    self._client.execute(tuple(old['exit']), old['yaw'], build_path(exit_plan, old['yaw'],
                        self._node.get_clock().now().to_msg(), self._settings.path_spacing_m), self._check)
                    stamp = self._motion.wait_stopped(self._check)
                    current = self._poses.lookup(self._settings.map_frame, self._settings.base_frame, stamp, self._check)
                    gate = measure_arrival(current, old['exit'], old['yaw'], self._settings.arrival_tolerance_m, self._settings.heading_tolerance_rad)
                    entry['exit_arrival'] = gate
                    if not gate['accepted']:
                        self._node.get_logger().warning('이탈 정지 후 도착 오차 기록: '+arrival_description(gate))
                    occupied = []
                if not occupied:
                    approach = self.plan(tuple(corridor['entry']))
                    entry['approach_route'] = asdict(approach)
                    self._needs_stop_confirmation = True
                    self._client.execute(tuple(corridor['entry']), corridor['yaw'],
                        build_path(approach, corridor['yaw'], self._node.get_clock().now().to_msg(), self._settings.path_spacing_m), self._check)
                    stamp = self._motion.wait_stopped(self._check)
                    current = self._poses.lookup(self._settings.map_frame, self._settings.base_frame, stamp, self._check)
                    gate = measure_arrival(current, corridor['entry'], corridor['yaw'], self._settings.arrival_tolerance_m, self._settings.heading_tolerance_rad)
                    entry['approach_arrival'] = gate
                    if not gate['accepted']:
                        self._node.get_logger().warning('진입 정지 후 도착 오차 기록: '+arrival_description(gate))
                    xy = (float(current[0,3]), float(current[1,3]))
                template = RoutePlan(uuid.uuid4().hex, self._graph.revision, self._graph.frame, (), (), 0.)
                plan = straight_plan(template, corridor, xy, math.atan2(current[1,0],current[0,0]), target,
                    self._settings.arrival_tolerance_m, self._settings.heading_tolerance_rad)
            else:
                plan=self.plan(target)
            path=None
            if plan is not None:
                plan_id=plan.plan_id
                entry['route']=asdict(plan)
                path=build_path(plan,yaw,self._node.get_clock().now().to_msg(),self._settings.path_spacing_m, reverse=reverse)
                entry['reverse']=reverse
            # 향후 허가를 연결할 때 이 실행 경계를 사용합니다. 현재는 교통 기능 없음.
            self._check()
            self._status=NavigationStatus(request_id,'MOVING',plan_id)
            entry['status']='MOVING'
            self._needs_stop_confirmation=True
            entry['nav2_status']=self._client.execute(target,yaw,path,self._check)
            self._status=NavigationStatus(request_id,'SETTLING',plan_id)
            entry['status']='SETTLING'
            if self._stop_output is not None: self._stop_output()
            stamp=self._motion.wait_stopped(self._settling_check)
            if self._arrival_validator is None:
                transform=self._poses.lookup(self._settings.map_frame,self._settings.base_frame,stamp,self._check)
                measured=measure_arrival(transform,target,yaw,self._settings.arrival_tolerance_m,self._settings.heading_tolerance_rad)
            else:
                measured=self._arrival_validator(stamp,self._settling_check)
            entry.update(measured,stamp_ns=stamp,finished_at=datetime.now(timezone.utc).isoformat())
            if self._arrival_validator is not None and measured.get('accepted') is not True:
                raise ArrivalValidationError(measured, stamp)
            # 잔여 자세 오차는 진단값이다. 완료·정지가 확인된 이동의 다음 출발을 막지 않는다.
            if not measured['accepted']:
                self._node.get_logger().warning('정지 후 도착 오차 기록: '+arrival_description(measured))
            self._needs_stop_confirmation=False
            self._status=NavigationStatus(request_id,'ARRIVED',plan_id)
            entry['status']='ARRIVED'
            return NavigationResult(request_id,plan_id,stamp,measured)
        except BaseException as error:
            # 실패 즉시 릴레이를 닫는다. Goal 취소·정지 확인 책임은 cancel_nav에 남긴다.
            if self._needs_stop_confirmation and self._stop_output is not None:
                try: self._stop_output()
                except Exception as stop_error: entry['stop_output_error']=str(stop_error)
            self._status=NavigationStatus(request_id,'INTERRUPTED',plan_id,str(error))
            entry.update(status='INTERRUPTED',error=str(error))
            # 목표 실행 또는 종료 확인 실패 때 Goal/정지 플래그를 유지합니다.
            raise
        finally:
            self._lock.release()

    def cancel_nav(self) -> None:
        """진행 I/O가 반환한 뒤 호출합니다. 취소는 일시정지/재개 구현이 아닙니다."""
        if not self._lock.acquire(blocking=False):
            raise RuntimeError('진행 중 I/O가 취소를 확인하고 반환한 뒤 정리해야 합니다.')
        try:
            if self._route_planner is not None:
                self._route_planner.cancel()
            stop_error=None
            if self._needs_stop_confirmation and self._stop_output is not None:
                try:self._stop_output()
                except Exception as error:stop_error=error
            # 출력 차단 콜백 실패가 자신의 Goal 취소까지 건너뛰게 하지 않는다.
            self._client.cancel()
            if self._needs_stop_confirmation:
                self._status=NavigationStatus(self._status.request_id,'STOPPING',self._status.plan_id)
                self._motion.wait_stopped(lambda: None)
                if stop_error is not None:raise stop_error
                self._needs_stop_confirmation=False
                self._status=NavigationStatus(self._status.request_id,'STOPPED',self._status.plan_id)
        finally:
            self._lock.release()

    def stationary_epoch(self) -> int | None:
        return self._motion.stationary_epoch()

    def stationary_now(self) -> bool:
        return self._motion.stationary_now()
