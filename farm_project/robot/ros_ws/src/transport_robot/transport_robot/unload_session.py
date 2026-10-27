"""하역 요청·선별장·대기 단계에 묶인 준비 신호. 전 작업의 신호는 재사용하지 않는다."""
from threading import Condition
import time
from typing import Callable
from .mission_types import Request


class UnloadSession:
    def __init__(self, timeout: float = 60.) -> None:
        self._cv = Condition()
        self.timeout = timeout
        self.request = None
        self.phase = 'IDLE'
        self.ready = False

    def begin(self, request: Request) -> None:
        with self._cv:
            self.request, self.phase, self.ready = request, 'APPROACH', False

    def stage(self, phase: str) -> None:
        with self._cv:
            self.phase = phase

    def accept(self, task_id: str, station_id: str, event: str) -> None:
        with self._cv:
            if not self.request or (task_id, station_id) != (self.request.task_id, self.request.station_id):
                raise ValueError('하역 작업/선별장 불일치')
            if event != 'UNLOAD_READY':
                raise ValueError('알 수 없는 하역 이벤트')
            if self.ready:
                return  # 현재 작업에서 접수한 신호의 재전송만 멱등 처리
            if self.phase != 'WAIT_READY':
                raise ValueError('선별장 정밀 도킹·정지 완료 후 대기 단계에서만 UNLOAD_READY 접수')
            self.ready = True
            self._cv.notify_all()

    def wait(self, check: Callable[[], None]) -> None:
        deadline = time.monotonic() + self.timeout
        with self._cv:
            while not self.ready:
                check()
                if time.monotonic() >= deadline:
                    raise TimeoutError('UNLOAD_READY 대기 시간 초과')
                self._cv.wait(.05)
            check()

    def close(self) -> None:
        with self._cv:
            self.request, self.phase, self.ready = None, 'IDLE', False
            self._cv.notify_all()
