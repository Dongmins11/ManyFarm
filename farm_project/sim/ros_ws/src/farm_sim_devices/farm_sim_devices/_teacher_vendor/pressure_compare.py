"""60Hz r2 원본 계산에서 추출. 재생성: sim/tools/import_teacher60.py."""

from dataclasses import dataclass, asdict

import math

@dataclass(frozen=True)

class PressureSpec:
    goal_N: float = 0.
    extra_close_deg: float = 2.
    rate_deg_s: float = 2.

    def validate(self):
        if not all(math.isfinite(v) for v in asdict(self).values()):
            raise ValueError('Finite pressure settings required')
        if not 0 <= self.goal_N <= 4 or not 0 <= self.extra_close_deg <= 2 or not 0 < self.rate_deg_s <= 2:
            raise ValueError('Goal0..4N; extra0..2deg; rate(0,2]deg/s')
        return self
