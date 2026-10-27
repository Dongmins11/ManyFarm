"""종료된 충돌 예측 Goal만 제한 횟수 재시도한다. 거리·속도 보호는 바꾸지 않는다."""
from collections.abc import Callable
import time

class Nav2ControlUnavailable(RuntimeError):
    """FollowPath가 충돌 예측 또는 원인 문구 없는 NO_VALID_CONTROL로 종료됐다."""

def run_with_collision_recovery(execute: Callable[[], int], ready: Callable[[], bool],
        stop: Callable[[], None], check: Callable[[], None], retries: int,
        log: Callable[[str], None], clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
        waiting: Callable[[bool], None] = lambda active: None) -> int:
    """취소·전체 실행 제한은 check가 담당한다. 회복 대기 중 항상 0 출력이다."""
    used = 0
    while True:
        check()
        try:
            return execute()
        except Nav2ControlUnavailable as error:
            stop()
            if used >= retries:
                log(f'COLLISION_RETRY_EXHAUSTED: retries={used}')
                raise
            used += 1
            earliest = clock() + 2.0
            deadline = clock() + 30.0
            log(f'COLLISION_RETRY_WAIT: retry={used}/{retries}, minimum_stop_s=2, cause={error}')
            waiting(True)
            try:
                while True:
                    check()
                    stop()
                    if clock() >= deadline:
                        raise TimeoutError('COLLISION_RETRY_NOT_READY: 30초 내 정지·TF 회복 미확인')
                    if clock() >= earliest and ready():
                        check()
                        log(f'COLLISION_RETRY_RESUME: retry={used}/{retries}')
                        break
                    sleep(.05)
            finally:
                waiting(False)
