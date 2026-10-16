"""60Hz r2 원본 계산에서 추출. 재생성: sim/tools/import_teacher60.py."""

import math

import torch

class BoundedGripPreload:
    def __init__(self, count, device, budget, rate):
        if not all(math.isfinite(x) and x > 0 for x in (budget, rate)):
            raise ValueError('Preload budget/rate must be finite and positive')
        self.budget, self.rate = budget, rate
        self.origin = torch.zeros(count, device=device)
        self.latched = torch.zeros(count, device=device, dtype=torch.bool)
        self.released = self.latched.clone()

    def reset(self, ids):
        self.origin[ids] = 0.
        self.latched[ids] = False
        self.released[ids] = False

    def step(self, previous, proposed, measured, action, eligible, *,
             speed, dt, max_error, lower, upper):
        command = action.clamp(-1., 1.)
        first = eligible & ~self.latched & (command <= 0)
        self.origin = torch.where(first, previous, self.origin)
        self.latched = eligible & (self.latched | first)
        # Opening disables automatic preload until explicit close/new grasp.
        self.released = eligible & (self.released | (command > 0))
        self.released &= command >= 0
        active = self.latched & ~self.released & (command <= 0)
        rate = min(self.rate, speed)
        increment = torch.where(command < 0, -command * rate * dt, rate * dt)
        desired = torch.maximum(previous - increment, self.origin - self.budget)
        desired = torch.maximum(desired, measured - max_error).clamp(lower, upper)
        neutral_released = eligible & self.released & (command == 0)
        result = torch.where(active, desired, proposed)
        result = torch.where(neutral_released, previous.clamp(lower, upper), result)
        held = eligible & (command == 0) & ((result - previous).abs() <= 1e-7)
        return result, held
