"""Bounded command candidates; no writes to contacts, physics or outcome flags."""
from dataclasses import dataclass, asdict
import math
import torch

from .handoff_grip_response_60hz import HandoffGripResponse


@dataclass(frozen=True)
class RetentionSpec:
    staged_preload: bool = False
    short_detach_hold: bool = False
    settle_s: float = 2.
    settle_cap_deg: float = 3.
    pull_cap_deg: float = 4.
    detach_hold_limit_s: float = .6

    def __post_init__(self):
        if type(self.staged_preload) is not bool or type(self.short_detach_hold) is not bool:
            raise ValueError('Boolean comparison switches required')
        if any(not math.isfinite(v) for k,v in asdict(self).items() if type(v) is not bool):
            raise ValueError('Finite comparison parameters required')
        if (self.settle_s != 2. or self.settle_cap_deg != 3. or self.pull_cap_deg != 4.
                or not .5 <= self.detach_hold_limit_s <= 1.):
            raise ValueError('Preserve2s settle,3/4 degree origin caps and a short finite hold')


class StagedOriginPreload(HandoffGripResponse):
    """A single unchanged origin; cap3 during settling, cap4 while pulling.

    The six degrees/s rate, release latch and original PD-error bound stay in
    the parent. This does not rebase the target at the phase transition.
    """
    def __init__(self,*args,comparison_spec,clock,**kwargs):
        super().__init__(*args,**kwargs)
        self.comparison_spec,self.clock=comparison_spec,clock

    def step(self,*args,**kwargs):
        elapsed=self.clock()
        if elapsed.shape != self.origin.shape or not torch.isfinite(elapsed).all():
            raise ValueError('Finite elapsed time per motor instance required')
        s=self.comparison_spec
        cap=torch.full_like(elapsed,s.pull_cap_deg)
        if s.staged_preload:
            cap=torch.where(elapsed<s.settle_s-1e-7,s.settle_cap_deg,cap)
        self.budget=cap*math.pi/180
        result,held=super().step(*args,**kwargs)
        self.diagnostics.update(staged_preload_cap_deg=cap.clone(),
            staged_preload_elapsed_s=elapsed.clone())
        return result,held


class ShortDetachHold:
    """Hold existing arm targets until retention or a finite timeout, never rebase.

    Reaction starts at the first policy tick observing *valid* detachment.
    Merely losing contact or an invalid break cannot enable this controller.
    Elapsed episode time and real retention/failure checks remain unchanged.
    """
    def __init__(self,count,device,spec):
        self.spec=spec
        self.observed_s=torch.full((count,),float('nan'),device=device)

    def reset(self,ids):
        self.observed_s[ids]=float('nan')

    def step(self,commands,elapsed,*,confirmed,release,attached,valid,retained):
        if commands.shape!=(len(self.observed_s),6) or not torch.isfinite(commands).all():
            raise ValueError('Finite six-dimensional command batch required')
        if elapsed.shape!=self.observed_s.shape or not torch.isfinite(elapsed).all():
            raise ValueError('Finite matching elapsed times required')
        scope=confirmed & ~release & ~attached & valid
        first=scope & torch.isnan(self.observed_s)
        self.observed_s=torch.where(first,elapsed,self.observed_s)
        age=torch.where(torch.isnan(self.observed_s),torch.zeros_like(elapsed),elapsed-self.observed_s)
        holding=(scope & ~retained & (age<self.spec.detach_hold_limit_s-1e-7)
                 & self.spec.short_detach_hold)
        result=commands.clone()
        result[holding,:5]=0.
        return result,dict(retention_arm_hold=holding,retention_observed_age_s=age)
