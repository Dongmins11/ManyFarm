"""명시적인 시뮬 수확 활동 요청의 세션·순서·유효기간을 검사합니다.

이동 Goal, 도착, 작업 완료를 팔 활동으로 해석하지 않습니다. 유효한 true를
보낸 시각부터 lease_s 동안만 활성 상태이며, 새 세션에는 이전 상태를 넘기지 않습니다.
"""
import math
import time
from typing import Any


def _finite_number(value: Any) -> bool:
    """JSON 숫자만 허용하고 bool·문자열·비유한 시간값을 거절합니다."""
    if type(value) not in (int, float):
        return False
    try:
        return math.isfinite(value)
    except OverflowError:
        return False


class ActivityGate:
    """한 시뮬 세션의 한 로봇 활동 요청만 받는 독립 gate입니다."""

    def __init__(self, session: str, robot_id: str, lease_s: float) -> None:
        if type(session) is not str or not session or type(robot_id) is not str or not robot_id:
            raise ValueError('활동 gate에는 비어 있지 않은 session과 robot_id가 필요합니다.')
        if not _finite_number(lease_s) or lease_s <= 0:
            raise ValueError('활동 lease_s는 유한한 양수 초여야 합니다.')
        self._session = session
        self._robot_id = robot_id
        self._lease_s = float(lease_s)
        self._sequence = -1
        self._sent = -math.inf
        self._active = False

    def accept(self, message: Any, now: float | None = None) -> bool:
        """신선한 요청만 저장합니다. 잘못된 요청은 기존 상태를 변경하지 않습니다."""
        now = time.monotonic() if now is None else now
        if not isinstance(message, dict) or not _finite_number(now):
            return False
        if (message.get('kind') != 'harvest_activity'
                or message.get('session') != self._session
                or message.get('robot_id') != self._robot_id):
            return False
        sequence, sent, active = message.get('seq'), message.get('sent'), message.get('active')
        if type(sequence) is not int or sequence < 0 or sequence <= self._sequence:
            return False
        if type(active) is not bool or not _finite_number(sent):
            return False
        if not 0 <= now - sent <= self._lease_s:
            return False
        self._sequence, self._sent, self._active = sequence, float(sent), active
        return True

    def value(self, now: float | None = None) -> bool:
        """송신 시각 기준으로 아직 유효한 true만 반환합니다. 재전송은 하지 않습니다."""
        now = time.monotonic() if now is None else now
        return bool(self._active and _finite_number(now) and 0 <= now - self._sent <= self._lease_s)
