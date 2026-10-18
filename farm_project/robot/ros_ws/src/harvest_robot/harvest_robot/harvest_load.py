"""현재 실행의 누적 실적을 인계 이후 적재 개수로 합산한다. ROS·장치에 의존하지 않는다."""
from .contract import validate_counts


class HarvestLoad:
    """호출자는 node.lock으로 보호한다. 수량은 현재 프로세스 실행 동안 유지한다."""

    def __init__(self) -> None:
        self.loaded_count = 0
        self._counts = (0, 0)
        self._active = False

    def begin(self) -> None:
        """새 좌표의 Action 시작. 이전 좌표의 적재량은 보존한다."""
        self._counts = (0, 0)
        self._active = True

    def observe(self, success: int, failed: int) -> None:
        """Feedback/최종 Result의 성공 증가분만 반영한다. 같은 값은 중복 합산하지 않는다."""
        if not self._active:
            raise ValueError('활성 수확 실행 없이 수량을 반영할 수 없습니다.')
        counts = validate_counts(success, failed, self._counts)
        total = self.loaded_count + success - self._counts[0]
        if total > 2147483647:
            raise ValueError('적재 개수가 RobotStatus int32 범위를 초과했습니다.')
        self.loaded_count, self._counts = total, counts

    def end(self) -> None:
        """성공·실패·취소 모두 이미 확정한 수확량을 보존한다."""
        self._active = False

    def reset_after_transfer(self) -> None:
        """수확 종료 후 물리 인계 완료 경계에서만 호출한다."""
        if self._active:
            raise ValueError('수확 실행 중 적재량 초기화 불가')
        self.loaded_count = 0
        self._counts = (0, 0)
