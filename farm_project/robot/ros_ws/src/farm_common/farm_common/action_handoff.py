"""작업과 복귀의 소유권 교체. 이전 실행의 정리가 끝나야 다음 실행을 허용한다."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
import threading


class ActionInterrupted(Exception):
    """외부 취소 또는 다른 종류의 액션에 의한 선점."""


@dataclass(eq=False)
class Reservation:
    kind: str
    task_id: str
    interrupted: threading.Event = field(default_factory=threading.Event)


class ActionHandoff:
    def __init__(self) -> None:
        self._condition = threading.Condition()
        self._active: Reservation | None = None
        self._pending: Reservation | None = None

    @property
    def busy(self) -> bool:
        with self._condition:
            return self._active is not None

    @property
    def current(self) -> tuple[str, str] | None:
        with self._condition:
            return (self._active.kind, self._active.task_id) if self._active else None

    @property
    def work_interrupted(self) -> bool:
        with self._condition:
            return bool(self._active and self._active.kind == 'work'
                        and self._active.interrupted.is_set())

    def reserve(self, kind: str, task_id: str) -> bool:
        """같은 종류의 중복 실행은 거절한다. 교체 대기는 한 건으로 제한한다."""
        with self._condition:
            if self._pending is not None or (self._active and self._active.kind == kind):
                return False
            token = Reservation(kind, task_id)
            if self._active is None:
                self._active = token
            else:
                self._active.interrupted.set()
                self._pending = token
            return True

    def acquire(self, kind: str, task_id: str, check: Callable[[], None]) -> Reservation:
        """정리 완료를 기다리는 동안에도 외부 취소·종료 요청을 확인한다."""
        with self._condition:
            while True:
                check()
                token = self._active
                if token is not None and (token.kind, token.task_id) == (kind, task_id):
                    if token.interrupted.is_set():
                        raise ActionInterrupted('다른 액션으로 교체됨')
                    return token
                if self._pending is None or (self._pending.kind, self._pending.task_id) != (kind, task_id):
                    raise RuntimeError('액션 예약이 없습니다.')
                self._condition.wait(.05)

    def release(self, kind: str, task_id: str) -> None:
        """호출자는 자원·주행 정리를 끝낸 뒤에만 소유권을 반납한다."""
        with self._condition:
            if self._active and (self._active.kind, self._active.task_id) == (kind, task_id):
                self._active, self._pending = self._pending, None
            elif self._pending and (self._pending.kind, self._pending.task_id) == (kind, task_id):
                self._pending = None
            self._condition.notify_all()
