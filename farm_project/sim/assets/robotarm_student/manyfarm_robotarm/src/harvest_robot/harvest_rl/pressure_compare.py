"""Separate finite pressure reserve; simulated normal forces, no state writes."""
from dataclasses import dataclass, asdict
import math
import torch


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


def pressure_step(base, measured, origin, spent, scope, qualified, force_min,
                  *, spec, dt, max_error, lower, upper):
    """Keep the original4deg squeeze and add one finite offset after it completes.

    Force goal is a feedback trigger, not an injected force or new success gate.
    No closing after qualification loss. Opening/transport/release take priority
    in the caller. Spending is cumulative and never renewed by a target opening.
    """
    spec.validate()
    if abs(dt-.05)>1e-9:raise ValueError('Requires20Hz')
    if spec.goal_N == 0:
        return base.clone(), spent.clone(), torch.zeros_like(base), scope & False
    finite=torch.isfinite(base)&torch.isfinite(measured)&torch.isfinite(origin)&torch.isfinite(spent)&torch.isfinite(force_min)
    if not finite.all():raise ValueError('Nonfinite pressure feedback')
    cap=math.radians(spec.extra_close_deg)
    desired=(base-spent).maximum(measured-max_error).clamp(lower,upper)
    base_done=(origin-base)>=math.radians(4.)-1e-6
    loading=scope & qualified & base_done & (force_min<spec.goal_N)
    room=torch.minimum((cap-spent).clamp_min(0), (desired-lower).clamp_min(0))
    room=room.minimum((desired-measured+max_error).clamp_min(0))
    room=room.minimum((desired-origin+math.radians(4.+spec.extra_close_deg)).clamp_min(0))
    room=torch.where(room>1e-7,room,0.)
    increment=torch.where(loading,room.clamp_max(math.radians(spec.rate_deg_s)*dt),0.)
    target=torch.where(scope,desired-increment,base)
    return target,spent+increment,increment,loading
