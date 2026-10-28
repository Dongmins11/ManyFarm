"""이동과 인계 차체 동작의 순서만 담당한다. 실제 주행은 주입한 기존 실행기가 맡는다."""
from collections.abc import Callable
from threading import Event, Lock
from typing import Any

STAGES = ('approach', 'departure', 'wall', 'retreat', 'align', 'return', 'exit')

class TransferSequence:
    """동일 실행기를 실물 시험과 후속 미션 연결에서 재사용한다. 자동 재시도하지 않는다."""
    def __init__(self, execute: Callable[[str], Any], cancel: Callable[[], None],
                 record: Callable[[dict], None]) -> None:
        self._execute, self._cancel, self._record = execute, cancel, record
        self._stop = Event()
        self._lock = Lock()

    def run(self) -> list[str]:
        if not self._lock.acquire(blocking=False):
            raise RuntimeError('연속 동작 실행 중입니다.')
        done: list[str] = []
        try:
            for stage in STAGES:
                if self._stop.is_set():
                    raise RuntimeError('연속 동작 취소됨')
                self._record(dict(stage=stage, phase='STARTED', completed=list(done)))
                result = self._execute(stage)
                if self._stop.is_set():
                    raise RuntimeError('연속 동작 취소됨')
                done.append(stage)
                self._record(dict(stage=stage, phase='SUCCEEDED', completed=list(done), result=result))
            return done
        except BaseException as error:
            failure = dict(phase='FAILED', completed=list(done),
                           error=str(error) or type(error).__name__)
            try:
                self._cancel()
            except BaseException as cleanup_error:
                failure['cleanup_error'] = str(cleanup_error) or type(cleanup_error).__name__
            self._record(failure)
            raise
        finally:
            self._lock.release()

    def cancel(self) -> None:
        self._stop.set()
        self._cancel()
