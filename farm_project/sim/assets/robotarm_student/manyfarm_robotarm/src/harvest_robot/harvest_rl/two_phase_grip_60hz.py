"""Finite settling preload followed by the original load-bearing closing rate."""
from dataclasses import dataclass
import math
import torch
from .handoff_grip_response_60hz import GripResponse, HandoffGripResponse


@dataclass(frozen=True)
class TwoPhaseGripSpec:
    settle_s: float = 2.
    settle_rate_deg_s: float = 6.
    pull_rate_deg_s: float = 2.
    weak_force_N: float = .12
    stop_force_N: float = .2

    def __post_init__(self):
        if self.settle_s != 2. or self.pull_rate_deg_s != 2.:
            raise ValueError('This comparison retains 2s settling and original 2 degrees/s load rate')
        GripResponse('feedback', self.settle_rate_deg_s, self.weak_force_N, self.stop_force_N)


class TwoPhaseGrip(HandoffGripResponse):
    def __init__(self, count, device, budget, rate, *, spec, feedback):
        initial = GripResponse('feedback',spec.settle_rate_deg_s,spec.weak_force_N,spec.stop_force_N)
        super().__init__(count,device,budget,rate,spec=initial,feedback=feedback)
        self.phase_spec = spec
        self.age = torch.zeros(count,device=device)
        self.ticks = torch.zeros(count,device=device,dtype=torch.long)

    def reset(self, ids):
        super().reset(ids)
        self.age[ids] = 0.
        self.ticks[ids] = 0

    def step(self, previous, proposed, measured, action, eligible, **kwargs):
        result, held = super().step(previous,proposed,measured,action,eligible,**kwargs)
        if abs(kwargs['dt']-.05)>1e-9:raise ValueError('Exactly 20Hz required')
        loading_phase = self.ticks >= round(self.phase_spec.settle_s/kwargs['dt'])
        # Compute the unchanged slow, finite preload once per policy tick.
        # Both phases share the SAME origin/budget and release latch.
        command = action.clamp(-1.,1.)
        rate = min(math.radians(self.phase_spec.pull_rate_deg_s),kwargs['speed'])
        increment = torch.where(command < 0,-command*rate*kwargs['dt'],rate*kwargs['dt'])
        desired = torch.maximum(previous-increment,self.origin-self.budget)
        desired = torch.maximum(desired,measured-kwargs['max_error']).clamp(kwargs['lower'],kwargs['upper'])
        active = self.latched & ~self.released & (command <= 0)
        original = torch.where(active,desired,proposed)
        neutral_released = eligible & self.released & (command == 0)
        original = torch.where(neutral_released,previous.clamp(kwargs['lower'],kwargs['upper']),original)
        result = torch.where(loading_phase,original,result)
        held = eligible & (command == 0) & ((result-previous).abs() <= 1e-7)
        self.ticks = torch.where(eligible,self.ticks+1,0)
        self.age = self.ticks.float()*kwargs['dt']
        self.diagnostics.update(response_loading_phase=loading_phase.clone(),
            response_close_rad=(self.origin-result).clamp_min(0),response_jaw_target_rad=result.clone())
        return result,held
