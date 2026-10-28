"""명령 공백의 0출력 대기와 잘못된 명령의 영구 차단을 분리한다.

호출자는 기존 runtime lock 안에서 접근한다. accept 이후 waiting이면 반드시
0출력하며, 새 epoch/취소/소유권 검사는 기존 runtime이 계속 담당한다.
"""
import math
from typing import Callable, Any


class TransientCommandGate:
    def __init__(self, factory: Callable[[], Any], stopped_stamp: Callable[[], int | None],
                 settle_s: float) -> None:
        if not math.isfinite(settle_s) or settle_s <= 0:
            raise ValueError('재개 정지 확인 시간은 양수 초여야 합니다.')
        self.factory, self.stopped_stamp = factory, stopped_stamp
        self.settle_ns = int(settle_s * 1e9)
        self.enabled = False
        self.error = ''
        self.waiting = False
        self.last_received = None
        self.started = 0.
        self.first_stop = self.previous_stop = None

    def arm(self, now: float) -> None:
        if self.error:
            raise RuntimeError(self.error)
        self.enabled = True
        self.started = now
        self.last_received = None
        self.waiting = False
        self.first_stop = self.previous_stop = None

    def close(self) -> None:
        self.enabled = False
        self.first_stop = self.previous_stop = None

    def hold(self) -> None:
        """입력/충돌 증명이 없으면 정지 증거를 버리고 재개를 보류한다."""
        self.waiting = True
        self.first_stop = self.previous_stop = None

    def expired(self, now: float) -> bool:
        if not self.enabled:
            return False
        last = self.last_received if self.last_received is not None else self.started
        if now - last > (.3 if self.last_received is not None else 5.):
            self.waiting = True
            self.first_stop = self.previous_stop = None
        # 공백은 terminal 오류가 아니다. watchdog은 waiting 동안 반드시 0을 발행한다.
        return False

    def accept(self, linear: float, angular: float, now: float) -> bool:
        if not self.enabled or self.error:
            return False
        # 기존 gate의 방향/범위/NaN 검사를 새 실제 메시지마다 그대로 사용한다.
        validator = self.factory()
        validator.arm(now)
        if not validator.accept(linear, angular, now):
            self.error = validator.error
            self.enabled = False
            return False
        self.expired(now)
        self.last_received = now  # timer가 아닌 실제 명령에서만 갱신한다.
        if self.waiting:
            stamp = self.stopped_stamp()
            if stamp is None:
                self.first_stop = self.previous_stop = None
            elif self.previous_stop is not None and stamp < self.previous_stop:
                self.error = '재개 정지 확인 중 odom 시각 역행'
                self.enabled = False
                return False
            else:
                if self.previous_stop is None or stamp-self.previous_stop > 500_000_000:
                    self.first_stop = stamp
                self.previous_stop = stamp
                if stamp-self.first_stop >= self.settle_ns:
                    self.waiting = False
        return True
