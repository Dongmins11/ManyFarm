"""Diagnostic command budget, independent of task success and physical state."""
import torch


def bounded_increment(velocity, jacobian, spent, scope, budget=.05, dt=.05):
    if budget <= 0 or abs(dt-.05) > 1e-12:
        raise ValueError('Requires positive command distance and original20Hz')
    distance = (jacobian[:, :3]@velocity[:, :, None]).squeeze(-1).norm(dim=-1)*dt
    scale = ((budget-spent).clamp_min(0)/distance.clamp_min(1e-12)).clamp_max(1.)
    result = torch.where(scope[:, None], velocity*scale[:, None], velocity)
    used = torch.where(scope, distance*scale, 0.)
    return result, spent+used
