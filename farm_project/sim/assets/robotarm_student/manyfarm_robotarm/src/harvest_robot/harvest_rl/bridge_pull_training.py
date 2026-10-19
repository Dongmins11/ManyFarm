"""Contracts and reward-only refinement for continuous, train-only bridge pull."""
import copy
import json
import math
from pathlib import Path
import torch
from .teacher_asset_reference import sha
from .grasp_handoff_60hz import contract_digest, physical_signature
from .followup_60hz import verify_source
from .bridge_pull_60hz import verify_checkpoint

ROOT=Path(__file__).resolve().parents[3]
FILES=['scripts/train_teacher60_bridge_pull.py',
       'scripts/analyze_teacher60_bridge_training.py',
       'src/harvest_robot/harvest_rl/bridge_pull_training.py',
       'src/harvest_robot/harvest_rl/teacher_bridge_pull_env.py',
       'src/harvest_robot/harvest_rl/bridge_pull_ppo.py']
SPEC=dict(version=1,bridge_s=2.,jaw_budget_deg=4.,jaw_rate_deg_s=6.,ramp_s=.5,
          initial_scale=.2,pull_budget_s=20.,retention_s=.5,early_window_s=1.,
          axial_target_m=.025,progress_weight=6.,contact_force_saturation_N=.15,
          contact_weight=1.,contact_loss_event_cost=2.,lateral_scale_m=.015,
          lateral_weight=.8,rotation_scale_rad=math.radians(20),rotation_weight=.3,
          collision_scale_N=2.,collision_weight=.25,gamma=.99,
          learning='Frozen HOME grasp actor; PPO arm5 samples only after actual2s bridge',
          normalizers='Preserve and freeze parent pull statistics; exclude HOME/bridge',
          terminal='Original physical failure, valid detachment and0.5s retention; finite20s pull budget includes bridge2s')


def source_metadata(grasp_checkpoint):
    checkpoint=Path(grasp_checkpoint).resolve()
    run=json.loads((checkpoint.parent/'run.json').read_text())
    contract=json.loads((checkpoint.parent/'domain_contract.json').read_text())
    saved=torch.load(checkpoint,map_location='cpu',weights_only=True)
    if (not contract.get('grasp_bridge') or saved['infos']['domain_contract_sha256']!=contract_digest(contract)
            or run['domain_contract_sha256']!=contract_digest(contract)):
        raise ValueError('Requires a verified grasp-bridge checkpoint, not a legacy grasp')
    m=dict(source_run=run,source_contract=contract,source_contract_sha256=contract_digest(contract),
           source_checkpoint=str(checkpoint),source_checkpoint_sha256=sha(checkpoint),
           physical_signature=physical_signature(run['task']),domain_stage=3,split='train')
    verify_source(m)
    return m,saved


def make_contract(metadata,pull_checkpoint):
    saved,model=verify_checkpoint(pull_checkpoint,metadata)
    return saved,dict(schema='teacher60_continuous_bridge_pull_training_v1',spec=SPEC,
        source_grasp_sha256=metadata['source_checkpoint_sha256'],
        source_grasp_contract_sha256=metadata['source_contract_sha256'],pull_transfer=model,
        physical_signature=metadata['physical_signature'],domain=metadata['source_run']['domain'],
        source_domain_files=metadata['source_contract']['domain_files'],
        files={name:sha(ROOT/name) for name in FILES},
        split='train',domain_stage=3,optimizer_transferred=False,grasp_actor_learns=False,
        bank_restore=False,old_probe_gate_reused=False,production_selection_changed=False)


def training_settings(metadata,seed):
    from .settings import TaskSettings
    cfg=TaskSettings(**copy.deepcopy(metadata['source_run']['task']))
    cfg.seed=seed;cfg.workspace_split='train';cfg.start_bank=''
    if physical_signature(cfg.as_dict())!=metadata['physical_signature']:
        raise ValueError('Continuous training changed frozen physical parameters')
    return cfg


def masked_returns(rewards,values,dones,active,last_values,last_active,gamma=.99,lam=.95):
    """GAE over real pull trajectories only; no bootstrap across HOME or terminals."""
    if rewards.shape!=values.shape or active.shape!=rewards.shape[:2]:
        raise ValueError('Expected [T,N,1] rewards/values and [T,N] phase mask')
    returns=torch.zeros_like(values);adv=torch.zeros_like(last_values)
    for t in reversed(range(len(rewards))):
        following=last_values if t==len(rewards)-1 else values[t+1]
        next_mask=last_active if t==len(rewards)-1 else active[t+1]
        keep=(active[t]&next_mask&~dones[t,:,0].bool())[:,None]
        delta=rewards[t]+gamma*following*keep-values[t]
        adv=torch.where(active[t,:,None],delta+gamma*lam*keep*adv,torch.zeros_like(adv))
        returns[t]=torch.where(active[t,:,None],adv+values[t],torch.zeros_like(adv))
    advantage=returns-values
    selected=advantage[active]
    if selected.numel():
        advantage=torch.where(active[:,:,None],(advantage-selected.mean())/(selected.std(unbiased=False)+1e-8),
                              torch.zeros_like(advantage))
    else:advantage.zero_()
    return returns,advantage


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
