"""60Hz r2 원본 계산에서 추출. 재생성: sim/tools/import_teacher60.py."""

import math

import torch

SPEC=dict(version=1,bridge_s=2.,jaw_budget_deg=4.,jaw_rate_deg_s=6.,ramp_s=.5,
          initial_scale=.2,pull_budget_s=20.,retention_s=.5,early_window_s=1.,
          axial_target_m=.025,progress_weight=6.,contact_force_saturation_N=.15,
          contact_weight=1.,contact_loss_event_cost=2.,lateral_scale_m=.015,
          lateral_weight=.8,rotation_scale_rad=math.radians(20),rotation_weight=.3,
          collision_scale_N=2.,collision_weight=.25,gamma=.99,
          learning='Frozen HOME grasp actor; PPO arm5 samples only after actual2s bridge',
          normalizers='Preserve and freeze parent pull statistics; exclude HOME/bridge',
          terminal='Original physical failure, valid detachment and0.5s retention; finite20s pull budget includes bridge2s')

class BridgePullReward:
    """Bounded force quality and physical calyx-axis potential; no control writes."""
    def __init__(self,n,device):
        self.previous=torch.zeros(n,device=device)
        self.quat=torch.zeros(n,4,device=device);self.quat[:,0]=1.
        self.was_qualified=torch.zeros(n,device=device,dtype=torch.bool)

    def reset(self,ids):
        self.previous[ids]=0;self.was_qualified[ids]=False

    def handoff(self,mask,quat):
        self.quat[mask]=quat[mask];self.previous[mask]=0.;self.was_qualified[mask]=True

    def step(self,*,active,attached,qualified,force_fixed,force_moving,displacement,axis,quat,
             elapsed,arm_force,terminal,dt):
        s=SPEC;axis=torch.as_tensor(axis,device=displacement.device,dtype=displacement.dtype)
        axis=axis/axis.norm().clamp_min(1e-12)
        axial=(displacement*axis).sum(-1)
        lateral=(displacement-axial[:,None]*axis).norm(dim=-1)
        q=quat/quat.norm(dim=-1,keepdim=True).clamp_min(1e-12)
        reference=self.quat/self.quat.norm(dim=-1,keepdim=True).clamp_min(1e-12)
        rotation=2*torch.acos((q*reference).sum(-1).abs().clamp(0,1))
        scope=active & attached
        quality=qualified.float()*(torch.minimum(force_fixed,force_moving)/s['contact_force_saturation_N']).clamp(0,1)
        potential=s['progress_weight']*(axial/s['axial_target_m']).clamp(0,1)*quality*scope
        potential=torch.where(terminal,torch.zeros_like(potential),potential)
        shaping=s['gamma']*potential-self.previous
        self.previous=torch.where(active,potential.detach(),self.previous)
        early=scope & (elapsed<2.+s['early_window_s'])
        lost=active & self.was_qualified & ~qualified
        self.was_qualified=torch.where(active,qualified,self.was_qualified)
        contact=s['contact_weight']*dt*quality*early
        loss=s['contact_loss_event_cost']*lost
        lateral_cost=s['lateral_weight']*dt*(lateral/s['lateral_scale_m']).square().clamp_max(4)*scope
        rotation_cost=s['rotation_weight']*dt*(rotation/s['rotation_scale_rad']).square().clamp_max(4)*scope
        collision=s['collision_weight']*dt*(arm_force/s['collision_scale_N']).square().clamp_max(9)*active
        reward=(shaping+contact-loss-lateral_cost-rotation_cost-collision)*active
        diag=dict(axial_m=axial,lateral_m=lateral,rotation_rad=rotation,quality=quality,
                  potential=potential,shaping=shaping,contact_bonus=contact,
                  contact_loss_cost=loss,lateral_cost=lateral_cost,rotation_cost=rotation_cost,
                  collision_cost=collision)
        if not torch.isfinite(reward).all():raise FloatingPointError('Nonfinite bridge pull reward')
        return reward,diag
