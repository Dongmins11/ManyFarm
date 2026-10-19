"""설정으로 선택한 내부 HarvestTask Action의 전달·종료 확인만 담당합니다.

시뮬 패키지를 import하지 않으며 후보·Teacher·재시도·수확 성공을 판단하지 않습니다.
취소 요청 ACK와 terminal Result를 기다려 늦게 수락된 자신의 Goal까지 정리합니다.
"""
from collections.abc import Callable, Mapping
from dataclasses import dataclass
import math
import threading
import time
from typing import Any

from .contract import validate_counts


class ArmExecutionError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class ArmActionSettings:
    endpoint: str
    readiness_timeout_s: float = 5.
    response_timeout_s: float = 5.
    execution_timeout_s: float = 180.
    cancel_timeout_s: float = 10.

    @classmethod
    def from_mapping(cls, config: Mapping) -> 'ArmActionSettings':
        if not isinstance(config, Mapping):
            raise ValueError('arm_action 설정 객체가 필요합니다.')
        endpoint = config.get('endpoint')
        if not isinstance(endpoint, str) or not endpoint.strip() or endpoint.strip() != endpoint:
            raise ValueError('arm_action.endpoint가 비어 있거나 공백을 포함합니다.')
        values = {name: config[name] for name in cls.__dataclass_fields__ if name in config}
        result = cls(**values)
        for name in cls.__dataclass_fields__:
            if name == 'endpoint':
                continue
            value = getattr(result, name)
            if type(value) not in (int, float) or not math.isfinite(value) or value <= 0:
                raise ValueError('arm_action.'+name+'은 유한한 양수 초여야 합니다.')
        return result


def configured_arm_settings(config: Mapping) -> ArmActionSettings | None:
    """환경명 대신 완료 정책으로 선택한다. 미설정 연결 주소를 자동 보완하지 않는다."""
    policy = config.get('completion_policy')
    if policy == 'ARRIVAL_ONLY_NO_HARVEST':
        return None
    if policy != 'ARRIVAL_THEN_ARM':
        raise ValueError('알 수 없는 수확 완료 정책')
    return ArmActionSettings.from_mapping(config.get('arm_action'))


