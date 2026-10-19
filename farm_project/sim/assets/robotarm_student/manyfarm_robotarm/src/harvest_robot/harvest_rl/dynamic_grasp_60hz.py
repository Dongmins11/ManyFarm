"""New approach objective: original2s bridge, measured small retreat, actual hold."""
import copy
import json
from pathlib import Path
import torch

SPEC=dict(version=1,command_travel_m=.005,required_actual_axial_m=.004,
    max_actual_lateral_m=.002,command_speed_m_s=.005,hold_s=.5,motion_timeout_s=2.5,
    success_bonus=8.,progress_budget=2.,hold_reward_per_s=1.,
    scope='After original250ms grasp and2s bridge: command5mm horizontal retreat, prove4mm measured TCP movement and0.5s actual attached qualification. Approach actor learns; scripted bridge/probe controls after confirmation.',
    not_a_full_pull_test=True,no_harvest_gate_relaxation=True)
FILES=['scripts/train_teacher60_dynamic_grasp.py',
       'src/harvest_robot/harvest_rl/dynamic_grasp_60hz.py',
       'src/harvest_robot/harvest_rl/teacher_dynamic_grasp_env.py',
       'src/harvest_robot/harvest_rl/bridge_pull_path.py',
       'src/harvest_robot/harvest_rl/matched_pull_60hz.py',
       'src/harvest_robot/harvest_rl/placement_height_v2.py',
       'src/harvest_robot/config/teacher60_placement_height_v2.json']


def dynamic_step(started,moved,hold,*,bridge_passed,qualified,attached,failed,axial,lateral,elapsed,dt):
    if abs(dt-.05)>1e-9:raise ValueError('Dynamic grasp requires20Hz control')
    first=~started & bridge_passed & qualified & attached & ~failed
    lost=started & ~(qualified & attached)
    new_moved=(started & ~moved & qualified & attached & ~failed &
        (axial>=SPEC['required_actual_axial_m']) & (lateral<=SPEC['max_actual_lateral_m']))
    moved=moved | new_moved
    pose_valid=(axial>=SPEC['required_actual_axial_m']-1e-6) & (lateral<=SPEC['max_actual_lateral_m'])
    hold=torch.where(started & moved & ~new_moved & pose_valid & qualified & attached & ~failed,hold+dt,0.)
    unreachable=started & ~moved & (elapsed>=SPEC['motion_timeout_s'])
    success=started & moved & (hold>=SPEC['hold_s']-1e-6) & qualified & attached & ~failed & ~lost
    return started|first,moved,hold,success,lost|unreachable,first,new_moved


def verify_transfer(checkpoint,saved,new_contract,root):
    from .grasp_handoff_60hz import contract_digest
    from .teacher_asset_reference import sha
    old=json.loads((Path(checkpoint).parent/'domain_contract.json').read_text())
    if saved.get('infos',{}).get('domain_contract_sha256')!=contract_digest(old):
        raise ValueError('Bridge parent checkpoint contract differs')
    expected=copy.deepcopy(new_contract);expected.pop('dynamic_grasp');expected.pop('placement_height_v2')
    for f in FILES:
        if f not in old['domain_files']:expected['domain_files'].pop(f,None)
    old_task=old['task'];new_task=expected['task']
    if new_task['region_min'][2]+new_task['region_origin'][2]!=.8:
        raise ValueError('Dynamic grasp must use explicit new minimum height')
    new_task['region_min']=old_task['region_min']
    if expected!=old:raise ValueError('Unapproved physical/domain/source change from bridge parent')
    if any(sha(Path(root)/f)!=h for f,h in old['domain_files'].items()):
        raise ValueError('Frozen bridge source changed')
    return dict(source_checkpoint=str(Path(checkpoint).resolve()),source_checkpoint_sha256=sha(checkpoint),
        source_contract_sha256=contract_digest(old),optimizer_transferred=False,
        normalizer_buffers_transferred=True,new_dynamic_objective=True,new_raised_height_domain=True)
