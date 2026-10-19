"""Tensor-only contact geometry from actual loaded PhysX points, reward only."""
import torch

SPEC=dict(version=1,center_scale_m=.006,height_scale_m=.02,quality_bonus=4.,
    height_cost_per_s=.8,far_distance_m=.18,extra_far_pool_repeats=3,
    meaning='Real force-weighted contact positions, original physical success and commands; no motor torque measurement')


def contact_centroid(force,points,counts,starts,target,max_points=128):
    """Gather one target pair per env; ignore speculative points with zero force.

    Incomplete/saturated buffers are unavailable diagnostics, not contact loss.
    All arithmetic stays on the tensor device during PPO.
    """
    n=len(target);device=points.device
    count=counts[torch.arange(n,device=device),target.long()].long()
    start=starts[torch.arange(n,device=device),target.long()].long()
    capacity=len(points)
    all_counts=counts.long();all_starts=starts.long()
    bad_range=((all_counts<0)|((all_counts>0)&((all_starts<0)|(all_starts+all_counts>capacity)))).any()
    complete=(count<=max_points)&(count>=0)&~bad_range&(all_counts.sum()<capacity)
    offsets=torch.arange(max_points,device=device)[None,:]
    index=start[:,None]+offsets
    valid=(offsets<count[:,None])&(index>=0)&(index<capacity)&complete[:,None]
    index=index.clamp(0,capacity-1)
    weights=force.reshape(-1)[index].abs()*valid
    total=weights.sum(-1)
    centroid=(points[index]*weights[:,:,None]).sum(1)/total.clamp_min(1e-12)[:,None]
    available=complete & (total>1e-6)
    return centroid,total,available,complete


def contact_geometry(fixed,moving,fruit_position,fruit_quat):
    a,fa,aa,ca=fixed;b,fb,ab,cb=moving
    quat=fruit_quat/fruit_quat.norm(dim=-1,keepdim=True).clamp_min(1e-12)
    w,x,y,z=quat.unbind(-1)
    stem_axis=torch.stack([2*(x*z+w*y),2*(y*z-w*x),1-2*(x*x+y*y)],-1)
    height=((a-b)*stem_axis).sum(-1).abs()
    offset=((a+b)*.5-fruit_position).norm(dim=-1)
    return dict(loaded_height_difference_m=height,loaded_center_offset_m=offset,
        loaded_fixed_normal_N=fa,loaded_moving_normal_N=fb,
        loaded_points_available=aa & ab,loaded_points_complete=ca & cb)


def contact_margin_reward(geometry,distance,qualified,attached,success,dt):
    active=geometry['loaded_points_available'] & qualified & attached
    height=geometry['loaded_height_difference_m']
    center_quality=torch.exp(-(distance/SPEC['center_scale_m']).square())
    height_quality=torch.exp(-(height/SPEC['height_scale_m']).square())
    quality=center_quality*height_quality*active
    bonus=SPEC['quality_bonus']*quality*success
    cost=SPEC['height_cost_per_s']*dt*(height/SPEC['height_scale_m']).square().clamp_max(4)*active
    return bonus-cost,dict(contact_margin_quality=quality,contact_margin_bonus=bonus,
        contact_margin_height_cost=cost,**geometry)


def verify_parent_transfer(checkpoint,saved,new_contract,root):
    """Only unchanged V4 actor/normalizer/physics can warm start the new reward."""
    import copy,json
    from pathlib import Path
    from .grasp_handoff_60hz import contract_digest
    from .teacher_asset_reference import sha
    old=json.loads((Path(checkpoint).parent/'domain_contract.json').read_text())
    if saved.get('infos',{}).get('domain_contract_sha256')!=contract_digest(old):
        raise ValueError('Parent V4 checkpoint does not match its saved contract')
    expected=copy.deepcopy(new_contract)
    expected.pop('contact_margin_refinement',None)
    for name in ('scripts/train_teacher60_contact_grasp.py',
                 'src/harvest_robot/harvest_rl/grasp_contact_margin_60hz.py',
                 'src/harvest_robot/harvest_rl/teacher_contact_margin_env.py',
                 'src/harvest_robot/harvest_rl/contact_points_60hz.py'):
        expected['domain_files'].pop(name,None)
    if old!=expected or old['domain']['name']!='teacher_60hz_capture_v4':
        raise ValueError('Parent V4 physics, source, domain or observation differs')
    if any(sha(Path(root)/name)!=value for name,value in old['domain_files'].items()):
        raise ValueError('Parent V4 source changed')
    return dict(source_checkpoint=str(Path(checkpoint).resolve()),source_checkpoint_sha256=sha(checkpoint),
        source_contract_sha256=contract_digest(old),optimizer_transferred=False,
        normalizer_buffers_transferred=True,curriculum_history_transferred=False,
        contact_margin_reward_changed=True)
