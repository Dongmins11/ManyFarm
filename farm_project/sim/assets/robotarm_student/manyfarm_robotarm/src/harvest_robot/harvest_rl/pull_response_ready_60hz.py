"""Separate fast-preload/contact-pull contract; original certifications stay frozen."""
from dataclasses import asdict
import json
from pathlib import Path
from .grasp_handoff_60hz import contract_digest
from .teacher_asset_reference import sha
from .pull_contact_reward_60hz import make_contract as reward_contract
from .handoff_grip_response_60hz import GripResponse

ROOT=Path(__file__).resolve().parents[3]
RESPONSE=GripResponse('fast',6.)
FILES=['scripts/teacher60_pull_response.py',
       'src/harvest_robot/harvest_rl/pull_response_ready_60hz.py',
       'src/harvest_robot/harvest_rl/handoff_grip_response_60hz.py',
       'src/harvest_robot/harvest_rl/pull_transfer_60hz.py']


def make_contract(metadata, refinement):
    if refinement.ramp_s != .5 or refinement.initial_scale != .2 or refinement.hold_after_detach:
        raise ValueError('Response runtime fixes the selected 0.5s/20 percent arm ramp')
    parent=reward_contract(metadata, refinement)
    return dict(schema='teacher60_fast_preload_contact_pull_v1',parent=parent,
        parent_contract_sha256=contract_digest(parent),response=asdict(RESPONSE),
        control=dict(total_preload_deg=4.,preload_rate_deg_s=6.,arm_settle_s=2.,
            release_priority=True,measured_angle_rebase=False,force_feedback=False),
        arm_commands=dict(scripted_probe='original joint-driven15mm/s Cartesian feasibility',
            learned_policy='selected0.5s/20-to100 percent bounded proposal ramp'),
        files={f:sha(ROOT/f) for f in FILES},
        meaning='Same physical source/criteria and contact-axis reward. Faster finite position preload, no simulated-force control or new policy inputs.')


def check_probe_reports(paths,metadata,refinement):
    expected=make_contract(metadata,refinement);digest=contract_digest(expected)
    bank=assignment=initial=None
    result={}
    for mode,path,minimum in [('hold',paths[0],.9),('pull-probe',paths[1],.8)]:
        path=Path(path);report=json.loads(path.read_text())
        run=json.loads((path.parent/'run.json').read_text())
        actual=json.loads((path.parent/'followup_contract.json').read_text())
        checks=dict(mode=mode,learning=False,physics_hz=60,policy_hz=20,split='validation',
            comparison_only=False,training_gate_eligible=True,followup_contract_sha256=digest,
            source_grasp_sha256=metadata['source_checkpoint_sha256'],
            source_grasp_contract_sha256=metadata['source_contract_sha256'],
            physical_signature=metadata['physical_signature'],domain_stage=metadata['domain_stage'])
        duration=2. if mode=='hold' else 9.25
        if (any(report.get(k)!=v for k,v in checks.items()) or actual!=expected
                or report.get('duration_s')!=duration or run.get('mode')!=mode
                or run.get('followup_contract_sha256')!=digest or run.get('learning') is not False
                or run.get('source_and_assets_still_match') is not True
                or abs(run.get('actual_physics_dt_s',0)-1/60)>1e-12
                or abs(run.get('actual_policy_dt_s',0)-.05)>1e-12):
            raise ValueError('New response hold/pull contract/source/clock evidence mismatch')
        # Verify the files used by the nested reward/control runtime too.
        for node in (actual,actual['parent'],actual['parent']['parent'],
                     actual['parent']['parent']['parent']):
            for f,h in node['files'].items():
                if sha(ROOT/f)!=h:raise ValueError('Response evidence runtime changed: '+f)
        b=report.get('probe_bank_sha256');s=report.get('bank_assignment_sha256')
        if not b or not s or (bank and b!=bank) or (assignment and s!=assignment):
            raise ValueError('Response hold/pull must use identical complete validation assignments')
        bank,assignment=b,s
        selection_path=Path(run['bank_indices_path'])
        bank_path=Path(run['start_bank'])
        if sha(bank_path)!=b or sha(selection_path)!=s:
            raise ValueError('Response probe bank/assignment changed')
        restored=json.loads((path.parent/'initial_state.json').read_text())
        if initial is not None and restored!=initial:
            raise ValueError('Actual restored response states differ between hold/pull')
        initial=restored
        episodes=report['episodes']
        if (len(episodes)<32 or len({e['env_id'] for e in episodes})!=len(episodes)
                or [e['env_id'] for e in episodes]!=list(range(len(episodes)))
                or any(type(e['passed']) is not bool for e in episodes)
                or [e['bank_state_index'] for e in episodes]!=restored['bank_state_indices']
                or restored['bank_state_indices']!=json.loads(selection_path.read_text())['indices']):
            raise ValueError('Complete matched 32-state response evidence required')
        for e in episodes:
            if not e['passed']:continue
            if (e['failure'] or e.get('timed_out') or e.get('guard_halted')
                    or (mode=='hold' and (not e['attached'] or e['first_unstable_s'] is not None))
                    or (mode=='pull-probe' and (e['attached'] or not e['valid_detach'] or not e['retained']))):
                raise ValueError('Probe claimed success without unchanged physical evidence')
        successes=sum(e['passed'] for e in episodes)
        if successes/len(episodes)<minimum:
            raise ValueError(f'Response {mode} gate not passed: {successes}/{len(episodes)}')
        result[mode]=dict(path=str(path.resolve()),sha256=sha(path),count=len(episodes),success=successes)
    return dict(reports=result,validation_bank_sha256=bank,assignment_sha256=assignment,
        meaning='New runtime static feasibility only; repeated validation, not full harvest or real-robot certification')
