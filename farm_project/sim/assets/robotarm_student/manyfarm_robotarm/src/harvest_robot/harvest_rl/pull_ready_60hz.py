"""Shared bounded gripping/settling and strict physical feasibility gate."""
import json
import math
from pathlib import Path

from .followup_60hz import make_contract as original_contract
from .grasp_handoff_60hz import contract_digest
from .teacher_asset_reference import sha

ROOT=Path(__file__).resolve().parents[3]
PRELOAD_DEG=4.
PRELOAD_RATE_DEG_S=2.
SETTLE_S=2.
FILES=['scripts/teacher_60hz_pull_ready.py',
       'src/harvest_robot/harvest_rl/pull_ready_60hz.py',
       'src/harvest_robot/harvest_rl/pull_ready_probe.py',
       'src/harvest_robot/harvest_rl/pull_speed_probe.py',
       'src/harvest_robot/harvest_rl/pull_speed_comparison.py',
       'src/harvest_robot/harvest_rl/kinematics.py']


def prepare_actions(actions,elapsed,confirmed,release_intent):
    """Pull owns the arm; certified grip is maintained by its bounded controller.

    This masks policy proposals only. No joint/body state, contact flag or force
    is written. Explicit release intent retains opening priority. The policy's
    sixth action stays in the common interface but is not a pull control DOF.
    """
    result=actions.clone()
    scope=confirmed & ~release_intent
    result[scope & (elapsed < SETTLE_S-1e-7),:5]=0.
    result[scope,5]=0.
    return result


def make_contract(metadata,*args,**kwargs):
    base=original_contract(metadata,'bounded-preload','stored',
        preload_budget=math.radians(PRELOAD_DEG),preload_rate=math.radians(PRELOAD_RATE_DEG_S))
    return dict(base,schema='teacher60_pull_ready_v1',
        pull_controller=dict(arm_settle_s=SETTLE_S,policy_arm_dofs=5,
            jaw='neutral after certified grasp; finite preload/hold; release intent has priority',
            preload_deg=PRELOAD_DEG,preload_rate_deg_s=PRELOAD_RATE_DEG_S),
        files={**base['files'],**{p:sha(ROOT/p) for p in FILES}})


def check_probe_reports(paths,metadata,minimum_count=32,**kwargs):
    expected=contract_digest(make_contract(metadata))
    bank=assignment=indices=initial=None
    accepted={}
    for mode,path,minimum in [('hold',paths[0],.9),('pull-probe',paths[1],.8)]:
        path=Path(path);report=json.loads(path.read_text())
        contract_path=path.parent/'followup_contract.json'
        run=json.loads((path.parent/'run.json').read_text())
        actual=json.loads(contract_path.read_text())
        checks=dict(mode=mode,learning=False,physics_hz=60,policy_hz=20,split='validation',
            source_grasp_sha256=metadata['source_checkpoint_sha256'],
            source_grasp_contract_sha256=metadata['source_contract_sha256'],
            domain_stage=metadata['domain_stage'],physical_signature=metadata['physical_signature'],
            followup_contract_sha256=expected,training_gate_eligible=True,comparison_only=False)
        if (any(report.get(k)!=v for k,v in checks.items()) or actual!=make_contract(metadata)
                or run.get('followup_contract_sha256')!=expected or run.get('learning') is not False
                or run.get('source_and_assets_still_match') is not True
                or abs(run.get('actual_physics_dt_s',0)-1/60)>1e-12
                or abs(run.get('actual_policy_dt_s',0)-.05)>1e-12):
            raise ValueError(f'{mode} report/source/clock/controller mismatch; rerun this ready runtime')
        if any(sha(ROOT/p)!=h for p,h in actual['files'].items()):
            raise ValueError('Ready runtime changed after the physical probe')
        current_bank=report.get('probe_bank_sha256');current_assignment=report.get('bank_assignment_sha256')
        if not current_bank or not current_assignment or (bank and bank!=current_bank) or (assignment and assignment!=current_assignment):
            raise ValueError('Hold/pull must share the complete paired validation bank assignment')
        bank,assignment=current_bank,current_assignment
        source_bank=Path(run['start_bank'])
        if sha(source_bank)!=current_bank or run.get('start_bank_sha256')!=current_bank:
            raise ValueError('Validation bank changed after probe')
        if report.get('duration_s',0)<(SETTLE_S if mode=='hold' else 8.):
            raise ValueError('Physical probe duration is too short')
        rows=report.get('episodes',[])
        if (len(rows)<minimum_count or [r.get('env_id') for r in rows]!=list(range(len(rows)))
                or any(type(r.get('passed')) is not bool for r in rows)
                or sum(r['passed'] for r in rows)/len(rows)<minimum):
            raise ValueError(f'{mode} physical feasibility gate failed; training not started')
        current_indices=[r['bank_state_index'] for r in rows]
        current_initial=json.loads((path.parent/'initial_state.json').read_text())
        if current_initial['bank_state_indices']!=current_indices or (indices is not None and indices!=current_indices):
            raise ValueError('Paired bank state indices differ')
        from .pull_speed_comparison import same_initial_states
        if initial is not None:same_initial_states(initial,current_initial)
        indices,initial=current_indices,current_initial
        for row in rows:
            if row['passed'] and (row['failure'] or row.get('timed_out') or row.get('guard_halted')
                or (mode=='hold' and (not row['attached'] or row['first_unstable_s'] is not None))
                or (mode=='pull-probe' and (row['attached'] or not row['valid_detach'] or not row['retained']))):
                raise ValueError('Inconsistent physical success evidence')
        accepted[mode+'_report_sha256']=sha(path)
    accepted.update(validation_bank_sha256=bank,bank_assignment_sha256=assignment)
    return accepted
