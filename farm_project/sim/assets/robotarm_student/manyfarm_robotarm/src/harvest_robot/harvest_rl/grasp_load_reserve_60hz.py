"""Separate grasp reward: saturated force reserve and balanced loaded geometry."""
import copy
import json
from pathlib import Path
import torch

SPEC=dict(version=1,center_scale_m=.006,height_scale_m=.012,
    net_force_reserve_N=.15,balance_saturation=.7,quality_bonus=6.,
    height_cost_per_s=1.2,imbalance_cost_per_s=.4,weak_cost_per_s=.4,
    meaning='Reward-only; real bilateral net forces and loaded points; force bonus saturates; physical criteria/actuators unchanged. Dynamic robustness still requires new physical tests.')
FILES=['scripts/train_teacher60_load_reserve.py',
       'src/harvest_robot/harvest_rl/grasp_load_reserve_60hz.py',
       'src/harvest_robot/harvest_rl/teacher_load_reserve_env.py']


def load_reserve_reward(geometry,distance,fixed,moving,qualified,attached,success,dt):
    available=geometry['loaded_points_available'] & geometry['loaded_points_complete']
    active=available & qualified & attached
    height=geometry['loaded_height_difference_m']
    small=fixed.minimum(moving).clamp_min(0)
    large=fixed.maximum(moving).clamp_min(1e-9)
    margin=(small/SPEC['net_force_reserve_N']).clamp(0,1)
    balance=(small/large).clamp(0,1)
    balance_quality=(balance/SPEC['balance_saturation']).clamp(0,1)
    geometry_quality=torch.exp(-(distance/SPEC['center_scale_m']).square()-(height/SPEC['height_scale_m']).square())
    quality=torch.where(active,geometry_quality*margin*balance_quality,0.)
    bonus=SPEC['quality_bonus']*quality*success
    raw_cost=dt*(SPEC['height_cost_per_s']*(height/SPEC['height_scale_m']).square().clamp_max(4)
        +SPEC['imbalance_cost_per_s']*(1-balance_quality)+SPEC['weak_cost_per_s']*(1-margin))
    cost=torch.where(active,raw_cost,0.)
    return bonus-cost,dict(load_reserve_quality=quality,load_reserve_bonus=bonus,
        load_reserve_cost=cost,load_reserve_net_force_margin=margin,
        load_reserve_force_balance=balance,load_reserve_active=active)


def replace_contact_margin_reward(reward,diagnostics,distance,qualified,attached,success,dt):
    """Use the parent's recorded bonus/cost; its diagnostics already include those keys."""
    old=diagnostics['contact_margin_bonus']-diagnostics['contact_margin_height_cost']
    extra,diag=load_reserve_reward(diagnostics,distance,
        diagnostics['fixed_force_N'],diagnostics['moving_force_N'],qualified,attached,success,dt)
    return reward-old+extra,diag


def verify_parent_transfer(checkpoint,saved,new_contract,root):
    """Verified contact-margin parent weights only; never resume changed reward."""
    from .grasp_handoff_60hz import contract_digest
    from .teacher_asset_reference import sha
    old=json.loads((Path(checkpoint).parent/'domain_contract.json').read_text())
    if saved.get('infos',{}).get('domain_contract_sha256')!=contract_digest(old):
        raise ValueError('Parent contact grasp checkpoint/contract mismatch')
    expected=copy.deepcopy(new_contract);expected.pop('load_reserve_refinement',None)
    for f in FILES:expected['domain_files'].pop(f,None)
    if (old!=expected or old['domain']['name']!='teacher_60hz_capture_v4'
            or old.get('contact_margin_refinement',{}).get('version')!=1):
        raise ValueError('Parent physical/domain/source/contact-margin contract differs')
    if any(sha(Path(root)/f)!=h for f,h in old['domain_files'].items()):
        raise ValueError('Frozen contact grasp parent source changed')
    return dict(source_checkpoint=str(Path(checkpoint).resolve()),source_checkpoint_sha256=sha(checkpoint),
        source_contract_sha256=contract_digest(old),optimizer_transferred=False,
        normalizer_buffers_transferred=True,curriculum_history_transferred=False,load_reserve_reward_changed=True)
