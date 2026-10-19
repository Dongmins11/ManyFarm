"""Audit continuous bridge/pull outcomes, loaded contacts and arm-link forces."""
import json
import math
from pathlib import Path
import sys
from collections import Counter

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src/harvest_robot'))
from harvest_rl.teacher_asset_reference import sha
from harvest_rl.grasp_handoff_60hz import contract_digest


def contact_summary(row):
    if not row['data_complete']:return dict(available=False,reason=row['unavailable_reason'])
    loaded=[(p,f) for p,f in zip(row['points_fruit_local_m'],row['normal_forces_N']) if f>1e-8]
    total=sum(f for _,f in loaded)
    return dict(available=bool(loaded),loaded_points=len(loaded),normal_force_N=total,
                centroid_fruit_m=[sum(p[j]*f for p,f in loaded)/total for j in range(3)] if loaded else None)


def analyze(path):
    path=Path(path);run=json.loads((path/'run.json').read_text())
    contract=json.loads((path/'bridge_pull_contract.json').read_text())
    evaluation=json.loads((path/'evaluation.json').read_text())
    if (not run.get('completed') or not run['source_still_matches'] or run['learning']
            or run['hardware_executed'] or not run['grasp_actor_unchanged'] or not run['normalizers_unchanged']
            or abs(run['actual_physics_dt_s']-1/60)>1e-12 or abs(run['actual_policy_dt_s']-.05)>1e-12
            or run['contract_sha256']!=contract_digest(contract)):
        raise ValueError('Incomplete or mutated continuous read-only run')
    for name,h in contract['files'].items():
        if sha(ROOT/name)!=h or sha(path/'source_snapshot'/name)!=h:raise ValueError('Runtime source changed')
    n=evaluation['count'];traces={i:[] for i in range(n)};contacts={i:[] for i in range(n)}
    for line in (path/'trace.jsonl').open():
        d=json.loads(line)
        for i,v in zip(d['env_ids'],d['rows']):traces[i].append(dict(time_s=d['time_s'],**dict(zip(d['columns'],v))))
    for line in (path/'contact_points.jsonl').open():
        d=json.loads(line)
        for j,i in enumerate(d['env_ids']):contacts[i].append(dict(time_s=d['time_s'],**{k:contact_summary(v[j]) for k,v in d['jaws'].items()}))
    episodes=evaluation['episodes']
    if [x['trial_id'] for x in episodes]!=list(range(n)) or sum(x['success'] for x in episodes)!=evaluation['success']:
        raise ValueError('Missing initial episodes')
    metrics=[]
    for episode in episodes:
        i=episode['trial_id'];rows=traces[i]
        if len(rows)!=len(contacts[i]):raise ValueError('Contact/trace frame mismatch')
        starts=[j for j,x in enumerate(rows) if x['chain_handoff']]
        confirmed=next((j for j,x in enumerate(rows) if x['chain_bridge_confirmed']),None)
        if len(starts)>1:raise ValueError('Multiple handoffs in a single assigned episode')
        h=starts[0] if starts else None
        if h is not None:
            if confirmed is None or h-confirmed<40:raise ValueError('Incomplete actual2s bridge')
            for x in rows[confirmed+1:h+1]:
                if (not x['attached'] or not x['qualified_grasp'] or not x['bilateral_contact']
                        or min(x['fixed_force_N'],x['moving_force_N'])<.08-1e-6
                        or x['distance_m']>.01+1e-6 or x['slip_m']>=.012 or x['failure']):
                    raise ValueError('Unqualified bridge sample')
            origin=rows[h]['jaw_origin_rad']
            if any(abs(x['jaw_origin_rad']-origin)>1e-6 or x['jaw_total_close_deg']>4.+1e-4 for x in rows[h:]):
                raise ValueError('Duplicate jaw budget/origin')
            if h+1<len(rows) and (abs(rows[h+1]['phase_elapsed_s']-2.05)>1e-5
                                  or abs(rows[h+1]['arm_ramp_scale']-.2)>1e-5):
                raise ValueError('Repeated settling after handoff')
        if episode['success']:
            if h is None or rows[-1]['detached_hold_s']<.5-1e-6:raise ValueError('Success missing retention')
            for x in rows[-10:]:
                if (x['attached'] or not x['valid_detach'] or not x['qualified_grasp'] or not x['bilateral_contact']
                        or min(x['fixed_force_N'],x['moving_force_N'])<.08-1e-6 or x['distance_m']>.01+1e-6
                        or x['slip_m']>=.012 or x['failure']):raise ValueError('Invalid actual0.5s retention')
        if any(x['detached_stem_force_N']>1e-6 or x['detached_stem_torque_Nm']>1e-6 for x in rows):
            raise ValueError('Detached stem wrench is nonzero')
        loss=next((j for j in range(h+1,len(rows)) if not rows[j]['qualified_grasp']),None) if h is not None else None
        peak=max(rows,key=lambda x:x['arm_max_force_N'])
        body=max(range(len(run['arm_contact_body_names'])),key=lambda j:peak[f'arm_body_{j}_force_N'])
        if episode['success']:kind='success'
        elif h is None:kind='pre-handoff failure'
        elif episode['timeout']:kind='pull timeout after contact loss' if loss is not None else 'pull timeout'
        else:kind='pull physical failure'
        def snapshot(j):
            x=rows[j]
            return dict(time_s=x['time_s'],distance_mm=x['distance_m']*1000,
                slip_mm=x['slip_m']*1000,fixed_N=x['fixed_force_N'],moving_N=x['moving_force_N'],
                loaded_height_difference_mm=x['loaded_height_difference_m']*1000,
                axial_mm=x['bridge_pull_axial_m']*1000,lateral_mm=x['bridge_pull_lateral_m']*1000,
                fruit_rotation_deg=x['bridge_pull_rotation_rad']*180/math.pi,
                contacts=contacts[i][j])
        metrics.append(dict(trial_id=i,success=episode['success'],confirmed=confirmed is not None,
            handoff=h is not None,classification=kind,reasons=episode['reasons'],sample=episode['sample'],
            handoff_snapshot=snapshot(h) if h is not None else None,
            first_contact_loss_snapshot=snapshot(loss) if loss is not None else None,
            first_contact_loss_after_handoff_s=rows[loss]['time_s']-rows[h]['time_s'] if loss is not None else None,
            peak_arm_force_N=peak['arm_max_force_N'],peak_arm_force_time_s=peak['time_s'],
            peak_arm_link=run['arm_contact_body_names'][body],
            collision_partner='Unknown: aggregate net-force sensor does not identify partner'))
    return dict(schema='continuous_bridge_pull_diagnostic_v1',completed=True,learning=False,
        count=n,success=evaluation['success'],handoffs=sum(x['handoff'] for x in metrics),
        confirmed=sum(x['confirmed'] for x in metrics),split=run['split'],
        classification_counts=dict(Counter(x['classification'] for x in metrics)),
        bridge_and_retention_verified=True,duplicate_settle_or_preload=False,metrics=metrics)


if __name__=='__main__':
    if len(sys.argv)!=2:raise SystemExit('Usage: analyze_teacher60_bridge_training.py OUTPUT')
    p=Path(sys.argv[1]);result=analyze(p)
    (p/'analysis.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k!='metrics'},indent=2))
