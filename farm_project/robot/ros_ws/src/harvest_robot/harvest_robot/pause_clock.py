"""0출력 대기만 유효 실행시간에서 뺀다. 갱신 중단은 대기로 추정하지 않는다."""
import math
import threading
import time

class PauseClock:
    def __init__(self, clock=time.monotonic, *, unlimited: bool = False) -> None:
        self._clock = clock
        self._unlimited = unlimited
        self._lock = threading.Lock()
        self._last = clock()
        self._active = False
        self._total = 0.

    def update(self, active: bool) -> float:
        with self._lock:
            now = self._clock()
            if now < self._last:
                raise RuntimeError('대기 시계 역행')
            if self._active:
                self._total += min(now-self._last, .2)
            self._last, self._active = now, active
            return self._total

    def counter(self) -> float:
        with self._lock:
            return self._total

    def scoped(self, allowance: float = 30.):
        """실행별 누계를 분리한다. 명시 선택 시 센서 대기 누적 상한을 두지 않는다."""
        started = self._clock()
        baseline = self.counter()
        elapsed = 0.
        lock = threading.Lock()
        def now() -> float:
            nonlocal elapsed
            with lock:
                credit = max(0., self.counter()-baseline)
                if not self._unlimited:
                    credit = min(allowance, credit)
                # 수신 주기보다 잦게 읽어도 누계를 잃지 않고, 시계 역행도 막는다.
                elapsed = max(elapsed, self._clock()-started-credit)
                return elapsed
        return now
