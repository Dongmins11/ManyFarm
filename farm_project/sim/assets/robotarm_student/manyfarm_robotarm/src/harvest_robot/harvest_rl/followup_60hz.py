"""CPU-verifiable provenance and routing for user-run 60Hz follow-up tasks."""
import copy
import json
import math
from pathlib import Path
from .grasp_handoff_60hz import physical_signature, contract_digest
from .teacher_asset_reference import sha, verify_teacher_assets

ROOT=Path(__file__).resolve().parents[3]
FILES=['scripts/teacher_60hz_followup.py',
       'src/harvest_robot/harvest_rl/followup_60hz.py',
       'src/harvest_robot/harvest_rl/grasp_handoff_60hz.py',
       'src/harvest_robot/harvest_rl/bounded_grip_60hz.py',
       'src/harvest_robot/harvest_rl/followup_60hz_probe.py']


def verify_source(metadata):
    r,c=metadata['source_run'],metadata['source_contract']
    if c['domain']['name']!='teacher_60hz_capture_v4':
        raise ValueError('Follow-up requires a new V4 grasp bank')
    if contract_digest(c)!=metadata['source_contract_sha256']:
        raise ValueError('Grasp source contract changed')
    wrong=[p for p,h in c['domain_files'].items() if sha(ROOT/p)!=h]
    if wrong:raise ValueError(f'Grasp source changed: {wrong}')
    if sha(metadata['source_checkpoint'])!=metadata['source_checkpoint_sha256']:
        raise ValueError('Source grasp checkpoint changed')
    verify_teacher_assets(r['reference'],r['cached_asset_reference'],r['source_run'])


def restore_grasp_handoff(bank, env, ids, *, assignments=None, arm_target='stored'):
    """Restore before the first contact update without inventing measured grip.

    The frozen base creates raw_grip lazily in its state update. Isaac's
    vector wrapper resets before that update, so the handoff reset needs empty
    contact buffers first. Existing buffers (including other envs) are kept;
    the bank invalidates only the restored ids and physics rechecks contact.
    """
    import torch
    for name in ('raw_grip', 'grip'):
        if not hasattr(env, name):
            setattr(env, name, torch.zeros(env.num_envs, device=env.device, dtype=torch.bool))
    if arm_target not in ('stored','measured'):
        raise ValueError('Unknown handoff arm target')
    if assignments is None:
        bank.restore(env, ids)
    else:
        # Reuse the frozen restoration, with a one-state view for each assigned
        # group. No random-function patch, filtered bank or contact fabrication.
        from types import SimpleNamespace
        chosen=assignments[ids]
        if assignments.shape!=(env.num_envs,) or ((chosen<0)|(chosen>=bank.count)).any():
            raise ValueError('Invalid paired handoff assignment')
        for index in chosen.unique().tolist():
            selected=ids[chosen==index]
            view=SimpleNamespace(metadata=bank.metadata,count=1,
                states={k:v[index:index+1] for k,v in bank.states.items()})
            type(bank).restore(view,env,selected)
            env.handoff_indices[selected]=index
    if arm_target=='measured':
        # Change only the position command, never the restored q/qd or bodies.
        measured=env.robot.data.joint_pos[ids][:,env.jids]
        env.targets[ids,:5]=measured[:,:5]
        env.robot.set_joint_position_target(env.targets[ids],joint_ids=env.jids,env_ids=ids)


def maintain_jaw_target(previous, proposed, measured, action, eligible, *,
                        mode, speed, dt, max_error, lower, upper):
    """Zero command holds a position; closing requires an explicit command.

    The baseline measured-minus-error servo may keep walking the target inward.
    Its per-tick error bound is not a bound on accumulated closure. Preserve
    explicit opening (including the base's release unloading), and bound an
    explicit closing command with the existing speed/error/position limits.
    """
    import torch
    if mode=='legacy':return proposed,torch.zeros_like(eligible)
    if mode!='fixed-target':raise ValueError('Unknown gripper maintenance mode')
    command=action.clamp(-1.,1.)
    close=torch.maximum(previous+command*speed*dt,measured-max_error).clamp(lower,upper)
    desired=torch.where(command==0,previous.clamp(lower,upper),close)
    result=torch.where(eligible & (command<=0),desired,proposed)
    return result,eligible & (command==0)


def pull_settings(metadata, split, seed):
    from .settings import TaskSettings
    cfg=TaskSettings(**copy.deepcopy(metadata['source_run']['task']))
    cfg.task='pull';cfg.reward_version=6;cfg.seed=seed
    cfg.workspace_split='train' if split=='train' else 'eval'
    cfg.pull_direction_shaping=True;cfg.pull_recovery_shaping=True
    # Restore attached measured states through the dedicated format, not the
    # detached legacy start_bank route. Physical settings remain exactly equal.
    cfg.start_bank=''
    if physical_signature(cfg.as_dict())!=metadata['physical_signature']:
        raise ValueError('Pull settings unexpectedly changed physical parameters')
    return cfg


