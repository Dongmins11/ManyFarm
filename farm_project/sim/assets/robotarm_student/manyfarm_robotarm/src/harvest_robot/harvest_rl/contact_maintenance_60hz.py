"""Probe-only contact maintenance with an immutable origin and finite budget.

Normal contact forces here are simulator feedback, not calibrated motor torque.
The frozen V4 and position-only preload implementations remain unchanged.
"""
from dataclasses import asdict, dataclass
import math

import torch

from .bounded_grip_60hz import BoundedGripPreload


@dataclass(frozen=True)
class Maintenance:
    extra_deg: float = 0.
    extra_rate_deg_s: float = 2.
    initial_hold_s: float = 1.
    weak_force_N: float = .6
    recovered_force_N: float = .8
    weak_duration_s: float = .1

    def __post_init__(self):
        if not math.isfinite(self.extra_deg) or not 0 <= self.extra_deg <= .5:
            raise ValueError('Extra closing must be finite and between 0 and 0.5 degrees')
        if any(not math.isfinite(v) or v <= 0 for k, v in asdict(self).items() if k != 'extra_deg'):
            raise ValueError('Maintenance rates and thresholds must be finite and positive')
        if self.recovered_force_N <= self.weak_force_N:
            raise ValueError('Recovery threshold must exceed weak-contact threshold')


class ContactMaintenance(BoundedGripPreload):
    def __init__(self, count, device, budget, rate, *, cfg, feedback):
        super().__init__(count, device, budget, rate)
        self.cfg, self.feedback, self.base_budget = cfg, feedback, budget
        self.age = torch.zeros(count, device=device)
        self.weak_age = self.age.clone()
        self.extra = self.age.clone()
        self.requested = self.latched.clone()
        self.adjusting = self.latched.clone()

    def reset(self, ids):
        super().reset(ids)
        self.age[ids] = self.weak_age[ids] = self.extra[ids] = 0.
        self.requested[ids] = self.adjusting[ids] = False

    def step(self, previous, proposed, measured, action, eligible, **kwargs):
        dt = kwargs['dt']
        first = eligible & ~self.latched & (action <= 0)
        self.age[first] = self.weak_age[first] = self.extra[first] = 0.
        self.requested[first] = False
        self.adjusting.zero_()
        if self.cfg.extra_deg:
            state = self.feedback()
            permitted = torch.zeros_like(eligible)
            minimum = torch.zeros_like(previous)
            if state is not None:
                # Previous physical update, never reset-initialized or predicted contact.
                permitted = (state['qualified'] & state['attached'] & ~state['failure']
                             & ~state['success'] & (state['slip'] < state['max_slip'])
                             & (state['distance'] < state['center_tolerance']))
                minimum = torch.minimum(state['fixed_force'], state['moving_force'])
                permitted &= torch.isfinite(minimum)
            active = (eligible & self.latched & ~self.released & (action <= 0)
                      & permitted & (self.age >= self.cfg.initial_hold_s - 1e-7))
            weak = active & (minimum < self.cfg.weak_force_N)
            self.weak_age = torch.where(weak, self.weak_age + dt, torch.zeros_like(self.weak_age))
            self.requested = active & (self.requested | (self.weak_age >= self.cfg.weak_duration_s - 1e-7))
            self.requested &= minimum < self.cfg.recovered_force_N
            self.adjusting = self.requested & (self.extra < math.radians(self.cfg.extra_deg) - 1e-7)
            rate = min(math.radians(self.cfg.extra_rate_deg_s), kwargs['speed'])
            # Allocate only actual usable target movement; no accumulated reserve while blocked by PD limits.
            margin = (previous - (measured - kwargs['max_error'])).clamp_min(0)
            increment = torch.minimum(torch.full_like(previous, rate * dt), margin)
            self.extra += torch.where(self.adjusting, increment, torch.zeros_like(increment))
            self.extra.clamp_(max=math.radians(self.cfg.extra_deg))
        self.budget = self.base_budget + self.extra
        result, held = super().step(previous, proposed, measured, action, eligible, **kwargs)
        # After preload, never close faster than the maintenance rate, including explicit close.
        if self.cfg.extra_deg:
            capped = eligible & self.latched & ~self.released & (action <= 0) & (self.age >= self.cfg.initial_hold_s - 1e-7)
            limit = min(math.radians(self.cfg.extra_rate_deg_s), kwargs['speed']) * dt
            result = torch.where(capped, torch.maximum(result, previous - limit), result)
            result = torch.where(capped & ~permitted, torch.maximum(result, previous), result)
            held = eligible & (action == 0) & ((result - previous).abs() <= 1e-7)
        self.age = torch.where(eligible, self.age + dt, torch.zeros_like(self.age))
        return result, held


def feedback_from_env(env):
    snap = getattr(env, 'followup_snapshot', None)
    if snap is None:
        return None
    d = snap['diagnostics']
    return dict(qualified=snap['qualified'], attached=snap['attached'], failure=snap['failure'],
                success=snap['success'], slip=snap['slip'], distance=d['distance_m'],
                fixed_force=d['fixed_force_N'], moving_force=d['moving_force_N'],
                max_slip=env.settings.max_slip, center_tolerance=env.settings.grasp_center_tolerance)
