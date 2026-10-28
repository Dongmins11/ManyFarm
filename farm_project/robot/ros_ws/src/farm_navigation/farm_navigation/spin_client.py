"""Nav2 Spin 전용 연결. 자신의 Goal만 취소하며 미확인 요청을 버리지 않는다."""
import math
import time
from typing import Any, Callable


class SpinClient:
    def __init__(self, node: Any, endpoint: str, settings: Any, group: Any = None,
                 *, client: Any = None, goal_factory: Callable | None = None, execution_clock=None) -> None:
        if not isinstance(endpoint, str) or not endpoint or any(c.isspace() for c in endpoint):
            raise ValueError('Spin endpoint를 명시해야 합니다.')
        if client is None or goal_factory is None:
            from nav2_msgs.action import Spin
            from rclpy.action import ActionClient
            if client is None:
                client = ActionClient(node, Spin, endpoint, callback_group=group)
            if goal_factory is None:
                goal_factory = Spin.Goal
        self._node = node
        self._pause_clock_factory = execution_clock
        self._client, self._goal_factory, self.settings = client, goal_factory, settings
        self._pending = self._handle = self._result = None

    @property
    def has_goal(self) -> bool:
        return self._pending is not None or self._handle is not None

    def ready(self) -> bool:
        return self._client.server_is_ready()

    def _wait(self, future: Any, timeout: float, check: Callable[[], None], *, clock=time.monotonic) -> Any:
        deadline = clock() + timeout
        while not future.done():
            check()
            if clock() >= deadline:
                raise TimeoutError('Spin 응답/종료 시간 초과; 요청 종료 확인 필요')
            time.sleep(.01)
        check()
        return future.result()

    def execute(self, angle: float, allowance: float, check: Callable[[], None]) -> None:
        if getattr(self._node, '_traffic', None) is not None:
            raise RuntimeError('교통 첫 범위에서 도킹/인계 Spin은 지원하지 않습니다.')
        if (type(angle) not in (int, float) or not math.isfinite(angle) or not 0 < abs(angle) <= math.pi
                or type(allowance) not in (int, float) or not math.isfinite(allowance)
                or not 0 < allowance < 2147483647):
            raise ValueError('회전각은 0 초과 pi 이하 절댓값, 제한시간은 유한한 양수 초여야 합니다.')
        if self.has_goal:
            raise RuntimeError('이전 Spin 종료 미확인')
        check()
        if not self.ready():
            raise RuntimeError('Spin 서버 미연결')
        goal = self._goal_factory()
        goal.target_yaw = float(angle)
        ns = int(allowance * 1e9)
        goal.time_allowance.sec, goal.time_allowance.nanosec = divmod(ns, 10**9)
        self._pending = self._client.send_goal_async(goal)
        self._handle = self._wait(self._pending, self.settings.response_timeout_s, check)
        if self._handle is None or not self._handle.accepted:
            self._clear()
            raise RuntimeError('Spin Goal 거절')
        self._result = self._handle.get_result_async()
        response = self._wait(self._result, allowance + self.settings.response_timeout_s, check,
            clock=self._pause_clock_factory() if self._pause_clock_factory is not None else time.monotonic)
        # 잘못된/비종결 응답은 소유권을 유지하여 stop에서 다시 확인한다.
        if response.status not in (4, 5, 6):
            raise RuntimeError('Spin terminal 상태 미확인')
        self._clear()
        if response.status != 4 or response.result.error_code != 0:
            raise RuntimeError(f'Spin 실패: status={response.status}, code={response.result.error_code}')

    def cancel(self) -> None:
        """지연 승인도 회수한다. 취소 접수 ACK만으로 정지 완료를 주장하지 않는다."""
        timeout = self.settings.cancel_timeout_s
        if self._handle is None and self._pending is not None:
            self._handle = self._wait(self._pending, timeout, lambda: None)
        if self._handle is not None and self._handle.accepted:
            result = self._result if self._result is not None else self._handle.get_result_async()
            acknowledged = False
            already_terminal = result.done()
            if not already_terminal:
                try:
                    ack = self._wait(self._handle.cancel_goal_async(), timeout, lambda: None)
                    acknowledged = ack.return_code == 0 and any(
                        bytes(info.goal_id.uuid) == bytes(self._handle.goal_id.uuid)
                        for info in ack.goals_canceling)
                except Exception:
                    # 취소 응답과 정상 완료가 교차할 수 있으므로 terminal도 확인한다.
                    pass
            response = self._wait(result, timeout, lambda: None)
            if response.status not in (4, 5, 6) or (response.status == 5 and not (acknowledged or already_terminal)):
                raise RuntimeError('Spin 자신의 Goal 취소/종료 미확인')
        self._clear()

    def _clear(self) -> None:
        self._pending = self._handle = self._result = None

    def close(self) -> None:
        self._client.destroy()
