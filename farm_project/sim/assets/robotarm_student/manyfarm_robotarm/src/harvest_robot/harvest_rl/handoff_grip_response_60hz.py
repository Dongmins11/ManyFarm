"""Separate, finite jaw-response comparisons. Never changes physical state or flags."""
from dataclasses import asdict, dataclass
import math
import torch

from .bounded_grip_60hz import BoundedGripPreload


@dataclass(frozen=True)
class GripResponse:
    mode: str = 'baseline'
    rate_deg_s: float = 6.
    weak_force_N: float = .12
    stop_force_N: float = .2

    def __post_init__(self):
        if self.mode not in ('baseline', 'fast', 'feedback'):
            raise ValueError('Unknown jaw response')
        if any(not math.isfinite(v) or v <= 0 for k, v in asdict(self).items() if k != 'mode'):
            raise ValueError('Finite positive response parameters required')
        if self.rate_deg_s > 10 or self.stop_force_N <= self.weak_force_N:
            raise ValueError('At most 10 degrees/s; ordered contact hysteresis required')


class HandoffGripResponse(BoundedGripPreload):
    """Same 4 degree origin budget/PD bound; optionally stop closing at contact.

    Feedback uses simulated normal force, not a measured STS3215 torque. A
    certified handoff may reacquire contact only while centered and attached.
    There is no measured-angle rebase or accumulated closing reserve.
    """
    def __init__(self, count, device, budget, rate, *, spec, feedback):
        super().__init__(count, device, budget, rate)
        if abs(budget - math.radians(4.)) > 1e-8:
            raise ValueError('The original four degree total closing bound is required')
        self.spec, self.feedback = spec, feedback
        if spec.mode != 'baseline':
            self.rate = math.radians(spec.rate_deg_s)
        self.loading = torch.ones(count, device=device, dtype=torch.bool)
        self.diagnostics = {}

    def reset(self, ids):
        super().reset(ids)
        self.loading[ids] = True

    def step(self, previous, proposed, measured, action, eligible, **kwargs):
        # Parent retains opening priority and the original max tracking error.
        result, held = super().step(previous, proposed, measured, action, eligible, **kwargs)
        if self.spec.mode == 'feedback':
            state = self.feedback()
            if state is None:
                # Only the first restored, certified state has no new sample.
                allowed = eligible
            else:
                minimum = state['fixed_force'].minimum(state['moving_force'])
                centered = (state['attached'] & ~state['failure'] & ~state['success']
                    & (state['distance'] < state['center_tolerance'])
                    & (state['slip'] < state['max_slip']) & torch.isfinite(minimum))
                self.loading = torch.where(minimum >= self.spec.stop_force_N, False,
                    torch.where(minimum < self.spec.weak_force_N, True, self.loading))
                allowed = centered & self.loading
            scoped = eligible & self.latched & ~self.released & (action <= 0)
            # Preserve any opening required by the unchanged PD-error bound.
            result = torch.where(scoped & ~allowed, torch.maximum(previous, result), result)
            held = eligible & (action == 0) & ((result-previous).abs() <= 1e-7)
        self.diagnostics = dict(response_loading=self.loading.clone(),
            response_close_rad=(self.origin-result).clamp_min(0),
            response_jaw_target_rad=result.clone())
        return result, held
