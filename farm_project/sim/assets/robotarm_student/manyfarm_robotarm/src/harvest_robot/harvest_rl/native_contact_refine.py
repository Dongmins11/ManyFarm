"""Measured-motion/contact-reserve reward. No state or actuator writes."""
from dataclasses import asdict, dataclass
import math
import torch


@dataclass(frozen=True)
class ContactRefineSpec:
    transverse_speed_m_s: float = .020
    transverse_weight: float = 1.
    angular_speed_rad_s: float = .20
    angular_weight: float = .6
    reserve_fraction: float = .75
    reserve_min_N: float = .12
    reserve_max_N: float = .60
    reserve_weight: float = .6
    collision_margin_N: float = 1.
    collision_scale_N: float = 3.
    collision_weight: float = 2.
    cost_square_cap: float = 4.
    hard_fraction: float = .25
    neighbors_per_anchor: int = 8
    exploration_std: float = .03

    def __post_init__(self):
        if any(not math.isfinite(x) or x <= 0 for x in asdict(self).values()):
            raise ValueError('Positive finite refinement parameters required')
        if not 0 < self.reserve_fraction <= 1 or not 0 < self.hard_fraction < 1:
            raise ValueError('Invalid reserve/sampling fractions')
        if not .08 < self.reserve_min_N < self.reserve_max_N:
            raise ValueError('Reserve must precede unchanged .08N loss gate')


SPEC = ContactRefineSpec()
TRAIN_ANCHOR_IDS = (19, 39)  # TRAIN failures10/22; never held-out447/473/494.


def training_pool(pool, bank_ids, points, *, train_end, spec=SPEC):
    """Exactly75% uniform +25% train-neighbor mixture; random poses unchanged."""
    if spec.hard_fraction != .25:
        raise ValueError('This version fixes the mixture at25%')
    if train_end < 1 or (bank_ids < 0).any() or (bank_ids >= train_end).any():
        raise ValueError('Original bank-derived train split required')
    chosen = []
    for anchor in TRAIN_ANCHOR_IDS:
        found = (bank_ids == anchor).nonzero().flatten()
        if len(found) != 1 or not (pool == found[0]).any():
            raise ValueError('Training anchor absent from current reachable domain')
        distances = (points[pool]-points[found[0]]).norm(dim=-1)
        chosen.append(pool[distances.argsort()[:spec.neighbors_per_anchor]])
    hard = torch.cat(chosen).unique(sorted=True)
    # Every original index gets3H copies; each hard index getsP extra copies.
    # Total mass =4PH. Uniform positions outside hard are still reachable.
    mixed = torch.cat((pool.repeat(3*len(hard)), hard.repeat(len(pool))))
    return mixed, hard


class ContactMotionReward:
    def __init__(self, n, device, spec=SPEC):
        self.spec = spec
        self.previous_tcp = torch.zeros(n, 3, device=device)
        self.previous_quat = torch.zeros(n, 4, device=device)
        self.previous_quat[:, 0] = 1.
        self.reserve = torch.zeros(n, device=device)
        self.seen = torch.zeros(n, dtype=torch.bool, device=device)

    def reset(self, ids):
        self.seen[ids] = False
        self.reserve[ids] = 0.

    def handoff(self, mask, tcp, quat, fixed, moving):
        self.previous_tcp[mask] = tcp[mask]
        self.previous_quat[mask] = quat[mask]
        s = self.spec
        self.reserve[mask] = (torch.minimum(fixed, moving)[mask]*s.reserve_fraction).clamp(
            s.reserve_min_N, s.reserve_max_N)
        self.seen[mask] = True

    def step(self, *, active, tcp, quat, axis, fixed, moving, arm_force, dt):
        if abs(dt-.05) > 1e-9:
            raise ValueError('Measured motion uses20Hz policy time')
        a = torch.as_tensor(axis, device=tcp.device, dtype=tcp.dtype)
        if a.shape != (3,) or not torch.isfinite(a).all() or a.norm() < 1e-9:
            raise ValueError('Nonzero finite pull axis required')
        if not all(torch.isfinite(v).all() for v in (tcp, quat, fixed, moving, arm_force)):
            raise FloatingPointError('Nonfinite measured motion/contact')
        if (quat.norm(dim=-1) < 1e-8).any():
            raise ValueError('Zero hand quaternion')
        a = a/a.norm(); s = self.spec; scope = active & self.seen
        velocity = (tcp-self.previous_tcp)/dt
        lateral = (velocity-(velocity*a).sum(-1)[:, None]*a).norm(dim=-1)
        q = quat/quat.norm(dim=-1, keepdim=True)
        ref = self.previous_quat/self.previous_quat.norm(dim=-1, keepdim=True).clamp_min(1e-12)
        # atan2 is stable for tiny motion and invariant under q -> -q.
        dot = (q*ref).sum(-1).abs().clamp(0., 1.)
        angular = 2*torch.atan2((1-dot.square()).clamp_min(0.).sqrt(), dot)/dt
        minimum = torch.minimum(fixed, moving).clamp_min(0.)
        shortage = ((self.reserve-minimum).clamp_min(0.)/self.reserve.clamp_min(.08)).clamp_max(1.)
        def cost(v, scale, weight):
            return dt*weight*(v/scale).square().clamp_max(s.cost_square_cap)*scope
        transverse_cost = cost(lateral, s.transverse_speed_m_s, s.transverse_weight)
        angular_cost = cost(angular, s.angular_speed_rad_s, s.angular_weight)
        reserve_cost = dt*s.reserve_weight*shortage.square()*scope
        collision_cost = cost((arm_force-s.collision_margin_N).clamp_min(0.),
            s.collision_scale_N, s.collision_weight)
        total = transverse_cost+angular_cost+reserve_cost+collision_cost
        self.previous_tcp.copy_(tcp.detach()); self.previous_quat.copy_(quat.detach())
        return total, dict(transverse_speed_m_s=lateral, angular_speed_rad_s=angular,
            reserve_N=self.reserve.clone(), min_force_N=minimum, reserve_shortage=shortage,
            transverse_cost=transverse_cost, angular_cost=angular_cost,
            reserve_cost=reserve_cost, collision_cost=collision_cost, total_cost=total)
