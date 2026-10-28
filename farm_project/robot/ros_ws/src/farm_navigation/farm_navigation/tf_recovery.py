"""종료 확인된 TF 오류만 복구한다. 미확정 Goal이나 다른 오류를 재전송하지 않는다."""
from collections.abc import Callable
import time

class Nav2TFError(RuntimeError):
    """FollowPath가 TF_ERROR로 ABORTED 응답을 반환했다."""


def run_with_tf_recovery(execute: Callable[[], int], ready: Callable[[], bool],
                         stop: Callable[[], None], check: Callable[[], None],
                         feedback_time: Callable[[], float], timeout: float,
                         log: Callable[[str], None],
                         clock: Callable[[], float] = time.monotonic,
                         sleep: Callable[[float], None] = time.sleep, *,
                         wait_forever: bool = False,
                         waiting: Callable[[bool], None] = lambda active: None) -> int:
    deadline = None
    failed_at = None
    while True:
        check()
        try:
            return execute()
        except Nav2TFError:
            # 실제 제어 Feedback이 다시 나왔을 때만 연속 장애 구간이 끝난 것으로 본다.
            if deadline is None or (failed_at is not None and feedback_time() > failed_at):
                deadline = clock() + timeout
            failed_at = clock()
            stop()
            log('TF_RECOVERY_WAIT: 정지 유지·TF 재확보 후 같은 경로 재개'
                if wait_forever else f'TF_RECOVERY_WAIT: 최대 {timeout:.1f}초, 정지 후 같은 경로 재개')
            waiting(True)
            next_log = clock() + 5.0
            try:
                while True:
                    check()  # 관제 취소·종료 신호를 삼키지 않는다.
                    stop()
                    if not wait_forever and clock() >= deadline:
                        log('TF_RECOVERY_TIMEOUT')
                        raise TimeoutError(f'TF_RECOVERY_TIMEOUT: {timeout:.1f}초 내 복구되지 않음')
                    if ready():
                        log('TF_RECOVERY_RESUME')
                        break
                    if clock() >= next_log:
                        log('TF_RECOVERY_WAIT: TF·정지 확인 대기 중')
                        next_log = clock() + 5.0
                    sleep(0.05)
            finally:
                waiting(False)
