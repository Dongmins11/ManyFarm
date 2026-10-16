"""60Hz r2 원본 계산에서 추출. 재생성: sim/tools/import_teacher60.py."""

from dataclasses import dataclass

import math

@dataclass(frozen=True)

class SurfaceSpec:
    effective_friction: float = 1.
    pad_mode: str = 'none'
    thickness_m: float = .001
    recess_m: float = .002
    half_width_m: float = .012

    def validate(self):
        if (not math.isfinite(self.effective_friction)
                or not 1 <= self.effective_friction <= 1.6
                or self.pad_mode not in ('none', 'flat', 'trough')
                or (self.thickness_m, self.recess_m, self.half_width_m) != (.001, .002, .012)):
            raise ValueError('Explicit mu1..1.6, none/flat/trough, fixed1mm/2mm/24mm geometry')
        return self

    @property
    def jaw_friction(self):
        # Fruit stays1.0 and both materials use average combination.
        return 2*self.effective_friction-1.
