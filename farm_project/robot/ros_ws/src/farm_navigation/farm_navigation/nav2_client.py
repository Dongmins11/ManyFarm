"""Nav2 액션 연결. 로봇 Mission/State를 모르며 자신의 Goal만 관리합니다."""
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
from .arrival import validate_goal_checkers


class Nav2Client:
    def __init__(self, node: Node, settings: NavigationSettings, group: CallbackGroup) -> None:
        self._node: Node = node
        self._settings: NavigationSettings = settings
        self._navigate=ActionClient(node,NavigateToPose,settings.navigate_action,callback_group=group)
        self._follow=ActionClient(node,FollowPath,settings.follow_action,callback_group=group)
        self._parameters=node.create_client(GetParameters,settings.controller_node.rstrip('/')+'/get_parameters',callback_group=group)
        self._pending: Future | None = None
        self._handle: ClientGoalHandle | None = None
        self._result: Future | None = None
        self._recovery_probe = None
        self._stop_publishers = ([node.create_publisher(Twist, topic, 10)
                                 for topic in ('cmd_vel_nav', 'cmd_vel')]
                                if settings.tf_recovery_enabled else [])
        self._last_control_feedback = 0.0

    @property
    def has_goal(self) -> bool:
        return self._pending is not None or self._handle is not None

    def _wait(self, future: Future, timeout: float, check: Callable[[],None]) -> Any:
        deadline=time.monotonic()+timeout
        while not future.done() and time.monotonic()<deadline:
            check()
            time.sleep(.02)
        check()
        if not future.done(): raise TimeoutError('Nav2 응답 시간 초과; 요청 종료 여부 확인 필요')
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

    def preflight(self, check: Callable[[],None]) -> dict[str,Any]:
        s=self._settings
        client=self._follow if s.mode=='follow_path' else self._navigate
        deadline=time.monotonic()+s.readiness_timeout_s
        while not client.server_is_ready() or not self._parameters.service_is_ready():
            check()
            if time.monotonic()>deadline: raise RuntimeError('Nav2 액션/파라미터 서버가 준비되지 않았습니다.')
            time.sleep(.05)
        values=self._read_parameters(['goal_checker_plugins','controller_plugins','progress_checker_plugins'],check)
        ids=values.get('goal_checker_plugins')
        if not isinstance(ids,list) or not ids: raise RuntimeError('goal_checker_plugins 누락')
        if s.mode=='follow_path':
            for name,value in [('goal_checker_plugins',s.goal_checker_id),('controller_plugins',s.controller_id),('progress_checker_plugins',s.progress_checker_id)]:
                if value not in (values.get(name) or []): raise RuntimeError(f'{name}에 {value}가 없습니다.')
            ids=[s.goal_checker_id]
        values.update(self._read_parameters([f'{name}.{key}' for name in ids for key in ('plugin','xy_goal_tolerance','yaw_goal_tolerance','stateful','symmetric_yaw_tolerance')],check))
        checked=dict(values,goal_checker_plugins=ids)
        checkers=validate_goal_checkers(checked,s.arrival_tolerance_m,s.heading_tolerance_rad)
        return {'mode':s.mode,'controller_node':s.controller_node,'parameters':values,'checkers':checkers,'status':'OK'}

    def set_recovery_probe(self, probe: Callable[[], bool]) -> None:
        self._recovery_probe = probe

    def _stop_for_recovery(self) -> None:
        # 자신의 Nav2 Goal이 종료된 뒤에만 호출한다. smoother 입력과 모터 입력에 0을 보낸다.
        for publisher in self._stop_publishers:
            publisher.publish(Twist())

    def _control_feedback(self, message: Any) -> None:
        self._last_control_feedback = time.monotonic()

    def execute(self, xy: tuple[float,float], yaw: float, path: Path | None, check: Callable[[],None]) -> int:
        if not self._settings.tf_recovery_enabled or self._settings.mode != 'follow_path':
            return self._execute_once(xy, yaw, path, check)
        if self._recovery_probe is None:
            raise RuntimeError('TF 복구 준비 확인 연결 누락')
        deadline = time.monotonic() + self._settings.goal_timeout_s
        def bounded_check() -> None:
            check()
            if time.monotonic() >= deadline:
                raise TimeoutError('Nav2 전체 주행 시간 초과')
        return run_with_tf_recovery(
            lambda: self._execute_once(xy, yaw, path, bounded_check),
            self._recovery_probe, self._stop_for_recovery, bounded_check,
            lambda: self._last_control_feedback,
            self._settings.tf_recovery_timeout_s,
            lambda text: self._node.get_logger().warning(text))

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
        if self._settings.tf_recovery_enabled:
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
        response=self._wait(self._result,self._settings.goal_timeout_s,check)
        self._clear()
        if response.status!=GoalStatus.STATUS_SUCCEEDED or getattr(response.result,'error_code',0)!=0:
            code = getattr(response.result, 'error_code', 0)
            message = f'Nav2 실패: status={response.status}, error_code={code}, {getattr(response.result,"error_msg","")}'
            if (self._settings.mode == 'follow_path'
                    and response.status == GoalStatus.STATUS_ABORTED
                    and code == getattr(FollowPath.Result, 'TF_ERROR', -1)):
                raise Nav2TFError(message)
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

