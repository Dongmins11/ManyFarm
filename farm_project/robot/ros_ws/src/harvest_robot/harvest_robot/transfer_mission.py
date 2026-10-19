"""ROS와 독립적인 인계 순서. monotonic 제한 시간, 이벤트 기반 대기.

준비→회전→DOCK_READY→DOCK_STABLE→배출→TRANSFER_COMPLETE→
TRANSPORT_CLEAR→복구. 허가 이벤트만으로 물리 완료를 생성하지 않는다.
"""
from dataclasses import dataclass
import math
import threading
import time
from typing import Any, Callable


class TransferFailure(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


class TransferCanceled(TransferFailure):
    def __init__(self) -> None:
        super().__init__('CANCELED', '관제가 인계 작업 취소를 요청했습니다.')


@dataclass(frozen=True)
class TransferOutcome:
    result_code: str
    error_code: str
    error_message: str
    transfer_complete: bool
    transport_clear: bool
    restore_complete: bool
    recovery_required: bool


class TransferMission:
    """한 인계만 담당. 서비스 콜백과 실행 스레드는 Condition으로 보호한다."""

    def __init__(self, devices: Any, feedback: Callable[[str], None],
                 canceled: Callable[[], bool], shutting_down: Callable[[], bool],
                 timeout_s: float = 120.0, stop_timeout_s: float = 10.0,
                 clock: Callable[[], float] = time.monotonic) -> None:
        for value in (timeout_s, stop_timeout_s):
            if isinstance(value, bool) or not math.isfinite(value) or value <= 0:
                raise ValueError('인계 제한 시간은 유한한 양수여야 합니다.')
        self.devices, self.feedback = devices, feedback
        self.canceled, self.shutting_down = canceled, shutting_down
        self.timeout_s, self.stop_timeout_s, self.clock = timeout_s, stop_timeout_s, clock
        self._condition = threading.Condition()
        self._phase = 'TRANSFER_PREPARING'
        self._events: set[str] = set()
        self._terminal = False
        self._begun = False
        self.transfer_complete = self.transport_clear = self.restore_complete = False

    @property
    def phase(self) -> str:
        with self._condition:
            return self._phase

    def receive(self, event: str) -> tuple[bool, str, str]:
        """ID 검사는 통신 계층에서 수행한다. 중복은 멱등 접수, 순서 역전은 거절."""
        with self._condition:
            if self._terminal:
                return False, 'NO_ACTIVE_TRANSFER', '종료된 인계입니다.'
            if event not in ('DOCK_STABLE', 'TRANSPORT_CLEAR'):
                return False, 'INVALID_EVENT', '지원하지 않는 운송 이벤트입니다.'
            if event in self._events:
                return True, 'NONE', ''
            required = {'DOCK_STABLE': 'WAIT_DOCK_STABLE',
                        'TRANSPORT_CLEAR': 'WAIT_TRANSPORT_CLEAR'}[event]
            if self._phase != required:
                return False, 'UNEXPECTED_EVENT', '현재 단계에서 허용되지 않습니다: ' + self._phase
            self._events.add(event)
            self._condition.notify_all()
            return True, 'NONE', ''

    def _phase_to(self, phase: str) -> None:
        with self._condition:
            self._phase = phase

    def _check(self) -> None:
        if self.shutting_down():
            raise TransferFailure('SHUTDOWN', '노드 종료 중 인계 동작을 중단합니다.')
        if self.canceled():
            raise TransferCanceled()

    def _wait_tick(self) -> None:
        with self._condition:
            self._condition.wait(timeout=0.02)

    def _perform(self, operation: str) -> None:
        self._check()
        # start 예외도 전송 여부 불명으로 취급한다.
        self._begun = True
        deadline = self.clock() + self.timeout_s
        ticket = self.devices.start(operation)
        while True:
            self._check()
            if self.clock() >= deadline:
                raise TransferFailure('DEVICE_TIMEOUT', operation + ' 완료 확인 시간 초과')
            result = self.devices.poll(ticket)
            if result.completed:
                if not result.ok:
                    raise TransferFailure('DEVICE_FAILED', operation + ': ' + result.detail)
                return
            self._wait_tick()

    def _wait_event(self, event: str) -> None:
        deadline = self.clock() + self.timeout_s
        while True:
            self._check()
            with self._condition:
                if event in self._events:
                    return
            if self.clock() >= deadline:
                raise TransferFailure('EVENT_TIMEOUT', event + ' 수신 시간 초과')
            self._wait_tick()

    def _stop(self) -> bool:
        """취소 시에도 정지 응답을 기다린다. 자세 복구·게이트 닫기를 호출하지 않는다."""
        try:
            deadline = self.clock() + self.stop_timeout_s
            ticket = self.devices.start('stop')
            while self.clock() < deadline:
                result = self.devices.poll(ticket)
                if result.completed:
                    return result.ok
                self._wait_tick()
        except Exception:
            pass
        return False

    def run(self) -> TransferOutcome:
        code, error_code, detail = 'SUCCESS', 'NONE', ''
        recovery = False
        try:
            self._perform('prepare_arm')
            self._perform('rotate_to_transfer')
            # Feedback 콜백에서 즉시 서비스가 돌아와도 받을 수 있게 먼저 전환한다.
            self._phase_to('WAIT_DOCK_STABLE')
            self.feedback('DOCK_READY')
            self._wait_event('DOCK_STABLE')
            self._phase_to('TRANSFERRING')
            self._perform('discharge')
            self.transfer_complete = True
            self._phase_to('WAIT_TRANSPORT_CLEAR')
            self.feedback('TRANSFER_COMPLETE')
            self._wait_event('TRANSPORT_CLEAR')
            self.transport_clear = True
            self._phase_to('RESTORING')
            self._perform('restore')
            self.restore_complete = True
            self._check()
        except Exception as error:
            code = 'CANCELED' if isinstance(error, TransferCanceled) else 'FAILED'
            error_code = error.code if isinstance(error, TransferFailure) else 'TRANSFER_INTERNAL_ERROR'
            detail = str(error)
            recovery = self._begun
            # 실패 후 새로운 허가 이벤트를 받아들이지 않는다.
            with self._condition:
                self._terminal = True
                self._phase = 'ERROR' if recovery else 'IDLE'
            if self._begun and not self._stop():
                code, error_code = 'FAILED', 'STOP_UNCONFIRMED'
                detail += '; 장치 정지 미확인'
        finally:
            with self._condition:
                self._terminal = True
        return TransferOutcome(code, error_code, detail, self.transfer_complete,
                               self.transport_clear, self.restore_complete, recovery)
