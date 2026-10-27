"""인계 이벤트는 현재 세션과 단계가 일치할 때만 접수한다."""
from threading import Condition
import time

class TransferSession:
    def __init__(self, timeout: float = 60.) -> None:
        self._cv = Condition()
        self.request = None
        self.events = set()
        self.phase = 'IDLE'
        self.timeout = timeout

    def begin(self, request) -> None:
        with self._cv:
            self.request, self.events, self.phase = request, set(), 'APPROACH'

    def stage(self, phase: str) -> None:
        with self._cv:
            self.phase = phase

    def accept(self, task_id: str, transfer_id: str, source: str, event: str) -> None:
        with self._cv:
            r = self.request
            if not r or (r.task_id,r.transfer_id,r.harvest_robot_id) != (task_id,transfer_id,source):
                raise ValueError('인계 세션/상대 불일치')
            if event not in ('DOCK_READY','TRANSFER_COMPLETE'):
                raise ValueError('알 수 없는 인계 이벤트')
            if event in self.events:
                return  # 현재 세션의 재전송은 멱등 처리
            if event == 'DOCK_READY' and self.phase != 'WAIT_READY':
                raise ValueError('DOCK_READY 수신 단계 불일치')
            if event == 'TRANSFER_COMPLETE' and self.phase != 'WAIT_TRANSFER':
                raise ValueError('안정 도킹 전 TRANSFER_COMPLETE 거절')
            self.events.add(event)
            self._cv.notify_all()

    def wait(self, event: str, check) -> None:
        deadline = time.monotonic()+self.timeout
        with self._cv:
            while event not in self.events:
                check()
                if time.monotonic() >= deadline:
                    raise TimeoutError(event+' 대기 시간 초과')
                self._cv.wait(.05)
            check()

    def close(self) -> None:
        with self._cv:
            self.request, self.phase = None, 'IDLE'
            self._cv.notify_all()
