"""Experimental reward only: real-contact axial pull, small lateral motion/rotation.

No commands, physical state writes, termination changes, or grasp flags here.
The reference rotation is the measured bank grasp pose, including random tilt.
"""
from dataclasses import asdict, dataclass
import math
from pathlib import Path
import torch
from .grasp_handoff_60hz import contract_digest
from .pull_refine_60hz import make_contract as original_contract
from .teacher_asset_reference import sha

ROOT=Path(__file__).resolve().parents[3]


@dataclass(frozen=True)
class ContactPullRewardSpec:
    axial_target_m: float=.025
    progress_weight: float=6.
    contact_weight: float=1.
    lateral_scale_m: float=.015
    lateral_weight: float=.8
    rotation_scale_rad: float=math.radians(20.)
    rotation_weight: float=.3
    timeout_cost: float=3.
    gamma: float=.99

    def __post_init__(self):
        if any(not math.isfinite(v) or v < 0 for v in asdict(self).values()):
            raise ValueError('Reward parameters must be finite and nonnegative')
        if min(self.axial_target_m,self.lateral_scale_m,self.rotation_scale_rad) <= 0 or not 0 < self.gamma <= 1:
            raise ValueError('Positive scales and valid gamma required')


def make_contract(metadata,refinement,spec=ContactPullRewardSpec()):
    parent=original_contract(metadata,refinement)
    return dict(schema='teacher60_pull_contact_reward_v1',parent=parent,
        parent_contract_sha256=contract_digest(parent),reward=asdict(spec),
        semantics='Reward only. Original 2s preload, 0.5s ramp, physical contact/grasp, detachment, retention and failure/timeout unchanged. Potential uses measured calyx displacement and qualified contact; no force threshold incentive.',
        files={name:sha(ROOT/name) for name in ['scripts/teacher60_pull_contact.py',
            'src/harvest_robot/harvest_rl/pull_contact_reward_60hz.py',
            'src/harvest_robot/harvest_rl/contact_points_60hz.py']})


class ContactPullReward:
    def __init__(self,n,device,spec=ContactPullRewardSpec()):
        self.spec=spec
        self.previous=torch.zeros(n,device=device)
        self.reference=torch.zeros(n,4,device=device);self.reference[:,0]=1
        self.initialized=torch.zeros(n,device=device,dtype=torch.bool)
        self.diagnostics={}

    def reset(self,ids):
        self.previous[ids]=0
        self.initialized[ids]=False

    def start(self,quat):
        mask=~self.initialized
        self.reference[mask]=quat[mask]
        self.initialized[mask]=True

    def step(self,*,displacement,axis,quat,qualified,confirmed,attached,distance,slip,
             center_tolerance,max_slip,elapsed,terminal,timeout,dt):
        s=self.spec
        axis=torch.as_tensor(axis,device=displacement.device,dtype=displacement.dtype)
        axis=axis/axis.norm().clamp_min(1e-12)
        axial=(displacement*axis).sum(-1)
        lateral=(displacement-axial[:,None]*axis).norm(dim=-1)
        normalized=quat/quat.norm(dim=-1,keepdim=True).clamp_min(1e-12)
        reference=self.reference/self.reference.norm(dim=-1,keepdim=True).clamp_min(1e-12)
        dot=(normalized*reference).sum(-1).abs().clamp(0.,1.)
        rotation=2*torch.acos(dot)
        # Grasp is graded inside the real thresholds, never granted by this reward.
        quality=qualified.float()*(1-.5*(distance/center_tolerance).clamp(0,1))*(1-.5*(slip/max_slip).clamp(0,1))
        active=confirmed & attached & (elapsed >= 2.-1e-7)
        potential=(s.progress_weight*(axial/s.axial_target_m).clamp(0,1)+s.contact_weight)*quality*active
        potential=torch.where(terminal,torch.zeros_like(potential),potential)
        shaping=s.gamma*potential-self.previous
        self.previous=potential.detach().clone()
        lateral_cost=s.lateral_weight*dt*(lateral/s.lateral_scale_m).square().clamp_max(4)*active
        rotation_cost=s.rotation_weight*dt*(rotation/s.rotation_scale_rad).square().clamp_max(4)*active
        timeout_cost=s.timeout_cost*timeout
        self.diagnostics=dict(contact_pull_active=active, contact_pull_quality=quality,
            contact_pull_axial_m=axial,contact_pull_lateral_m=lateral,
            contact_pull_rotation_rad=rotation,contact_pull_potential=potential,
            contact_pull_shaping=shaping,contact_pull_lateral_cost=lateral_cost,
            contact_pull_rotation_cost=rotation_cost,contact_pull_timeout_cost=timeout_cost)
        return shaping-lateral_cost-rotation_cost-timeout_cost
