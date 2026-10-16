"""60Hz r2 원본 계산에서 추출. 재생성: sim/tools/import_teacher60.py."""

from dataclasses import dataclass

import math

from .pull_ready_60hz import prepare_actions as parent_actions

@dataclass(frozen=True)

class PullRefinement:
    ramp_s: float = 0.
    initial_scale: float = .2
    hold_after_detach: bool = False

    def __post_init__(self):
        if not math.isfinite(self.ramp_s) or self.ramp_s < 0:
            raise ValueError('Ramp duration must be finite and nonnegative')
        if not math.isfinite(self.initial_scale) or not 0 < self.initial_scale <= 1:
            raise ValueError('Initial arm scale must be in (0, 1]')

def prepare_actions(actions, elapsed, confirmed, release_intent, attached, valid_detach, spec):
    """Modify commands only; keep loaded targets, real contact and failure criteria.

    Ramp is applied to bounded actions so a saturated proposal cannot defeat it.
    Ramp=0, hold=False is byte-for-byte the original ready action computation.
    Zero arm command maintains the existing target, never measured joint rebasing.
    """
    result = parent_actions(actions, elapsed, confirmed, release_intent)
    scope = confirmed & ~release_intent
    scale = elapsed.new_ones(elapsed.shape)
    if spec.ramp_s:
        fraction = ((elapsed - 2.) / spec.ramp_s).clamp(0., 1.)
        scale = spec.initial_scale + (1. - spec.initial_scale) * fraction
        ramping = scope & (elapsed >= 2. - 1e-7) & (elapsed < 2. + spec.ramp_s)
        result[ramping, :5] = result[ramping, :5].clamp(-1., 1.) * scale[ramping, None]
    holding = scope & valid_detach & ~attached if spec.hold_after_detach else scope & False
    result[holding, :5] = 0.
    return result, scale, holding
