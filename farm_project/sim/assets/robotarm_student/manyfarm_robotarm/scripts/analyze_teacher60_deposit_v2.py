"""Audit real deposit and frozen control; allow later batched physical divergence explicitly."""
import argparse
from collections import Counter
import json
import math
from pathlib import Path
from analyze_teacher60_transport_gain import analyze as audit_stop
from analyze_teacher60_transport_servo import trace_rows
from harvest_rl.teacher_asset_reference import sha
from harvest_rl.grasp_handoff_60hz import contract_digest


def analyze(path):
    path = Path(path)
    run = json.loads((path/'run.json').read_text())
    contract = json.loads((path/'bridge_pull_contract.json').read_text())
    evaluation = json.loads((path/'evaluation.json').read_text())
    root = Path(__file__).resolve().parents[1]
    if (not run.get('completed') or run['learning'] or run['hardware_executed']
            or not run['source_still_matches'] or not run['normalizers_unchanged']
            or not run['grasp_actor_unchanged'] or run['contract_sha256'] != contract_digest(contract)
            or abs(run['actual_physics_dt_s']-1/60) > 1e-12
            or abs(run['actual_policy_dt_s']-.05) > 1e-12):
        raise ValueError('Incomplete or mutated60/20Hz inference connection')
    for f, h in contract['files'].items():
        if sha(root/f) != h or sha(path/'source_snapshot'/f) != h:
            raise ValueError('Source mismatch: '+f)
    baseline = Path(run['stop_baseline'])
    audited = audit_stop(baseline)
    old_run = json.loads((baseline/'run.json').read_text())
    for key in ('split', 'seed', 'task', 'evaluation_checkpoint_sha256', 'grasp_checkpoint'):
        if run[key] != old_run[key]:
            raise ValueError('Unmatched upstream '+key)
    old_contract = json.loads((baseline/'bridge_pull_contract.json').read_text())
    for key in ('checkpoint_sha256', 'run_sha256', 'original_task'):
        if contract['transport'][key] != old_contract['transport'][key]:
            raise ValueError('Transport source changed')
    for f, h in old_contract['files'].items():
        if contract['files'].get(f) != h:
            raise ValueError('Frozen stop source changed: '+f)
    if json.loads((path/'initial_samples.json').read_text()) != json.loads((baseline/'initial_samples.json').read_text()):
        raise ValueError('Initial assigned scenes changed')
    rows, old = trace_rows(path), trace_rows(baseline)
    for rr in rows.values():
        for j, row in enumerate(rr):
            row['time_s'] = (j+1)*run['actual_policy_dt_s']
    episodes = evaluation['episodes']
    if evaluation['count'] != 32 or [e['trial_id'] for e in episodes] != list(range(32)):
        raise ValueError('Missing first assigned episodes')
    baseline_success = {m['trial_id'] for m in audited['metrics'] if m['success']}
    keys = ['arm_q_'+str(j)+'_rad' for j in range(5)] + ['arm_target_'+str(j)+'_rad' for j in range(5)] + [
        'fruit_'+axis+'_m' for axis in 'xyz'] + ['fixed_force_N', 'moving_force_N',
        'gripper_q_rad', 'jaw_target_rad', 'jaw_origin_rad', 'chain_bridge_hold_s',
        'detached_hold_s', 'transport_jaw_stiffness_Nm_rad', 'release_stop_s']
    first_release_time = min(x['time_s'] for rr in rows.values() for x in rr if x['deposit_handoff']) if any(x['deposit_handoff'] for rr in rows.values() for x in rr) else float('inf')
    maximum = 0.; compared = 0; metrics = []; handoffs = set()
    strict_max = 0.; later_differences = {}
    lo, hi = run['task']['box_min'], run['task']['box_max']
    tol = run['task']['box_contact_tolerance']
    bottom_tol = max(tol, run['task']['box_bottom_contact_tolerance'])
    for e in episodes:
        i = e['trial_id']; rr = rows[i]
        if not rr or any(not all(math.isfinite(v) for v in row.values()) for row in rr):
            raise ValueError('Missing/nonfinite trace')
        switch = [j for j, x in enumerate(rr) if x['deposit_handoff']]
        if len(switch) > 1:
            raise ValueError('Repeated deposit switch')
        h = switch[0] if switch else None
        prefix = rr[:h+1] if h is not None else rr
        if len(prefix) != len(old[i]):
            raise ValueError('Pre-release episode duration changed: '+str(i))
        for x, previous in zip(prefix, old[i]):
            for k in keys:
                if k not in x or k not in previous:continue
                delta = abs(x[k]-previous[k]); maximum = max(maximum, delta); compared += 1
                if x['time_s'] <= first_release_time:
                    strict_max = max(strict_max, delta)
                    if delta > 1e-6:
                        raise ValueError('Prefix changed before any release command: '+str(i)+' '+k+' '+str(delta))
                elif delta > 1e-6:
                    later_differences[k] = max(later_differences.get(k, 0.), delta)
        if h is not None:
            handoffs.add(i)
            if rr[h]['deposit_action_active'] or h < 5 or rr[h]['release_stop_s'] < .3-1e-6:
                raise ValueError('Early deposit authorization')
            for x in rr[h-5:h+1]:
                if not x['stop_all_ok'] or x['failure']:
                    raise ValueError('Missing original0.3s actual stop')
            for j in range(h+1, len(rr)):
                x, previous = rr[j], rr[j-1]
                if (not x['deposit_action_active'] or x['transport_action_active']
                        or x['deposit_arm_target_error_rad'] > 1e-6
                        or any(abs(x['arm_command_'+str(k)]) > 1e-7 for k in range(5))
                        or abs(x['jaw_origin_rad']-rr[h]['jaw_origin_rad']) > 1e-6
                        or abs(x['transport_jaw_stiffness_Nm_rad']-rr[h]['transport_jaw_stiffness_Nm_rad']) > 1e-6
                        or x['jaw_target_rad'] < previous['jaw_target_rad']-1e-6):
                    raise ValueError('Release scope/hold/gain/origin violation')
                max_delta = run['opening_rate_rad_s']*.05
                if j == h+1:
                    max_delta += max(0., rr[h]['gripper_q_rad']-rr[h]['jaw_target_rad'])
                if x['jaw_target_rad']-previous['jaw_target_rad'] > max_delta+1e-6:
                    raise ValueError('Repeated preload unloading or opening too fast')
                if abs(x['close_action']-run['opening_rate_rad_s']/run['task']['gripper_speed']) > 1e-6:
                    raise ValueError('Wrong actual jaw command')
            if h+1 < len(rr) and abs(rr[h+1]['deposit_elapsed_s']-.05) > 1e-5:
                raise ValueError('Release clock mismatch')
        for x in rr:
            if x['jaw_total_close_deg'] > 4.0001 or x['detached_stem_force_N'] > 1e-6 or x['detached_stem_torque_Nm'] > 1e-6:
                raise ValueError('Repeated squeeze or detached stem wrench')
        if e['success']:
            if h is None or rr[-1]['deposit_hold_s'] < run['task']['place_hold_s']-1e-6:
                raise ValueError('Success without actual deposit dwell')
            for x in rr[-round(run['task']['place_hold_s']/.05):]:
                if (not x['deposit_mesh_inside'] or not x['deposit_both_jaws_clear']
                        or x['attached'] or not x['has_retained'] or not x['valid_detach']
                        or x['failure'] or x['fruit_speed_m_s'] >= .12
                        or max(x['fixed_force_N'], x['moving_force_N']) >= run['task']['contact_threshold']):
                    raise ValueError('Success before physical separation/settling')
                for j, axis in enumerate('xyz'):
                    if (x['deposit_hull_lower_'+axis+'_m'] < lo[j]-(bottom_tol if j == 2 else tol)-1e-6
                            or x['deposit_hull_upper_'+axis+'_m'] > hi[j]+tol+1e-6):
                        raise ValueError('Actual collider outside box')
        after = rr[h+1:] if h is not None else []
        kind = ('deposited' if e['success'] else 'upstream_failure' if h is None else
                'release_timeout' if e['timeout'] else 'release_physical_failure')
        metrics.append(dict(trial_id=i, classification=kind, success=e['success'],
            stop_handoff=h is not None, reasons=e['reasons'], sample=e['sample'],
            release_duration_s=rr[-1]['deposit_elapsed_s'] if h is not None else None,
            clear_ever=any(x['deposit_both_jaws_clear'] for x in after),
            inside_ever=any(x['deposit_mesh_inside'] for x in after),
            release_approved=bool(rr[-1]['deposit_release_approved']),
            peak_release_speed_m_s=max((x['fruit_speed_m_s'] for x in after), default=0.),
            peak_release_angular_rad_s=max((x['deposit_fruit_angular_speed_rad_s'] for x in after), default=0.)))
    if handoffs != baseline_success:
        raise ValueError('Stop success IDs changed before release')
    success = sum(e['success'] for e in episodes)
    if success != evaluation['success']:
        raise ValueError('Wrong success total')
    return dict(schema='teacher60_actual_deposit_audit_v2', split=run['split'], count=32,
        success=success, stop_handoffs=len(handoffs), deposit_conditional_success=success/max(len(handoffs), 1),
        retained_handoffs=audited['retained_handoffs'], full_box_deposit_tested=True,
        learning=False, hardware_executed=False, production_selection_changed=False,
        stop_success_ids_unchanged=True, control_source_unchanged=True,
        prefix_before_any_release_unchanged=True, prefix_before_any_release_max_abs_difference=strict_max,
        prefix_values_compared=compared, prefix_max_abs_difference=maximum,
        later_batch_physical_differences=later_differences,
        comparison_note='After the first scene opens, other scenes no longer see the identical GPU physics/reset workload. Later state differences are reported, not labelled bit-exact unchanged.',
        actual_mesh_and_both_jaw_clear_dwell_audited=True,
        classification_counts=dict(Counter(m['classification'] for m in metrics)), metrics=metrics)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__); p.add_argument('output', type=Path)
    a = p.parse_args(); report = analyze(a.output)
    (a.output/'deposit_analysis_v2.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k != 'metrics'}, indent=2))
