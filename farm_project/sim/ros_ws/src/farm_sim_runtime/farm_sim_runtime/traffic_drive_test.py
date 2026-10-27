"""공동 교통 시험용 진입점. 기존 소유권·계획기·Nav2·교통 클라이언트를 사용한다."""
from __future__ import annotations

import math
import threading
from typing import Any, Callable

import rclpy
from rclpy.action import ActionServer, CancelResponse, GoalResponse
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.clock import Clock, ClockType
from farm_interfaces.action import NavigateToNode
from farm_navigation.navigator import Navigator


class TestCanceled(Exception):
    """이 시험 Goal의 취소 요청."""


class TrafficDriveTest:
    def __init__(self, node: Any, profile: dict, settings: Any, client: Any,
                 poses: Any, motion: Any, handoff: Any, *,
                 unavailable: Callable[[], bool], block: Callable[[], None],
                 record: Callable[[dict], None]) -> None:
        if profile['mode'] != 'sim' or node._traffic is None:
            raise ValueError('교통 시험 서버는 교통 활성 시뮬에서만 실행합니다.')
        self.node, self.traffic, self.handoff = node, node._traffic, handoff
        self.unavailable, self.block = unavailable, block
        self.map_id = profile['map_id']
        self.record = record
        self.graph = self.traffic.registry.graph
        self.goal = None
        self.state_lock = threading.Lock()
        self.cancel_requested = False
        self.finishing = False
        self.phase = ''
        self.poses = poses
        self.navigator = Navigator(node, settings, client, poses, motion, self.check,
                                   self.graph, record=record)
        self.server = ActionServer(node, NavigateToNode, 'traffic_test/navigate_to_node',
            execute_callback=self.execute, goal_callback=self.accept,
            cancel_callback=self.cancel,
            callback_group=ReentrantCallbackGroup(), result_timeout=3600)
        self.timer = node.create_timer(.2, self.feedback,
            clock=Clock(clock_type=ClockType.STEADY_TIME), callback_group=ReentrantCallbackGroup())

    def all_ready(self) -> bool:
        """현재 관제의 양 로봇 등록과 자기 위치 정합이 모두 준비돼야 한다."""
        with self.traffic.lock:
            control = self.traffic.control
            if not self.traffic.ready or control is None:
                return False
            for robot_id in ('scout_01', 'harvest_01'):
                registrations = [r for r in control.robots if r.robot_id == robot_id]
                if len(registrations) != 1:
                    return False
                r = registrations[0]
                if r.registration_state != 'REGISTERED' or not r.boot_id or not r.sync_id or r.accepted_status_sequence <= 0:
                    return False
            return True

    def accept(self, request: Any) -> GoalResponse:
        if (not request.task_id.strip() or request.map_id != self.map_id
                or request.target_node_id not in self.traffic.registry.nodes
                or self.unavailable() or not self.all_ready()):
            return GoalResponse.REJECT
        # 일반 작업/복귀/인계와 동일 소유권. 시험이 일반 작업을 선점하지 않는다.
        if not self.handoff.reserve('traffic_test', request.task_id, preempt=False, interruptible=False):
            return GoalResponse.REJECT
        with self.state_lock:
            self.cancel_requested = self.finishing = False
        return GoalResponse.ACCEPT

    def cancel(self, goal: Any) -> CancelResponse:
        with self.state_lock:
            if self.finishing:
                return CancelResponse.REJECT
            self.cancel_requested = True
            return CancelResponse.ACCEPT

    def check(self) -> None:
        if self.cancel_requested or (self.goal is not None and self.goal.is_cancel_requested):
            raise TestCanceled('교통 주행 시험 취소')
        if self.unavailable() or not rclpy.ok():
            raise RuntimeError('교통 주행 시험 중 로봇 종료/복구 필요')
        self.traffic.check_work()

    def execute(self, goal: Any) -> NavigateToNode.Result:
        request = goal.request
        result = NavigateToNode.Result(result_code='FAILED', error_code='NAVIGATION_FAILED')
        self.goal = goal
        try:
            self.traffic.begin_task()
            self.handoff.acquire('traffic_test', request.task_id, lambda: None)
            self.check()
            if not self.all_ready():
                raise RuntimeError('교통 등록 READY 변경')
            self.phase = 'PLANNING'
            goal.publish_feedback(NavigateToNode.Feedback(phase=self.phase))
            self.navigator.preflight_navigation()
            target = self.graph.nodes[self.traffic.registry.nodes[request.target_node_id]]
            plan = self.navigator.plan(target)
            current = self.poses.current(self.check)
            yaw = (math.atan2(plan.points[-1][1]-plan.points[-2][1],
                              plan.points[-1][0]-plan.points[-2][0]) if len(plan.points) > 1
                   else math.atan2(current[1, 0], current[0, 0]))
            # Nav2Client가 전체 경로를 Acquire하고 대기/재탐색한다. 허가 없이 실행하지 않는다.
            arrival = self.navigator.navigate(target, yaw, route_plan=plan)
            if not arrival.measurement['accepted']:
                raise RuntimeError('시험 목표 도착 오차 초과: ' + str(arrival.measurement))
            self.traffic.wait_position_report(arrival.stamp_ns, self.check,
                                              self.traffic.settings.settle_timeout_s)
            self.check()
            self.traffic.finish_task(request.task_id, self.traffic.settings.cancel_timeout_s)
            with self.state_lock:
                self.check()
                self.finishing = True
                result.result_code, result.error_code = 'SUCCESS', 'NONE'
                goal.succeed()
        except Exception as error:
            result.error_message = str(error)
            try:
                self.navigator.cancel_nav()
                self.traffic.finish_task(request.task_id, self.traffic.settings.cancel_timeout_s)
            except Exception as cleanup_error:
                self.block()
                with self.state_lock:
                    self.finishing = True
                result.error_code = 'CANCEL_UNCONFIRMED'
                result.error_message += '; 정지/허가 정리 미확인: ' + str(cleanup_error)
                goal.abort()
            else:
                with self.state_lock:
                    self.finishing = True
                    canceled = self.cancel_requested or goal.is_cancel_requested
                if canceled:
                    result.result_code, result.error_code = 'CANCELED', 'NONE'
                    goal.canceled()
                else:
                    goal.abort()
        finally:
            entry = dict(event='TRAFFIC_DRIVE_RESULT', task_id=request.task_id,
                         target_node_id=request.target_node_id, result_code=result.result_code,
                         error_code=result.error_code, error_message=result.error_message)
            # 기록 실패가 이미 확정한 Action 결과/소유권 정리를 방해하지 않게 한다.
            try:
                self.record(entry)
                logger = self.node.get_logger()
                (logger.info if result.result_code == 'SUCCESS' else logger.warning)(str(entry))
            except Exception as log_error:
                self.node.get_logger().error(f'교통 시험 기록 실패: {log_error}')
            finally:
                self.goal = None
                self.handoff.release('traffic_test', request.task_id)
        return result

    def feedback(self) -> None:
        goal = self.goal
        if goal is None or not goal.is_active:
            return
        with self.traffic.lock:
            phase = 'MOVING' if self.traffic.moving else 'PLANNING'
        if phase != self.phase:
            self.phase = phase
            goal.publish_feedback(NavigateToNode.Feedback(phase=phase))

    def close(self) -> None:
        self.node.destroy_timer(self.timer)
        self.server.destroy()
