"""Nav2 액션 연결. 로봇 Mission/State를 모르며 자신의 Goal만 관리합니다."""
from farm_navigation.operation_clock import operation_time
from collections.abc import Callable
from typing import Any
import time
import math
from rclpy.node import Node
from rclpy.callback_groups import CallbackGroup
from rclpy.task import Future
from rclpy.action import ActionClient
from rclpy.action.client import ClientGoalHandle
from rclpy.parameter import parameter_value_to_python
from rcl_interfaces.srv import GetParameters
from nav2_msgs.action import NavigateToPose, FollowPath
from action_msgs.msg import GoalStatus
from nav_msgs.msg import Path
from geometry_msgs.msg import Twist
from .tf_recovery import run_with_tf_recovery, Nav2TFError
from .navigation_types import NavigationSettings
from .collision_recovery import Nav2ControlUnavailable, run_with_collision_recovery
from .arrival import validate_goal_checkers


class Nav2Client:
    def __init__(self, node: Node, settings: NavigationSettings, group: CallbackGroup, *, execution_clock=None,
                 retryable_control_error: Callable[[str], bool] | None = None) -> None:
        self._pause_clock_factory = execution_clock
        self._retryable_control_error = retryable_control_error
        self._node: Node = node
        self._settings: NavigationSettings = settings
        self._navigate=ActionClient(node,NavigateToPose,settings.navigate_action,callback_group=group)
        self._follow=ActionClient(node,FollowPath,settings.follow_action,callback_group=group)
        self._parameters=node.create_client(GetParameters,settings.controller_node.rstrip('/')+'/get_parameters',callback_group=group)
        self._pending: Future | None = None
        self._handle: ClientGoalHandle | None = None
        self._result: Future | None = None
        self._recovery_probe = None
        self._recovery_stop = None
        self._stop_publishers = ([node.create_publisher(Twist, topic, 10)
                                 for topic in ('cmd_vel_nav', 'cmd_vel')]
                                if settings.tf_recovery_enabled else [])
        self._last_control_feedback = 0.0
        self._nominal_linear_speed_mps: float | None = None

    @property
    def has_goal(self) -> bool:
        return self._pending is not None or self._handle is not None

    def _execution_clock(self) -> Callable[[], float]:
        """주행 경과시간: use_sim_time 활성 시 ROS 시계, 실물은 단조 실시간이다."""
        if getattr(self, '_pause_clock_factory', None) is not None:
            return self._pause_clock_factory()
        ros_clock = self._node.get_clock()
        if not ros_clock.ros_time_is_active:
            return time.monotonic
        previous = ros_clock.now().nanoseconds
        def now() -> float:
            nonlocal previous
            current = ros_clock.now().nanoseconds
            if current < previous:
                raise RuntimeError('주행 중 시뮬 시계가 역행했습니다; 요청 종료 여부 확인 필요')
            previous = current
            return current / 1e9
        return now

    def _wait(self, future: Future, timeout: float, check: Callable[[],None], *,
              clock: Callable[[], float] | None = None,
              timeout_message: str = 'Nav2 응답 시간 초과; 요청 종료 여부 확인 필요') -> Any:
        # 연결/응답/취소도 시뮬 동작 시계를 사용한다.
        clock = (lambda: operation_time(self._node)) if clock is None else clock
        deadline=clock()+timeout
        while not future.done() and clock()<deadline:
            check()
            time.sleep(.02)
        check()
        if not future.done(): raise TimeoutError(timeout_message)
        return future.result()

    def _read_parameters(self, names: list[str], check: Callable[[],None]) -> dict[str,Any]:
        req=GetParameters.Request();req.names=names
        future=self._parameters.call_async(req)
        try:
            response=self._wait(future,self._settings.response_timeout_s,check)
            if response is None or len(response.values)!=len(names): raise RuntimeError('Nav2 설정 응답 누락')
            return {name:parameter_value_to_python(value) for name,value in zip(names,response.values)}
        finally:
            if not future.done(): self._parameters.remove_pending_request(future)

    def preflight(self, check: Callable[[],None], *, wall_parameters: dict[str,Any] | None = None) -> dict[str,Any]:
        s=self._settings
        client=self._follow if s.mode=='follow_path' else self._navigate
        deadline=operation_time(self._node)+s.readiness_timeout_s
        while not client.server_is_ready() or not self._parameters.service_is_ready():
            check()
            if operation_time(self._node)>deadline: raise RuntimeError('Nav2 액션/파라미터 서버가 준비되지 않았습니다.')
            time.sleep(.05)
        names = ['goal_checker_plugins', 'controller_plugins', 'progress_checker_plugins']
        speed_parameter = f'{s.controller_id}.desired_linear_vel'
        if s.mode == 'follow_path' and wall_parameters is None:
            names.append(speed_parameter)
        values=self._read_parameters(names,check)
        speed = values.get(speed_parameter)
        self._nominal_linear_speed_mps = (float(speed) if isinstance(speed, (int, float))
            and not isinstance(speed, bool) and math.isfinite(speed) and speed > 0 else None)
        ids=values.get('goal_checker_plugins')
        if not isinstance(ids,list) or not ids: raise RuntimeError('goal_checker_plugins 누락')
        if s.mode=='follow_path':
            for name,value in [('goal_checker_plugins',s.goal_checker_id),('controller_plugins',s.controller_id),('progress_checker_plugins',s.progress_checker_id)]:
                if value not in (values.get(name) or []): raise RuntimeError(f'{name}에 {value}가 없습니다.')
            ids=[s.goal_checker_id]
        # 먼저 종류만 읽는다. 미선언 파라미터가 섞이면 실제 ROS는 전체 요청을 실패시킨다.
        values.update(self._read_parameters([f'{name}.plugin' for name in ids],check))
        standard_ids=[name for name in ids if values.get(f'{name}.plugin') in
                      ('nav2_controller::SimpleGoalChecker','nav2_controller::StoppedGoalChecker')]
        if standard_ids:
            values.update(self._read_parameters([f'{name}.{key}' for name in standard_ids
                for key in ('xy_goal_tolerance','yaw_goal_tolerance','stateful','symmetric_yaw_tolerance')],check))
        stopped_ids = [name for name in ids if values.get(f'{name}.plugin') == 'nav2_controller::StoppedGoalChecker']
        if stopped_ids:
            values.update(self._read_parameters([f'{name}.{key}' for name in stopped_ids
                for key in ('trans_stopped_velocity', 'rot_stopped_velocity')]
                + ['min_x_velocity_threshold', 'min_y_velocity_threshold', 'min_theta_velocity_threshold'], check))
        if wall_parameters is not None:
            if s.mode != 'follow_path': raise ValueError('벽 완료 판정은 명시적 FollowPath 전용입니다.')
            if values.get(f'{s.goal_checker_id}.plugin') != 'farm_wall_controller::WallGoalChecker':
                raise ValueError('선택한 벽 완료 판정기 종류 불일치')
            values.update(self._read_parameters([f'wall_alignment.{key}' for key in wall_parameters],check))
        checked=dict(values,goal_checker_plugins=ids)
        checkers=validate_goal_checkers(checked,s.arrival_tolerance_m,s.heading_tolerance_rad,
            stopped_linear_limit=s.stopped_linear_mps, stopped_angular_limit=s.stopped_angular_rps, wall_parameters=wall_parameters)
        return {'mode':s.mode,'controller_node':s.controller_node,'parameters':values,'checkers':checkers,'status':'OK'}

    def set_recovery_probe(self, probe: Callable[[], bool]) -> None:
        self._recovery_probe = probe

    def set_recovery_stop(self, stop: Callable[[], None]) -> None:
        """현재 출력 소유자가 제공하는 정지 함수. 추가 publisher를 생성하지 않는다."""
        self._recovery_stop = stop

    def _stop_for_recovery(self) -> None:
        # 자신의 Nav2 Goal이 종료된 뒤에만 호출한다. smoother 입력과 모터 입력에 0을 보낸다.
        if self._recovery_stop is not None:
            self._recovery_stop()
            return
        for publisher in self._stop_publishers:
            publisher.publish(Twist())

    def _control_feedback(self, message: Any) -> None:
        self._last_control_feedback = operation_time(self._node)

    def _execution_timeout(self, path: Path | None) -> float:
        """전송 경로 길이/설정 속도의2배+60초. 기존 제한시간을 하한으로 둔다."""
        base = self._settings.goal_timeout_s
        # 인계 전용 시계 선택은 원본 단계별 예산을 유지한다. 일반 주행은 거리 예산을 유지한다.
        if getattr(self, '_pause_clock_factory', None) is not None:
            return base
        speed = getattr(self, '_nominal_linear_speed_mps', None)
        if self._settings.mode != 'follow_path' or path is None or speed is None:
            return base
        points = [(pose.pose.position.x, pose.pose.position.y) for pose in path.poses]
        distance = sum(math.dist(a, b) for a, b in zip(points, points[1:]))
        if not math.isfinite(distance):
            raise ValueError('주행 경로 길이는 유한해야 합니다.')
        return max(base, float(math.ceil(2.0*distance/speed + 60.0)))

    def request_stop(self) -> None:
        """교통 콜백에서 기다리지 않고 자신의 진행/지연 승인 Goal에 취소를 보낸다."""
        self._stop_for_recovery()
        if self._handle is not None and self._handle.accepted:
            self._handle.cancel_goal_async()
        elif self._pending is not None:
            def cancel_late(future: Any) -> None:
                handle = future.result()
                if handle is not None and handle.accepted:
                    handle.cancel_goal_async()
            self._pending.add_done_callback(cancel_late)

    def _retryable_message(self, message: str) -> bool:
        """NO_VALID_CONTROL 문구만 분류한다. 상태·오류 코드 검사는 호출부에서 유지한다."""
        classifier = getattr(self, '_retryable_control_error', None)
        return (classifier(message) if classifier is not None
                else not message.strip() or 'collision ahead' in message.lower())

    def execute(self, xy: tuple[float,float], yaw: float, path: Path | None, check: Callable[[],None]) -> int:
        """접근·작업·이탈·복귀가 공유하는 최종 출발 경계. 허가 대기는 주행 제한시간 밖이다."""
        traffic = getattr(self._node, '_traffic', None)
        if traffic is None:
            return self._execute_authorized(xy, yaw, path, check)
        if self not in traffic.motion_clients:
            traffic.motion_clients.append(self)
        path, generation = traffic.acquire(path, check)
        def guarded() -> None:
            check()
            traffic.check(generation)
        try:
            guarded()
            return self._execute_authorized(xy, yaw, path, guarded)
        finally:
            # 정상/실패 모두 먼저 정지 명령을 보내며 점유는 실제 위치로 별도 반납한다.
            traffic.movement_finished()

    def _execute_authorized(self, xy: tuple[float,float], yaw: float, path: Path | None, check: Callable[[],None]) -> int:
        if (not self._settings.tf_recovery_enabled and not self._settings.collision_retry_count) or self._settings.mode != 'follow_path':
            return self._execute_once(xy, yaw, path, check)
        if self._recovery_probe is None:
            raise RuntimeError('TF 복구 준비 확인 연결 누락')
        if self._settings.collision_retry_count and not self._settings.tf_recovery_enabled and self._recovery_stop is None:
            raise RuntimeError('재시도 정지 출력 소유자 연결 누락')
        execution_clock = self._execution_clock()
        excluded = 0.0
        wait_start = None
        def retry_waiting(active: bool) -> None:
            nonlocal excluded, wait_start
            now = execution_clock()
            if active:
                wait_start = now
            elif wait_start is not None:
                excluded += now - wait_start
                wait_start = None
        def active_clock() -> float:
            now = execution_clock()
            return now - excluded - (now-wait_start if wait_start is not None else 0.)
        deadline = active_clock() + self._execution_timeout(path)
        def bounded_check() -> None:
            check()
            if active_clock() >= deadline:
                raise TimeoutError('Nav2 전체 주행 시간 초과')
        def execute_with_tf_recovery() -> int:
            if not self._settings.tf_recovery_enabled:
                return self._execute_once(xy, yaw, path, bounded_check)
            return run_with_tf_recovery(
                lambda: self._execute_once(xy, yaw, path, bounded_check),
                self._recovery_probe, self._stop_for_recovery, bounded_check,
                lambda: self._last_control_feedback,
                self._settings.tf_recovery_timeout_s,
                lambda text: self._node.get_logger().warning(text), clock=lambda: operation_time(self._node))
        if self._settings.collision_retry_count:
            return run_with_collision_recovery(execute_with_tf_recovery,
                self._recovery_probe, self._stop_for_recovery, bounded_check,
                self._settings.collision_retry_count,
                lambda text: self._node.get_logger().warning(text), clock=lambda: operation_time(self._node), waiting=retry_waiting)
        return execute_with_tf_recovery()

    def _execute_once(self, xy: tuple[float,float], yaw: float, path: Path | None, check: Callable[[],None]) -> int:
        check()
        if self.has_goal: raise RuntimeError('이전 주행 종료 확인 전에는 새 Goal을 보낼 수 없습니다.')
        if self._settings.mode=='follow_path':
            if path is None or len(path.poses)<2: raise ValueError('FollowPath에 유효한 경로 필요')
            goal=FollowPath.Goal();goal.path=path
            goal.controller_id=self._settings.controller_id
            goal.goal_checker_id=self._settings.goal_checker_id
            goal.progress_checker_id=self._settings.progress_checker_id
            client=self._follow
        else:
            goal=NavigateToPose.Goal()
            goal.pose.header.frame_id=self._settings.map_frame
            goal.pose.header.stamp=self._node.get_clock().now().to_msg()
            goal.pose.pose.position.x=float(xy[0]);goal.pose.pose.position.y=float(xy[1])
            goal.pose.pose.orientation.z=math.sin(yaw/2);goal.pose.pose.orientation.w=math.cos(yaw/2)
            client=self._navigate
        if self._settings.tf_recovery_enabled or self._settings.collision_retry_count:
            # 이전 경로의 좌표·순서는 유지하고 전송 시각만 갱신한다.
            if path is not None:
                path.header.stamp = self._node.get_clock().now().to_msg()
                for pose in path.poses:
                    pose.header.stamp = path.header.stamp
            self._pending=client.send_goal_async(goal, feedback_callback=self._control_feedback)
        else:
            self._pending=client.send_goal_async(goal)
        # 취소/timeout 때 pending을 보존해야 늦은 승인 Goal까지 자신의 것만 취소할 수 있습니다.
        self._handle=self._wait(self._pending,self._settings.response_timeout_s,check)
        if not self._handle.accepted:
            self._clear()
            raise RuntimeError('Nav2 Goal 거절')
        self._result=self._handle.get_result_async()
        timeout = self._execution_timeout(path)
        if timeout > self._settings.goal_timeout_s:
            self._node.get_logger().info(
                f'경로별 주행 제한 {timeout:.1f}초 '
                f'(기본 {self._settings.goal_timeout_s:.1f}초, 설정 속도 {self._nominal_linear_speed_mps:.3f}m/s)')
        response=self._wait(self._result,timeout,check,
            clock=self._execution_clock(),
            timeout_message='Nav2 주행 완료 시간 초과; 요청 종료 여부 확인 필요')
        self._clear()
        if response.status!=GoalStatus.STATUS_SUCCEEDED or getattr(response.result,'error_code',0)!=0:
            code = getattr(response.result, 'error_code', 0)
            message = f'Nav2 실패: status={response.status}, error_code={code}, {getattr(response.result,"error_msg","")}'
            if (self._settings.mode == 'follow_path'
                    and response.status == GoalStatus.STATUS_ABORTED
                    and code == getattr(FollowPath.Result, 'TF_ERROR', -1)):
                raise Nav2TFError(message)
            if (self._settings.collision_retry_count
                    and self._settings.mode == 'follow_path'
                    and response.status == GoalStatus.STATUS_ABORTED
                    and code == getattr(FollowPath.Result, 'NO_VALID_CONTROL', -1)
                    and self._retryable_message(getattr(response.result, 'error_msg', ''))):
                raise Nav2ControlUnavailable(message)
            raise RuntimeError(message)
        return int(response.status)

    def _clear(self) -> None:
        self._pending=self._handle=self._result=None

    def cancel(self) -> None:
        """새 취소 신호는 확인하지 않고 이미 보낸 Goal의 종료를 끝까지 확인합니다."""
        timeout=self._settings.cancel_timeout_s
        def uninterrupted() -> None:
            pass
        if self._handle is None and self._pending is not None:
            self._handle=self._wait(self._pending,timeout,uninterrupted)
        if self._handle is not None and self._handle.accepted:
            result=self._result or self._handle.get_result_async()
            self._wait(self._handle.cancel_goal_async(),timeout,uninterrupted)
            terminal=self._wait(result,timeout,uninterrupted).status
            if terminal not in (GoalStatus.STATUS_CANCELED,GoalStatus.STATUS_ABORTED,GoalStatus.STATUS_SUCCEEDED):
                raise RuntimeError('Nav2 Goal 종료 미확인')
        self._clear()

    def close(self) -> None:
        for publisher in self._stop_publishers:
            self._node.destroy_publisher(publisher)
        self._navigate.destroy();self._follow.destroy()
        self._node.destroy_client(self._parameters)