def make_contract(metadata, maintenance='fixed-target', handoff_arm='stored', *,
                  preload_budget=math.radians(1.), preload_rate=math.radians(10.)):
    if maintenance not in ('legacy','fixed-target','bounded-preload') or handoff_arm not in ('stored','measured'):
        raise ValueError('Unknown follow-up maintenance contract')
    if not all(math.isfinite(x) and x>0 for x in (preload_budget,preload_rate)):
        raise ValueError('Preload budget/rate must be finite and positive')
    return dict(schema='teacher60_pull_from_v4_grasp_v2',
        source_grasp_sha256=metadata['source_checkpoint_sha256'],
        source_grasp_contract_sha256=metadata['source_contract_sha256'],
        physical_signature=metadata['physical_signature'],
        task='pull',reward_version=6,normalization_contract='teacher82_grasp_progress_identity_v1',
        pull_direction_shaping=True,pull_recovery_shaping=True,
        maintenance=dict(gripper=maintenance,handoff_arm=handoff_arm,
            zero_action={'fixed-target':'hold established target',
                'bounded-preload':'rate-limited finite preload from latched target',
                'legacy':'legacy measured-minus-error squeeze'}[maintenance],
            **(dict(preload_budget_rad=preload_budget,preload_rate_rad_s=preload_rate,
                opening_priority=True) if maintenance=='bounded-preload' else {})),
        files={p:sha(ROOT/p) for p in FILES})


def check_probe_reports(paths, metadata, minimum_count=32, *, maintenance='fixed-target', handoff_arm='stored',
                        preload_budget=math.radians(1.),preload_rate=math.radians(10.)):
    validation_bank=None
    expected=contract_digest(make_contract(metadata,maintenance,handoff_arm,
        preload_budget=preload_budget,preload_rate=preload_rate))
    for mode,path,minimum in [('hold',paths[0],.9),('pull-probe',paths[1],.8)]:
        r=json.loads(Path(path).read_text())
        if (r.get('mode')!=mode or r.get('learning') is not False
                or r.get('physics_hz')!=60 or r.get('policy_hz')!=20
                or r.get('split')!='validation'
                or r.get('source_grasp_sha256')!=metadata['source_checkpoint_sha256']
                or r.get('source_grasp_contract_sha256')!=metadata['source_contract_sha256']
                or r.get('domain_stage')!=metadata['domain_stage']
                or r.get('physical_signature')!=metadata['physical_signature']
                or r.get('followup_contract_sha256')!=expected):
            raise ValueError(f'Wrong {mode} report/source/clock/split/maintenance; rerun probes with the current control contract')
        bank=r.get('probe_bank_sha256')
        if not bank or (validation_bank is not None and validation_bank!=bank):
            raise ValueError('Both probes must use the same held-out validation bank')
        validation_bank=bank
        if r.get('duration_s',0)<(1. if mode=='hold' else 8.):
            raise ValueError(f'{mode} duration is too short for the feasibility gate')
        rows=r.get('episodes',[])
        if (len(rows)<minimum_count or any(type(x.get('passed')) is not bool for x in rows)
                or sum(x['passed'] for x in rows)/len(rows)<minimum):
            raise ValueError(f'{mode} feasibility gate failed; inspect contact/force traces before training')
    return {'hold_report_sha256':sha(paths[0]),'pull_report_sha256':sha(paths[1])}


def route_phase(phase, grasped, contact, attached, detached, retained, stopped):
    import torch
    # Full harvest may already have accepted a physically captured break during
    # the original grace check. Do not strand that valid grasp in entry routing.
    result=torch.where((phase==0)&grasped&contact&(attached|detached),1,phase)
    result=torch.where((phase==1)&detached&retained&contact,2,result)
    return torch.where((phase==2)&detached&retained&contact&stopped,3,result)


def chain_tail_actions(actions, phase, phase_steps, dt, release_mode):
    """Preserve the prior transport ramp and explicitly selected release mode."""
    result=actions.clone()
    elapsed=(phase_steps-1).clamp_min(0)*dt
    scale=.25+.75*(elapsed/3.).clamp(0,1)
    transport=phase==2
    result[transport,:5]=result[transport,:5].clamp(-1,1)*scale[transport,None]
    if release_mode=='fixed':
        result[phase==3,:5]=0.
        result[phase==3,5]=.15
    elif release_mode!='policy':raise ValueError('Unknown release mode')
    return result
