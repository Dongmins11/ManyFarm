"""Audit first assigned episodes and the no-reset retained-pull transport switch."""
import json
import math
from collections import Counter
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src/harvest_robot'))
from harvest_rl.teacher_asset_reference import sha
from harvest_rl.grasp_handoff_60hz import contract_digest


def analyze(path):
    path=Path(path)
    run=json.loads((path/'run.json').read_text())
    contract=json.loads((path/'bridge_pull_contract.json').read_text())
    evaluation=json.loads((path/'evaluation.json').read_text())
    if (not run.get('completed') or run['learning'] or run['hardware_executed']
            or not run['source_still_matches'] or not run['normalizers_unchanged']
            or not run['grasp_actor_unchanged'] or run['contract_sha256']!=contract_digest(contract)
            or abs(run['actual_physics_dt_s']-1/60)>1e-12 or abs(run['actual_policy_dt_s']-.05)>1e-12):
        raise ValueError('Incomplete or mutated inference-only connection')
    for f,h in contract['files'].items():
        if sha(ROOT/f)!=h or sha(path/'source_snapshot'/f)!=h:
            raise ValueError('Source mismatch: '+f)
    n=evaluation['count'];rows={i:[] for i in range(n)}
    for line in (path/'trace.jsonl').open():
        d=json.loads(line)
        for i,v in zip(d['env_ids'],d['rows']):
            rows[i].append(dict(time_s=d['time_s'],**dict(zip(d['columns'],v))))
    episodes=evaluation['episodes']
    if [e['trial_id'] for e in episodes]!=list(range(n)):
        raise ValueError('Missing initial assigned episodes')
    metrics=[]
    for e in episodes:
        r=rows[e['trial_id']]
        if not r or any(not all(math.isfinite(v) for v in x.values()) for x in r):
            raise ValueError('Missing/nonfinite trace')
        handoffs=[j for j,x in enumerate(r) if x['transport_handoff']]
        if len(handoffs)>1:raise ValueError('Repeated transport switch')
        h=handoffs[0] if handoffs else None
        if h is not None:
            if r[h]['transport_action_active']:raise ValueError('Transport acted on switch tick')
            if h<9:raise ValueError('Missing retention history')
            for x in r[h-9:h+1]:
                if (x['attached'] or not x['valid_detach'] or not x['qualified_grasp']
                        or min(x['fixed_force_N'],x['moving_force_N'])<.08-1e-6
                        or x['distance_m']>.01+1e-6 or x['slip_m']>=.012 or x['failure']):
                    raise ValueError('Transport started without actual0.5s retained grasp')
            for x in r[h+1:]:
                if (not x['transport_action_active'] or x['retention_target_hold']
                        or x['path_hold'] or abs(x['close_action'])>1e-7
                        or abs(x['gripper_target_rad']-r[h]['gripper_target_rad'])>1e-6
                        or abs(x['jaw_origin_rad']-r[h]['jaw_origin_rad'])>1e-6):
                    raise ValueError('Transport guard leak or duplicate jaw control')
            if h+1<len(r) and abs(r[h+1]['transport_elapsed_s']-.05)>1e-5:
                raise ValueError('Transport clock did not start on handoff')
        if any(x['jaw_total_close_deg']>4.0001 or x['detached_stem_force_N']>1e-6
               or x['detached_stem_torque_Nm']>1e-6 for x in r):
            raise ValueError('Jaw budget or detached wrench changed')
        if e['success']:
            if h is None or r[-1]['release_stop_s']<.3-1e-6:
                raise ValueError('Success lacks transport stop')
            for x in r[-6:]:
                if not x['stop_all_ok'] or x['failure']:raise ValueError('Invalid0.3s stop')
        after=r[h+1:] if h is not None else []
        loss=next((x for x in after if not x['qualified_grasp']),None)
        motion=max((sum(x[f'arm_command_{j}']**2 for j in range(5))**.5 for x in after),default=0.)
        final=r[-1]
        kind=('transport_stop_success' if e['success'] else
              'pull_or_approach_failure' if h is None else
              'transport_timeout_contact_loss' if e['timeout'] and loss else
              'transport_timeout' if e['timeout'] else 'transport_physical_failure')
        metrics.append(dict(trial_id=e['trial_id'],classification=kind,success=e['success'],
            retained_handoff=h is not None,sample=e['sample'],reasons=e['reasons'],
            handoff_s=r[h]['time_s'] if h is not None else None,
            transport_duration_s=final['transport_elapsed_s'] if h is not None else None,
            first_qualification_loss_s=loss['transport_elapsed_s'] if loss else None,
            first_loss=dict(fixed_N=loss['fixed_force_N'],moving_N=loss['moving_force_N'],
                center_mm=loss['distance_m']*1000,slip_mm=loss['slip_m']*1000) if loss else None,
            final_placement_distance_m=final['placement_distance_m'],
            final_stop_zone=bool(final['stop_zone_ok']),max_arm_command_norm=motion,
            peak_arm_force_N=max(x['arm_max_force_N'] for x in r)))
    success=sum(x['success'] for x in metrics);handoff=sum(x['retained_handoff'] for x in metrics)
    if success!=evaluation['success']:raise ValueError('Episode count mismatch')
    return dict(schema='teacher60_bridge_transport_audit_v1',count=n,success=success,
        retained_handoffs=handoff,transport_conditional_success=success/max(handoff,1),
        split=run['split'],learning=False,hardware_executed=False,
        transport_is_legacy_transfer=True,full_box_deposit_tested=False,
        retention_and_stop_audited=True,duplicate_preload=False,guard_leak=False,
        classification_counts=dict(Counter(x['classification'] for x in metrics)),metrics=metrics)


if __name__=='__main__':
    if len(sys.argv)!=2:raise SystemExit('Usage: analyze_teacher60_bridge_transport.py OUTPUT')
    p=Path(sys.argv[1]);r=analyze(p)
    (p/'analysis.json').write_text(json.dumps(r,indent=2)+'\n')
    print(json.dumps({k:v for k,v in r.items() if k!='metrics'},indent=2))