class ArmActionClient:
    """별도 executor 스레드가 ROS future를 진행시키는 동안 작업 스레드에서 기다립니다."""

    def __init__(self, node: Any, settings: ArmActionSettings, group: Any = None, *, client: Any = None) -> None:
        if client is None:
            from rclpy.action import ActionClient
            from farm_interfaces.action import HarvestTask
            client = ActionClient(node, HarvestTask, settings.endpoint, callback_group=group)
        self._client, self.settings = client, settings
        self._pending = self._handle = self._result = None
        self._goal = self._progress = None
        self._counts = (0, 0)
        self._feedback_error: Exception | None = None
        self._cancel_ack = False
        self._lock = threading.Lock()
        self._token = 0
        self.last_result: dict | None = None

    def server_is_ready(self) -> bool:
        """동작 요청 없이 설정된 팔 서버의 연결 상태만 조회한다."""
        return self._client.server_is_ready()

    @property
    def has_goal(self) -> bool:
        return self._pending is not None or self._handle is not None

    def _wait(self, future: Any, timeout: float, check: Callable[[], None], *, cleanup: bool = False) -> Any:
        deadline = time.monotonic()+timeout
        while not future.done():
            check()
            if not cleanup and self._feedback_error is not None:
                raise ArmExecutionError('ARM_PROTOCOL_ERROR', str(self._feedback_error))
            if time.monotonic() >= deadline:
                raise ArmExecutionError('ARM_TIMEOUT', '팔 Action 응답/종료 대기 시간 초과')
            time.sleep(.01)
        check()
        if not cleanup and self._feedback_error is not None:
            raise ArmExecutionError('ARM_PROTOCOL_ERROR', str(self._feedback_error))
        return future.result()

    def _feedback(self, message: Any, token: int) -> None:
        with self._lock:
            if token != self._token or self._goal is None:
                return
            try:
                value = message.feedback
                if (value.robot_id != self._goal.robot_id
                        or value.task_id != self._goal.harvest_task.task_id):
                    raise ValueError('팔 Feedback robot/task 불일치')
                counts = validate_counts(value.success_count, value.failed_count, self._counts)
                self._counts = counts
                if self._progress is not None:
                    self._progress(*counts)
            except Exception as error:
                self._feedback_error = error

    def _terminal(self, response: Any) -> dict:
        # action_msgs/GoalStatus: SUCCEEDED=4, CANCELED=5, ABORTED=6.
        expected = {4: 'SUCCESS', 5: 'CANCELED', 6: 'FAILED'}.get(response.status)
        value, goal = response.result, self._goal
        try:
            if (expected is None or value.result_code != expected or value.robot_id != goal.robot_id
                    or value.task_id != goal.harvest_task.task_id or value.window_id != goal.harvest_task.window_id
                    or value.expected_count != goal.harvest_task.expected_count
                    or not isinstance(value.error_code, str) or not isinstance(value.error_message, str)):
                raise ValueError('팔 Result 상태/robot/task/window/expected 계약 불일치')
            with self._lock:
                counts = validate_counts(value.harvested_count, value.failed_count, self._counts)
                self._counts = counts
                # terminal 이후 늦게 도착한 Feedback은 확정 Result를 덮어쓰지 않습니다.
                self._token += 1
                if self._progress is not None:
                    self._progress(*counts)
            result = dict(result_code=expected, harvested_count=counts[0], failed_count=counts[1],
                          error_code=value.error_code, error_message=value.error_message)
            self.last_result = result
            if value.error_code == 'CANCEL_UNCONFIRMED':
                raise ArmExecutionError('CANCEL_UNCONFIRMED', value.error_message or '팔 정지 미확인')
            return result
        except ArmExecutionError:
            raise
        except (AttributeError, TypeError, ValueError) as error:
            raise ArmExecutionError('ARM_PROTOCOL_ERROR', str(error)) from error

    def execute(self, goal: Any, check: Callable[[], None], progress: Callable[[int, int], None]) -> dict:
        if self.has_goal:
            raise ArmExecutionError('CANCEL_UNCONFIRMED', '이전 팔 Goal 종료 확인이 필요합니다.')
        self._token += 1
        token = self._token
        self._goal, self._progress, self._counts = goal, progress, (0, 0)
        self._feedback_error, self.last_result = None, None
        self._cancel_ack = False
        deadline = time.monotonic()+self.settings.readiness_timeout_s
        while not self._client.server_is_ready():
            check()
            if time.monotonic() >= deadline:
                raise ArmExecutionError('ARM_UNAVAILABLE', '팔 Action 서버가 준비되지 않았습니다.')
            time.sleep(.01)
        check()
        self._pending = self._client.send_goal_async(goal, feedback_callback=lambda value: self._feedback(value, token))
        self._handle = self._wait(self._pending, self.settings.response_timeout_s, check)
        if self._handle is None or not self._handle.accepted:
            self._clear()
            raise ArmExecutionError('ARM_REJECTED', '팔 Action Goal이 거절됐습니다.')
        self._result = self._handle.get_result_async()
        response = self._wait(self._result, self.settings.execution_timeout_s, check)
        result = self._terminal(response)
        self._clear()
        return result

    def cancel(self) -> dict | None:
        """외부 취소 신호와 별개로 늦은 승인·취소 ACK·실제 종료를 끝까지 확인합니다."""
        timeout = self.settings.cancel_timeout_s
        if self._handle is None and self._pending is not None:
            self._handle = self._wait(self._pending, timeout, lambda: None, cleanup=True)
        if self._handle is not None and self._handle.accepted:
            result = self._result or self._handle.get_result_async()
            if not result.done():
                try:
                    ack = self._wait(self._handle.cancel_goal_async(), timeout, lambda: None, cleanup=True)
                    self._cancel_ack = (ack.return_code == 0 and any(
                        bytes(info.goal_id.uuid) == bytes(self._handle.goal_id.uuid)
                        for info in ack.goals_canceling))
                except (ArmExecutionError, AttributeError, TypeError):
                    # 이미 완료된 SUCCESS/FAILED와 취소 ACK가 교차하면 실제 terminal을 우선합니다.
                    self._cancel_ack = False
            response = self._wait(result, timeout, lambda: None, cleanup=True)
            if response.status == 5 and not self._cancel_ack:
                raise ArmExecutionError('CANCEL_UNCONFIRMED', '자신의 팔 Goal 취소 수락 ACK가 없습니다.')
            terminal = self._terminal(response)
            self._clear()
            return terminal
        self._clear()
        return None

    def _clear(self) -> None:
        with self._lock:
            self._token += 1
            self._pending = self._handle = self._result = None
            self._goal = self._progress = None

    def close(self) -> None:
        self._client.destroy()
