"""Finite, command-only load reserve for qualified free-fruit transport.

Force inputs are simulator diagnostics in N, not calibrated STS3215 telemetry.
No physical state, contact flags or success gates are written here.
"""
from dataclasses import dataclass, asdict
import math
import torch


@dataclass(frozen=True)
class LoadFollowSpec:
    extra_close_deg: float = .5
    close_rate_deg_s: float = 1.
    trigger_force_N: float = .5

    def validate(self):
        values = asdict(self)
        if not all(math.isfinite(v) for v in values.values()):
            raise ValueError('Load-follow parameters must be finite')
        if not 0 <= self.extra_close_deg <= .5:
            raise ValueError('Separate extra closing budget must be0..0.5deg')
        if not 0 < self.close_rate_deg_s <= 1.:
            raise ValueError('Extra closing rate must be(0,1]deg/s')
        if not .08 < self.trigger_force_N <= 1.:
            raise ValueError('Weak-load trigger must beabove original0.08N and<=1N')
        return self


def follow_step(previous, measured, origin, spent, eligible, force_min, *,
                spec, dt, lower, contact_threshold, max_error):
    """Consume one episode budget; never rebase origin, open, or recover lost contact.

    The parent retains its4deg preload. Only this extra reserve is charged here,
    even if the parent later opens near the box. That opening never refunds it.
    """
    spec.validate()
    if not 0 < dt <= .05+1e-9 or not 0 < contact_threshold < spec.trigger_force_N:
        raise ValueError('Requires original20Hz period/contact threshold')
    budget = math.radians(spec.extra_close_deg)
    rate = math.radians(spec.close_rate_deg_s)
    finite = torch.isfinite(previous) & torch.isfinite(measured) & torch.isfinite(origin)
    finite &= torch.isfinite(spent) & torch.isfinite(force_min)
    active = eligible & finite & (force_min > contact_threshold) & (force_min < spec.trigger_force_N)
    # All quantities are distances available in the closing (decreasing q) direction.
    # Float32 accumulation must not reopen a sub-microradian leftover budget
    # after the parent unloads. Treat that numerical residue as exhausted.
    remaining = torch.where(budget-spent > 1e-7, budget-spent, 0.)
    joint_room = (previous-lower).clamp(min=0.)
    error_room = (previous-measured+max_error).clamp(min=0.)
    total_room = (previous-origin+math.radians(4.+spec.extra_close_deg)).clamp(min=0.)
    amount = torch.minimum(torch.minimum(remaining, joint_room),
                           torch.minimum(error_room, total_room)).clamp(max=rate*dt)
    increment = torch.where(active, amount, 0.)
    return previous-increment, spent+increment, increment, active
