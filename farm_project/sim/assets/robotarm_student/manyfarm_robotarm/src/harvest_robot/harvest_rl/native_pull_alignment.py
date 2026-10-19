"""Reward-only pull refinement relative to the measured handoff, not the plant.

No physical state, action, gate or contact-force writes. A tilted/deformed fruit
already present at handoff is not charged as new lateral hand motion.
"""
from dataclasses import asdict, dataclass
import math
import torch


@dataclass(frozen=True)
class AlignmentSpec:
    lateral_scale_m: float = .005
    lateral_weight: float = 1.6
    rotation_scale_rad: float = math.radians(10.)
    rotation_weight: float = .8
    center_margin_m: float = .006
    center_limit_m: float = .010
    center_weight: float = 1.
    slip_scale_m: float = .006
    slip_weight: float = 1.
    extra_contact_loss_cost: float = 4.
    maximum_normalized_square: float = 4.
    exploration_std: float = .04

    def __post_init__(self):
        if any(not math.isfinite(v) or v <= 0 for v in asdict(self).values()):
            raise ValueError('Positive finite alignment parameters required')
        if not self.center_margin_m < self.center_limit_m:
            raise ValueError('Center margin must precede the unchanged10mm gate')


SPEC = AlignmentSpec()


class NativePullAlignment:
    def __init__(self, n, device, spec=SPEC):
        self.spec = spec
        self.origin = torch.zeros(n, 3, device=device)
        self.quat = torch.zeros(n, 4, device=device); self.quat[:, 0] = 1.
        self.seen = torch.zeros(n, device=device, dtype=torch.bool)
        self.was_qualified = self.seen.clone()

    def reset(self, ids):
        self.seen[ids] = False; self.was_qualified[ids] = False

    def handoff(self, mask, tcp, quat):
        self.origin[mask] = tcp[mask]; self.quat[mask] = quat[mask]
        self.seen[mask] = True; self.was_qualified[mask] = True

    def step(self, *, active, attached, qualified, tcp, quat, axis, center, slip, dt):
        if abs(dt-.05) > 1e-9:
            raise ValueError('Alignment reward retains20Hz policy time')
        a = torch.as_tensor(axis, device=tcp.device, dtype=tcp.dtype)
        if a.shape != (3,) or not torch.isfinite(a).all() or a.norm() < 1e-9:
            raise ValueError('Nonzero finite world pull axis required')
        a = a/a.norm(); s = self.spec
        offset = tcp-self.origin
        axial = (offset*a).sum(-1)
        lateral = (offset-axial[:, None]*a).norm(dim=-1)
        q = quat/quat.norm(dim=-1, keepdim=True).clamp_min(1e-12)
        ref = self.quat/self.quat.norm(dim=-1, keepdim=True).clamp_min(1e-12)
        rotation = 2*torch.acos((q*ref).sum(-1).abs().clamp(0., 1.))
        scope = active & self.seen
        pulling = scope & attached
        def cost(value, scale, weight, mask):
            return dt*weight*(value/scale).square().clamp_max(s.maximum_normalized_square)*mask
        lateral_cost = cost(lateral, s.lateral_scale_m, s.lateral_weight, pulling)
        rotation_cost = cost(rotation, s.rotation_scale_rad, s.rotation_weight, pulling)
        center_cost = cost((center-s.center_margin_m).clamp_min(0.),
                           s.center_limit_m-s.center_margin_m, s.center_weight, scope)
        slip_cost = cost(slip, s.slip_scale_m, s.slip_weight, scope)
        lost = scope & self.was_qualified & ~qualified
        loss_cost = s.extra_contact_loss_cost*lost
        self.was_qualified = torch.where(scope, qualified, self.was_qualified)
        total = lateral_cost+rotation_cost+center_cost+slip_cost+loss_cost
        if not torch.isfinite(total).all():
            raise FloatingPointError('Nonfinite native alignment reward')
        return total, dict(axial_m=axial, lateral_m=lateral, rotation_rad=rotation,
            lateral_cost=lateral_cost, rotation_cost=rotation_cost, center_cost=center_cost,
            slip_cost=slip_cost, extra_loss_cost=loss_cost, total_cost=total)
