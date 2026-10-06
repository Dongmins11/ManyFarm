"""기존 기하 코드가 사용하는 각도 정규화(rad)."""
import math

def wrap_angle(a: float) -> float:
    if not math.isfinite(a):
        raise ValueError("non-finite angle")
    return (a + math.pi) % (2 * math.pi) - math.pi
