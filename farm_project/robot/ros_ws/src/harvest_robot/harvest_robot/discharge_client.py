"""배출 Action 연결. 단일 Goal 소유권을 유지하고 자동 재전송하지 않는다."""
import math
import time
from typing import Any, Callable
from .discharge_result import DischargeReply, DischargeEvidence
from .transfer_devices import DeviceResult


def discharge_parameters(config: dict) -> dict:
    """Action 방식은 명시 설정일 때만 선택한다. 운영 주소/시간을 추측하지 않는다."""
    mode = config.get('discharge_mode', 'device_services')
    values = config.get('discharge_action', {})
    if mode not in ('device_services', 'action') or not isinstance(values, dict):
        raise ValueError('배출 방식/설정 오류')
    if mode == 'device_services':
        if values: raise ValueError('discharge_action은 action 방식에서만 사용합니다.')
    else:
        if config.get('rotation_mode', 'device_services') not in ('nav2_spin', 'components'):
            raise ValueError('배출 Action은 공통 nav2_spin 어댑터와 조합합니다.')
        if set(values) != {'endpoint', 'response_timeout_s', 'cancel_timeout_s'}:
            raise ValueError('배출 endpoint/응답·취소 제한시간을 명시해야 합니다.')
        endpoint = values['endpoint']
        if not isinstance(endpoint, str) or not endpoint or any(c.isspace() for c in endpoint):
            raise ValueError('배출 endpoint가 필요합니다.')
        for name in ('response_timeout_s', 'cancel_timeout_s'):
            value = values[name]
            if type(value) not in (int, float) or not math.isfinite(value) or value <= 0:
                raise ValueError(name + '는 유한한 양수여야 합니다.')
    return {'discharge_mode': mode, 'discharge_action': values}


class DischargeClient:
    """start/poll/cancel은 동일 장치 작업 스레드에서 호출. Feedback만 ROS 콜백이다."""
    def __init__(self, node: Any, endpoint: str, response_timeout_s: float,
                 cancel_timeout_s: float, group: Any = None, *, client: Any = None,
                 goal_factory: Callable | None = None,
                 feedback: Callable[[str], None] | None = None) -> None:
        discharge_parameters({'discharge_mode': 'action', 'rotation_mode': 'nav2_spin',
            'discharge_action': dict(endpoint=endpoint, response_timeout_s=response_timeout_s,
                                     cancel_timeout_s=cancel_timeout_s)})
        if client is None or goal_factory is None:
            from farm_interfaces.action import Discharge
            from rclpy.action import ActionClient
            if client is None: client = ActionClient(node, Discharge, endpoint, callback_group=group)
            if goal_factory is None: goal_factory = Discharge.Goal
        self.client, self.goal_factory = client, goal_factory
        self.response_timeout_s, self.cancel_timeout_s = response_timeout_s, cancel_timeout_s
        self.feedback = feedback
        self.phase = ''
        self._pending = self._handle = self._result = None
        self._unknown = False
        self._evidence = None
        self._finished = None
        self._token = None

    def ready(self) -> bool:
        return not self.has_goal and self.client.server_is_ready()

    @property
    def has_goal(self) -> bool:
        return self._unknown or self._pending is not None or self._handle is not None

    def start(self, evidence: DischargeEvidence) -> object:
        if not self.ready(): raise RuntimeError('배출 서버 미연결 또는 이전 요청 종료 미확인')
        evidence.request_once()
        self._evidence, self._finished, self._token = evidence, None, object()
        token = self._token
        self.phase = ''
        goal = self.goal_factory(); goal.transfer_id = evidence.transfer_id
        def report(message: Any) -> None:
            # 이전 Goal Feedback이 다음 인계의 진행 단계에 섞이지 않도록 한다.
            if token is self._token and self._finished is None:
                phase = message.feedback.phase
                if phase in ('OPENING', 'DISCHARGING', 'CLOSING'):
                    self.phase = phase
                    if self.feedback: self.feedback(phase)
        self._unknown = True
        self._deadline = time.monotonic() + self.response_timeout_s
        try:
            self._pending = self.client.send_goal_async(goal, feedback_callback=report)
            self._unknown = False
        except Exception:
            evidence.invalidate()
            raise
        return token

    def poll(self, ticket: object) -> DeviceResult:
        if ticket is not self._token: return DeviceResult(True, False, '이전 배출 요청 ticket')
        if self._finished is not None: return self._finished
        try:
            if self._handle is None:
                if not self._pending.done():
                    if time.monotonic() >= self._deadline: raise TimeoutError('배출 Goal 응답 시간 초과')
                    return DeviceResult(False)
                self._handle = self._pending.result()
                if self._handle is None: raise RuntimeError('빈 Goal 응답; 종료 미확인')
                if not self._handle.accepted:
                    self._clear(); raise RuntimeError('배출 Goal 거절')
                self._result = self._handle.get_result_async()
            if not self._result.done(): return DeviceResult(False)
            response = self._result.result()
            if response.status not in (4, 5, 6): raise RuntimeError('배출 terminal 상태 미확인')
            self._clear()
            reply = response.result
            self._finished = self._evidence.finish(
                DischargeReply(reply.transfer_id, reply.error_codes, reply.error_message),
                action_succeeded=response.status == 4)
        except Exception as error:
            self._evidence.invalidate()
            self._finished = DeviceResult(True, False, str(error))
        return self._finished

    def _clear(self) -> None:
        self._pending = self._handle = self._result = None
        self._unknown = False

    def cancel(self) -> None:
        """늦은 승인도 회수한다. terminal 확인은 물리 정지/닫힘 확인이 아니다."""
        if self._evidence: self._evidence.invalidate()
        self._finished = DeviceResult(True, False, '배출 중단')
        deadline = time.monotonic() + self.cancel_timeout_s
        def wait(future: Any) -> Any:
            while not future.done():
                if time.monotonic() >= deadline: raise TimeoutError('배출 취소/종료 미확인')
                time.sleep(.01)
            return future.result()
        if self._unknown: raise RuntimeError('배출 전송 여부 미확인; 현장 복구 필요')
        if self._handle is None and self._pending is not None:
            self._handle = wait(self._pending)
            if self._handle is None: raise RuntimeError('배출 승인 미확인')
        if self._handle is not None and self._handle.accepted:
            result = self._result if self._result is not None else self._handle.get_result_async()
            if not result.done():
                # ACK만으로 성공 반환하지 않고 아래에서 반드시 terminal을 기다린다.
                self._handle.cancel_goal_async()
            response = wait(result)
            if response.status not in (4, 5, 6): raise RuntimeError('배출 종료 상태 미확인')
        self._clear()

    def close(self) -> None:
        self.client.destroy()
