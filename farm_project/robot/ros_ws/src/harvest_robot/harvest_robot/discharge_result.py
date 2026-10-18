"""배출 완료 증거의 공통 판정. ROS 형식·감지 방식과 독립적이다.

한 인계마다 새 인스턴스를 생성한다. Action 성공과 빈 오류 배열을 함께
확인한다. 실제 센서 판정은 Jetson 책임이며 여기서 추정하지 않는다.
"""
from dataclasses import dataclass
from .transfer_devices import DeviceResult


@dataclass(frozen=True)
class DischargeReply:
    transfer_id: str
    error_codes: list[str]
    error_message: str


class DischargeEvidence:
    """단일 요청의 결과만 보관한다. 취소/실패 후 늦은 성공으로 복구하지 않는다."""

    def __init__(self, transfer_id: str) -> None:
        if not isinstance(transfer_id, str) or not transfer_id.strip():
            raise ValueError('현재 인계 식별값이 필요합니다.')
        self.transfer_id = transfer_id
        self._requested = False
        self._terminal = False
        self._verified = False

    def request_once(self) -> None:
        """전송 직전에 호출한다. 전송 예외가 나도 자동 재전송하지 않는다."""
        if self._requested or self._terminal:
            raise RuntimeError('배출 재요청 금지')
        self._requested = True

    def finish(self, reply: DischargeReply, *, action_succeeded: bool) -> DeviceResult:
        """현재 Goal의 terminal Result만 전달한다. Feedback으로 호출하지 않는다."""
        if not self._requested or self._terminal:
            return DeviceResult(True, False, '요청 전 또는 종료 후 배출 응답')
        self._terminal = True
        self._verified = (
            reply.transfer_id == self.transfer_id
            and isinstance(reply.error_codes, (list, tuple))
            and len(reply.error_codes) == 0
            and isinstance(reply.error_message, str)
            and action_succeeded is True)
        detail = '' if self._verified else (
            '배출 전체 완료 미확인: ' + str(reply.error_codes) + ' ' + str(reply.error_message))
        return DeviceResult(True, self._verified, detail)

    def invalidate(self) -> None:
        """실패·취소·시간초과 시 증거를 폐기한다. 물리 정지를 뜻하지 않는다."""
        self._terminal = True
        self._verified = False

    def restore_check(self) -> DeviceResult:
        """닫기 재요청 없이 현재 인계의 전체 완료 증거만 확인한다."""
        return DeviceResult(True, self._verified,
                            '' if self._verified else '배출·닫기 전체 완료 증거 없음')
