"""인계 전용 재관측 경계. 성공·새 Goal을 만들지 않고 호출자가 같은 검사를 다시 한다."""
from typing import Any, Callable
from farm_navigation.pose_provider import TransformUnavailable


class InputUnavailable(RuntimeError):
    """입력 부재/과거 만료. 미래 시각·비정상 값·좌표계 오류는 포함하지 않는다."""


class ClearancePending(InputUnavailable):
    """현재 자세에 대한 충돌 증명 대기. 이동 허가가 아니다."""


class WaitingPoses:
    """공통 TF 제공자는 그대로 두고 인계 조합에서만 재조회한다."""
    def __init__(self, source: Any, retry: Callable, unavailable: Callable) -> None:
        self.source, self.retry, self.unavailable = source, retry, unavailable

    def lookup(self, target: str, source: str, stamp_ns: int, check: Callable) -> Any:
        return self.retry(lambda: self.source.lookup(target, source, stamp_ns, check, on_unavailable=self.unavailable), check=check)

    def lookup_available_pair(self, targets: tuple, source: str, sample_stamp: Callable,
                              check: Callable) -> Any:
        return self.retry(lambda: self.source.lookup_available_pair(targets, source, sample_stamp, check), check=check)
