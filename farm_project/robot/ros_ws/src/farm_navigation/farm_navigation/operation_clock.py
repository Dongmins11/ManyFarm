"""동작 판정용 초 단위 시계. 시뮬 pause 동안 예산을 소모하지 않는다."""
import time
from typing import Any


def operation_time(node: Any) -> float:
    """ROS 시계가 활성화된 시뮬은 /clock, 실물은 기존 단조 시계를 반환한다.

    /clock 최초 수신 전 값은 0이다. 호출자는 준비/취소를 계속 검사하며
    시계 수신을 기다린다. 실제시간 fallback으로 시뮬 예산을 소모하지 않는다.
    """
    # ROS 없이 client를 주입하는 독립 실행의 기존 단조 시계 계약을 유지한다.
    if node is None:
        return time.monotonic()
    clock = node.get_clock()
    if clock.ros_time_is_active:
        return clock.now().nanoseconds / 1e9
    return time.monotonic()
