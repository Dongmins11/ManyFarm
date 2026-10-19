"""Bounded inference comparisons; inherited harvest gates are never changed."""
from dataclasses import dataclass,asdict
import math
import torch


@dataclass(frozen=True)
class FollowupSpec:
    bridge_velocity_cap: float=1.5
    bridge_rate_deg_s: float=6.
    transport_mode: str='baseline'

    def validate(self):
        if self.bridge_velocity_cap not in (1.5,.3,.15):raise ValueError('Only original/0.3/0.15rad/s comparison')
        if self.bridge_rate_deg_s not in (6.,3.):raise ValueError('Only original6 or gentler3deg/s')
        if self.transport_mode not in ('baseline','early_position'):raise ValueError('Unknown transport comparison')
        return self


def early_escape(scope,clear,error,blocked,qualified):
    # Do not wait until every proposed joint command becomes zero. A single
    # active-set limit with >20mm remaining goal error is evidence of constraint.
    return scope & clear & qualified & (error>.02) & (blocked>=1)


def report(path):
    import json
    from pathlib import Path
    path=Path(path);run=json.loads((path/'run.json').read_text())
    result=json.loads((path/'evaluation.json').read_text())
    audit=json.loads((path/'jaw_surface_audit_end.json').read_text())
    if not run['completed'] or run['learning'] or run['hardware_executed'] or not run['normalizers_unchanged']:
        raise ValueError('Incomplete/inconsistent inference comparison')
    if not audit['all_clones_verified'] or audit['pad_shapes'] or not audit['camera_motor_materials_unchanged'] or not audit['full_mass_inertia_attributes_unchanged']:
        raise ValueError('Material/geometry/inertia audit missing')
    samples=json.loads((path/'initial_samples.json').read_text())
    success_ids=[r['trial_id'] for r in result['episodes'] if r['success']]
    stop_ids=[];retained_ids=[];metrics={};failures=[]
    max_commands=0.;max_predicted=0.;max_escape_angular=0.;cap_updates=0;escape_updates=0
    with (path/'trace.jsonl').open() as f:
        for line in f:
            frame=json.loads(line)
            for i,row in zip(frame['env_ids'],frame['rows']):
                v=dict(zip(frame['columns'],row));m=metrics.setdefault(i,dict(trial_id=i,bridge=False,retained=False,stop=False,
                    max_jaw_velocity_rad_s=0.,transport_max_goal_error_m=0.,escape_steps=0,
                    height_at_confirmation_mm=None,first_bridge_loss_s=None))
                if v['chain_bridge_confirmed']:m['bridge']=True
                if v.get('has_retained',v.get('transport_active',False)):m['retained']=True
                if v.get('deposit_handoff',False):m['stop']=True
                if v.get('followup_bridge_limited',False):
                    cap_updates+=1
                    m['max_jaw_velocity_rad_s']=max(m['max_jaw_velocity_rad_s'],abs(v['gripper_velocity_rad_s']))
                    if v['followup_actual_velocity_limit_rad_s']>run['followup']['bridge_velocity_cap']+1e-6:raise ValueError('Requested cap not applied')
                if m['height_at_confirmation_mm'] is None and v['chain_bridge_confirmed']:
                    m['height_at_confirmation_mm']=v['loaded_height_difference_m']*1000
                if v.get('chain_bridge_loss') and m['first_bridge_loss_s'] is None:m['first_bridge_loss_s']=frame['time_s']
                if v.get('followup_escape_active',False):
                    m['escape_steps']+=1;escape_updates+=1
                    max_escape_angular=max(max_escape_angular,v['followup_escape_predicted_angular_rad_s'])
                if v.get('transport_active',False) and not v.get('deposit_action_active',False):
                    m['transport_max_goal_error_m']=max(m['transport_max_goal_error_m'],v.get('transport_goal_error_m',0.))
                    max_commands=max(max_commands,max(abs(v.get(f'arm_command_{j}',0))*run['task']['action_speed'] for j in range(5)))
                    max_predicted=max(max_predicted,v.get('transport_path_predicted_speed_m_s',0.))
    for episode in result['episodes']:
        i=episode['trial_id'];m=metrics[i];t=episode['terminal']
        if m['retained']:retained_ids.append(i)
        if m['stop']:stop_ids.append(i)
        m.update(success=episode['success'],sample=samples[i],terminal=t)
        if episode['success']:
            # The unmodified class produced success. Check its actual evidence,
            # including recorded authorized stop, real mesh and both jaws clear.
            if not (m['stop'] and t['valid_detach'] and t['deposit_mesh_inside'] and t['deposit_both_jaws_clear']
                    and t['deposit_hold_s']>=run['task']['place_hold_s']-1e-5):raise ValueError('Physical deposit evidence missing')
        else:failures.append(dict(trial_id=i,sample=samples[i],reasons=episode['reasons'],
            bridge_loss_s=m['first_bridge_loss_s'],retained=m['retained'],stop=m['stop'],
            terminal_goal_error_m=t.get('transport_goal_error_m'),terminal=t))
    if max_commands>.30001 or max_predicted>.03501 or max_escape_angular>.08001:
        raise ValueError('Original command speed limits exceeded')
    summary=dict(schema='teacher60_friction_followup_audit_v1',followup=run['followup'],
        count=result['count'],success=result['success'],success_ids=success_ids,retained_ids=retained_ids,
        stop_ids=stop_ids,failures=failures,cap_updates=cap_updates,escape_updates=escape_updates,
        max_transport_joint_command_rad_s=max_commands,max_transport_predicted_speed_m_s=max_predicted,
        max_escape_predicted_angular_rad_s=max_escape_angular,learning=False,hardware_executed=False,
        production_selection_changed=False,classification_counts=dict(deposited=len(success_ids),failed=len(failures)),
        metrics=list(metrics.values()))
    return summary
