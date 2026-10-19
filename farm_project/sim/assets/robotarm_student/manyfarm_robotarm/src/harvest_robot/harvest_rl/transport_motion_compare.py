"""Bounded transport-only candidates; keep joint guards, ramp and20Hz unchanged."""
import math
import torch


def validate_motion(speed, orientation_length):
    if not math.isfinite(speed) or not 0 < speed <= .035:
        raise ValueError('TCP speed must be in(0,0.035]m/s')
    if not math.isfinite(orientation_length) or not .02 <= orientation_length <= .04:
        raise ValueError('Orientation length must be in[0.02,0.04]m')


def solve_motion(jacobian, wanted, targets, lower, upper, ramp, *, speed=.035, orientation_length=.02):
    validate_motion(speed, orientation_length)
    j = jacobian.clone(); j[:, 3:] *= orientation_length
    eye = torch.eye(5, device=j.device, dtype=j.dtype)
    lo = lower[:5].expand_as(targets).clone()
    hi = upper[:5].expand_as(targets).clone(); hi[:, 2] = hi[:, 2].clamp_max(1.45)
    blocked = torch.zeros_like(targets, dtype=torch.bool)
    for _ in range(6):
        js = torch.where(blocked[:, None, :], 0., j)
        velocity = torch.linalg.solve(js.transpose(1, 2)@js+.003**2*eye,
            js.transpose(1, 2)@wanted[:, :, None]).squeeze(-1)
        velocity = torch.where(blocked, 0., velocity)
        limit = .3*ramp[:, None]
        new = (((targets-.05*limit <= lo+.005) & (velocity < 0))
               | ((targets+.05*limit >= hi-.005) & (velocity > 0)))
        if torch.equal(blocked | new, blocked): break
        blocked |= new
    scale = (.3*ramp/velocity.abs().amax(-1).clamp_min(1e-12)).clamp_max(1.)
    predicted = (jacobian[:, :3]@velocity[:, :, None]).squeeze(-1)
    scale = scale.minimum((speed*ramp/predicted.norm(dim=-1).clamp_min(1e-12)).clamp_max(1.))
    return velocity*scale[:, None], blocked
