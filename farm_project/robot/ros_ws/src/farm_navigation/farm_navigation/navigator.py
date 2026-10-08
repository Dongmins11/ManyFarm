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
from .arrival import measure_arrival, arrival_description


class Navigator:
    def __init__(self, node: Node, settings: NavigationSettings, client: Nav2Client,
                 poses: PoseProvider, motion: MotionMonitor, check: Callable[[],None],
                 graph: RouteGraph | None = None,
                 record: Callable[[dict[str,Any]],None] | None = None,
                 route_planner: Any = None) -> None:
        self._node=node
        self._settings=settings
        self._client=client
        self._poses=poses
        self._motion=motion
        self._check=check
        self._graph=graph
        self._route_planner=route_planner
        self._record=record
        self._lock=threading.Lock()
        self._status=NavigationStatus()
        self._needs_stop_confirmation=False
        if settings.mode=='follow_path' and graph is None and route_planner is None:
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
        actual=self._poses.current(self._check)
        if self._route_planner is not None:
            return self._route_planner.plan((float(actual[0,3]),float(actual[1,3])),xy,self._check)
        assert self._graph is not None
        return self._graph.plan((float(actual[0,3]),float(actual[1,3])),xy,
                                self._settings.max_start_distance_m,self._settings.max_goal_distance_m)

    def navigate(self, xy: Sequence[float], yaw: float) -> NavigationResult:
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
            plan = None
            if self._settings.parallel_approach:
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
                        raise RuntimeError('도착 재검사 실패: '+arrival_description(measured))
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
                        raise RuntimeError('작업 구간 이탈 실패: '+arrival_description(gate))
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
                        raise RuntimeError('진입 정렬 실패: '+arrival_description(gate))
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
                path=build_path(plan,yaw,self._node.get_clock().now().to_msg(),self._settings.path_spacing_m)
            # 향후 허가를 연결할 때 이 실행 경계를 사용합니다. 현재는 교통 기능 없음.
            self._check()
            self._status=NavigationStatus(request_id,'MOVING',plan_id)
            entry['status']='MOVING'
            self._needs_stop_confirmation=True
            entry['nav2_status']=self._client.execute(target,yaw,path,self._check)
            self._status=NavigationStatus(request_id,'SETTLING',plan_id)
            entry['status']='SETTLING'
            stamp=self._motion.wait_stopped(self._check)
            transform=self._poses.lookup(self._settings.map_frame,self._settings.base_frame,stamp,self._check)
            measured=measure_arrival(transform,target,yaw,self._settings.arrival_tolerance_m,self._settings.heading_tolerance_rad)
            entry.update(measured,stamp_ns=stamp,finished_at=datetime.now(timezone.utc).isoformat())
            if not measured['accepted']:
                raise RuntimeError('도착 허용오차 초과: '+arrival_description(measured))
            self._needs_stop_confirmation=False
            self._status=NavigationStatus(request_id,'ARRIVED',plan_id)
            entry['status']='ARRIVED'
            return NavigationResult(request_id,plan_id,stamp,measured)
        except Exception as error:
            self._status=NavigationStatus(request_id,'INTERRUPTED',plan_id,str(error))
            entry.update(status='INTERRUPTED',error=str(error))
            # 종료 실패 때 새 이동을 막을 수 있도록 Goal/정지 플래그를 유지합니다.
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
            self._client.cancel()
            if self._needs_stop_confirmation:
                self._status=NavigationStatus(self._status.request_id,'STOPPING',self._status.plan_id)
                self._motion.wait_stopped(lambda: None)
                self._needs_stop_confirmation=False
                self._status=NavigationStatus(self._status.request_id,'STOPPED',self._status.plan_id)
        finally:
            self._lock.release()

    def stationary_now(self) -> bool:
        return self._motion.stationary_now()
