"""Audit surface-only actual full-harvest comparisons on matched32 scenes."""
import json
from pathlib import Path
from collections import Counter
from analyze_teacher60_native_contact_control_chain import analyze as original_audit
from analyze_teacher60_transport_servo import trace_rows


def analyze(path):
    path=Path(path);report=original_audit(path)
    run=json.loads((path/'run.json').read_text())
    contract=json.loads((path/'bridge_pull_contract.json').read_text())
    override=json.loads((path/'jaw_surface_override.json').read_text())
    spec=run['jaw_surface_comparison']
    if spec!=contract['jaw_surface_comparison'] or spec!=override['spec']:
        raise ValueError('Surface provenance differs')
    if override['original_assets_modified'] or override['added_rigid_bodies'] or override['silicone_compliance_modelled']:
        raise ValueError('Unauthorized body/source/compliance change')
    for name in ['jaw_surface_audit.json','jaw_surface_audit_end.json']:
        a=json.loads((path/name).read_text())
        if not all(a[k] for k in ['all_clones_verified','jaw_material_verified','fruit_material_unchanged','mass_inertia_attributes_unchanged']):
            raise ValueError('Actual surface clone/material audit failed')
        if a['pad_shapes']!=(0 if spec['pad_mode']=='none' else 128):raise ValueError('Wrong cloned pad count')
    episodes=json.loads((path/'evaluation.json').read_text())['episodes'];rows=trace_rows(path)
    metrics=[]
    for e in episodes:
        rr=rows[e['trial_id']]
        def first(key):return next(((j+1)*.05 for j,x in enumerate(rr) if x.get(key)),None)
        h=first('chain_handoff');r=first('transport_handoff');p=first('deposit_handoff')
        phase=('deposited' if e['success'] else
            'release_or_deposit_failure' if p is not None else
            'transport_or_stop_failure' if r is not None else
            'pull_or_retention_failure' if h is not None else
            'bridge_failure' if any(x.get('chain_bridge_started') or x.get('chain_bridge_hold_s',0)>0 for x in rr) else
            'approach_or_grasp_failure')
        loss=next((x for j,x in enumerate(rr) if h is not None and (j+1)*.05>=h and not x['qualified_grasp']),None)
        physical_loss=next(((j+1)*.05 for j,x in enumerate(rr)
            if h is not None and (j+1)*.05>=h and not x.get('deposit_action_active')
            and min(x['fixed_force_N'],x['moving_force_N'])<.08),None)
        opening=[x for x in rr if x.get('deposit_action_active')]
        metrics.append(dict(trial_id=e['trial_id'],success=e['success'],phase=phase,reasons=e['reasons'],sample=e['sample'],
            grasp_confirmed=any(x.get('has_grasped') for x in rr),handoff_s=h,retained=r is not None,retained_s=r,
            stop_s=p,valid_detach=any(x.get('valid_detach') for x in rr),
            first_physical_contact_loss_after_handoff_s=physical_loss,
            first_qualification_loss_center_mm=None if loss is None else loss['center_error_m']*1000,
            first_qualification_loss_force_min_N=None if loss is None else min(loss['fixed_force_N'],loss['moving_force_N']),
            max_attached_stem_force_N=max((x.get('applied_stem_force_norm_N',0) for x in rr if x['attached']),default=0),
            max_opening_fruit_speed_m_s=max((x['fruit_speed_m_s'] for x in opening),default=None),
            opening_duration_s=len(opening)*.05,
            both_jaws_clear_after_open=any(x.get('deposit_both_jaws_clear') for x in opening)))
    report.update(schema='teacher60_jaw_surface_comparison_audit_v1',jaw_surface_comparison=spec,
        surface_clone_and_material_audited=True,phase_counts=dict(Counter(m['phase'] for m in metrics)),
        surface_metrics=metrics,retained=sum(m['retained'] for m in metrics),
        stop=sum(m['stop_s'] is not None for m in metrics),
        note='Actual closed-loop32 first episodes; original success/failure unchanged; surfaces changed before HOME, not cloned handoff states; rigid geometry surrogate, no calibrated rubber elasticity')
    return report


def compare(folders):
    reports=[analyze(p) for p in folders]
    base=reports[0];base_ids={m['trial_id'] for m in base['surface_metrics'] if m['success']}
    result=[]
    for folder,r in zip(folders,reports):
        ids={m['trial_id'] for m in r['surface_metrics'] if m['success']}
        if [m['sample'] for m in r['surface_metrics']]!=[m['sample'] for m in base['surface_metrics']]:raise ValueError('Assigned scenes differ')
        result.append(dict(folder=str(folder),spec=r['jaw_surface_comparison'],success=r['success'],retained=r['retained'],stop=r['stop'],
            recovered_ids=sorted(ids-base_ids),regressed_ids=sorted(base_ids-ids),
            preserved_success=len(ids & base_ids),original_failures_recovered=len(ids-base_ids),
            phase_counts=r['phase_counts'],metrics=r['surface_metrics']))
    return dict(schema='teacher60_jaw_surface_paired_results_v1',count_per_variant=32,
        baseline_failures=sorted(set(range(32))-base_ids),baseline_success=len(base_ids),variants=result,
        learning=False,hardware_executed=False,production_selection_changed=False)


if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('folders',nargs='+',type=Path);p.add_argument('--out',type=Path)
    a=p.parse_args();result=compare(a.folders)
    if a.out:a.out.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({**result,'variants':[{k:v for k,v in x.items() if k!='metrics'} for x in result['variants']]},indent=2))
