"""Audit intended native-policy transfer and unchanged physical deposit gates."""
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
    height_changed=run['placement_height_v2']['minimum_changed']
    for key in ('split', 'seed', 'grasp_checkpoint'):
        if run[key] != old_run[key]:
            raise ValueError('Unmatched upstream '+key)
    old_contract = json.loads((baseline/'bridge_pull_contract.json').read_text())
    for key in ('checkpoint_sha256', 'run_sha256', 'original_task'):
        if contract['transport'][key] != old_contract['transport'][key]:
            raise ValueError('Transport source changed')
    for f, h in old_contract['files'].items():
        if contract['files'].get(f) != h:
            raise ValueError('Frozen stop source changed: '+f)
    if not height_changed and json.loads((path/'initial_samples.json').read_text()) != json.loads((baseline/'initial_samples.json').read_text()):
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
    first_transport_time = min(x['time_s'] for rr in rows.values() for x in rr if x['transport_handoff']) if any(x['transport_handoff'] for rr in rows.values() for x in rr) else float('inf')
    maximum = 0.; compared = 0; metrics = []; handoffs = set(); retained = set()
    from harvest_rl.transport_motion_compare import validate_motion
    speed, orientation = run['transport_speed_m_s'], run['orientation_length_m']
    validate_motion(speed, orientation)
    if contract['motion_comparison']['speed_m_s'] != speed or contract['motion_comparison']['orientation_length_m'] != orientation:
        raise ValueError('Motion contract mismatch')
    strict_max = 0.; later_differences = {}; duration_changes = {}
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
            if not height_changed and min(len(prefix),len(old[i]))*run['actual_policy_dt_s'] <= first_transport_time:
                raise ValueError('Episode duration changed before any transport')
            duration_changes[i]=(len(prefix)-len(old[i]))*run['actual_policy_dt_s']
        for x, previous in zip(prefix, old[i]):
            for k in keys:
                if k not in x or k not in previous:continue
                delta = abs(x[k]-previous[k]); maximum = max(maximum, delta); compared += 1
                if not height_changed and x['time_s'] <= first_transport_time:
                    strict_max = max(strict_max, delta)
                    if delta > 1e-6:
                        raise ValueError('Prefix changed before any transport command: '+str(i)+' '+k+' '+str(delta))
                elif delta > 1e-6:
                    later_differences[k] = max(later_differences.get(k, 0.), delta)
        transports = [j for j, x in enumerate(rr) if x['transport_handoff']]
        if len(transports) > 1: raise ValueError('Repeated transport switch')
        if transports:
            retained.add(i); u = transports[0]
            if (rr[u]['transport_action_active'] or rr[u]['detached_hold_s'] < .5-1e-6
                    or not rr[u]['has_retained'] or not rr[u]['valid_detach'] or not rr[u]['qualified_grasp']):
                raise ValueError('Transport before actual retention')
            if u < 9 or any(not x['qualified_grasp'] or not x['valid_detach'] or x['attached']
                           or x['failure'] for x in rr[u-9:u+1]):
                raise ValueError('Missing actual0.5s retention dwell')
        for x in rr:
            if not x['transport_action_active']: continue
            ramp = x['motion_compare_ramp']
            command = max(abs(x['arm_command_'+str(k)]) for k in range(5))*run['task']['action_speed']
            if (abs(x['motion_compare_speed_limit_m_s']-speed) > 1e-7
                    or abs(x['motion_compare_orientation_length_m']-orientation) > 1e-7
                    or x['transport_path_predicted_speed_m_s'] > speed*ramp+1e-6
                    or command > .3*ramp+1e-6
                    or (not x['motion_compare_qualified'] and command > 1e-7)):
                raise ValueError('Transport speed/qualification bound violated')
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
            if x['jaw_total_close_deg'] > 4.+run['pressure_comparison']['extra_close_deg']+1e-4 or x['detached_stem_force_N'] > 1e-6 or x['detached_stem_torque_Nm'] > 1e-6:
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
    from harvest_rl.placement_height_v2 import height_settings
    from harvest_rl.settings import TaskSettings
    expected_task,expected_placement=height_settings(TaskSettings(**old_run['task']),not height_changed)
    if expected_task.as_dict()!=run['task'] or expected_placement!=contract['placement_height_v2'] or expected_placement!=run['placement_height_v2']:
        raise ValueError('More than lower height changed or placement contract differs')
    import numpy as np
    bank=np.load(root/'outputs/harvest_rl/assets/workspace.npz')
    samples=json.loads((path/'initial_samples.json').read_text())
    points=bank['points'][[int(row[0]) for row in samples]]
    lo=np.array(expected_placement['lower_xyz_m']);hi=np.array(expected_placement['upper_xyz_m'])
    if not ((points>=lo-1e-7)&(points<=hi+1e-7)).all():raise ValueError('Sampled fruit outside new placement bounds')
    new_success = {e['trial_id'] for e in episodes if e['success']}
    improved = sorted(new_success-baseline_success); regressed = sorted(baseline_success-new_success)
    success = sum(e['success'] for e in episodes)
    if success != evaluation['success']:
        raise ValueError('Wrong success total')
    report=dict(schema='teacher60_pressure_audit_v1',placement_height_v2=expected_placement,
        paired_scene_comparison=not height_changed,nominal_min_sample_z_m=float(points[:,2].min()),nominal_max_sample_z_m=float(points[:,2].max()), split=run['split'], count=32,
        success=success, stop_handoffs=len(handoffs), deposit_conditional_success=success/max(len(handoffs), 1),
        retained_handoffs=len(retained), baseline_retained_handoffs=audited['retained_handoffs'],
        baseline_success=audited['success'],improved_ids=improved if not height_changed else None,regressed_ids=regressed if not height_changed else None,
        transport_speed_m_s=speed,orientation_length_m=orientation, full_box_deposit_tested=True,
        learning=False, hardware_executed=False, production_selection_changed=False,
        stop_success_ids_unchanged=handoffs==baseline_success if not height_changed else None, upstream_control_source_unchanged=True,
        transport_motion_intentionally_changed=(speed,orientation)!=(.035,.02),
        transport_speed_and_pause_audited=True,
        prefix_before_any_transport_unchanged=not height_changed, prefix_before_any_transport_max_abs_difference=strict_max,
        prefix_values_compared=compared, prefix_max_abs_difference=maximum,
        later_batch_physical_differences=later_differences, stop_duration_changes_s=duration_changes,
        comparison_note='Height-v2 changes sampled scenes by filtering the lower range; slot IDs are not paired comparisons. Frozen weights, original control, physical materials and success gates remain. Legacy diagnostic preserves original samples.',
        actual_mesh_and_both_jaw_clear_dwell_audited=True,
        classification_counts=dict(Counter(m['classification'] for m in metrics)), metrics=metrics)
    report=pressure_audit(path,run,contract,rows,episodes,report)
    return native_chain_audit(path,run,contract,rows,report)



def native_chain_audit(path,run,contract,rows,report):
    from harvest_rl.native_policy_transfer import verify_policy
    from harvest_rl.bridge_pull_training import source_metadata
    metadata,_=source_metadata(run['grasp_checkpoint'])
    _,verified=verify_policy(metadata,run['pull_checkpoint'],run['evaluation_checkpoint'],run['native_policy']['role'])
    if verified!=run['native_policy'] or verified!=contract['native_policy']:
        raise ValueError('Native checkpoint/control selection differs')
    reference=Path(run['pressure_comparison']['reference'])
    old=trace_rows(reference);prefix=0.
    if run['pull_stability']!=contract['pull_stability'] or run['settle_compliance']!=contract['settle_compliance'] or run['posture_comparison']!=contract['posture_comparison']:
        raise ValueError('Preserved chain controller metadata changed')
    final=run['settle_compliance']['final_gain_Nm_rad']
    limit=run['settle_compliance']['goal_limit_m']
    if limit not in (.005,.01):raise ValueError('Unexpected plateau eligibility limit')
    for i,rr in rows.items():
        for j,x in enumerate(rr):
            if x['jaw_total_close_deg']>4.+1e-4:
                raise ValueError('Original4degree jaw budget exceeded')
            if x['stability_pause'] and (not x['stability_scope'] or x['stability_qualified_before'] or x['stability_pause_target_error_rad']>1e-7 or max(abs(x[f'arm_command_{k}']) for k in range(5))>1e-7):
                raise ValueError('Invalid qualification pause')
            gain=x['transport_jaw_stiffness_Nm_rad']
            if not final-1e-6<=gain<=8+1e-6 or (not x['transport_gain_active'] and abs(gain-8)>1e-6):raise ValueError('Gain outside actual plateau scope')
            if x['transport_action_active']:
                reserve=.5 if x['settle_pre_center_m']<.006 and x['settle_pre_slip_m']<.006 else 1.
                if abs(x['settle_force_requirement_N']-reserve)>1e-7:raise ValueError('Unbounded weak-contact relaxation')
                previous=x['settle_pre_gain_Nm_rad']
                if gain>previous+1e-6 or previous-gain>.350001:raise ValueError('Gain ramp rate/increase violation')
                if not x['settle_ramp_allowed'] and abs(gain-previous)>1e-6:raise ValueError('Unprotected relaxation')
                if x['settle_ramp_allowed'] and (x['settle_pre_center_m']>=.008+1e-7 or x['settle_pre_slip_m']>=.008+1e-7 or x['settle_pre_force_N']<=x['settle_force_requirement_N']-1e-7 or x['settle_pre_sdk_speed_m_s']<=.18-1e-7):raise ValueError('Missing contact reserve or jitter guard')
            if x.get('transport_gain_eligible',0.):
                if (not x['settle_pre_zone'] or not x['settle_pre_grip'] or not x['settle_pre_raw']
                        or x['settle_pre_release'] or x['settle_pre_slip_m']>=run['task']['max_slip']
                        or x['settle_pre_goal_error_m']>=limit+1e-7
                        or x['settle_pre_tcp_speed_m_s']>.02+1e-7 or x['settle_pre_pose_speed_m_s']>.02+1e-7
                        or x['settle_pre_sdk_speed_m_s']<=.2-1e-7 or x['settle_pre_force_N']<=.5-1e-7):
                    raise ValueError('Relaxation without actual stationary qualified box plateau')
            if x.get('transport_gain_started',0.) and (j<5 or any(not y.get('transport_gain_eligible',0.) for y in rr[j-5:j+1])):raise ValueError('Plateau gate missing')
            if x['posture_changed'] and (not x['posture_scope'] or not x['transport_action_active'] or x['deposit_action_active']):raise ValueError('Invalid posture scope')
            if x['posture_first'] and (j<9 or any(not y['posture_stall'] for y in rr[j-9:j+1])):raise ValueError('Unconfirmed posture stall')
            if x['posture_active'] and (x['posture_angle_rad']>=.6+1e-6 or x['posture_predicted_angular_rad_s']>.08+1e-6):raise ValueError('Posture bound exceeded')
            if x['posture_center_path_m']>.002+1e-6:raise ValueError('Center correction budget exceeded')
        end=min(next((j+1 for j,x in enumerate(rr) if x['chain_handoff']),len(rr)),
                next((j+1 for j,x in enumerate(old[i]) if x['chain_handoff']),len(old[i])))
        for x,y in zip(rr[:end],old[i][:end]):
            for k in [f'arm_q_{j}_rad' for j in range(5)]+[f'arm_target_{j}_rad' for j in range(5)]+['jaw_target_rad','fruit_x_m','fruit_y_m','fruit_z_m','fixed_force_N','moving_force_N']:
                prefix=max(prefix,abs(x[k]-y[k]))
    override=run['floor_collision_override']
    if override!=contract['floor_collision_override']:raise ValueError('Undeclared floor collision change')
    collision=json.loads((path/'floor_override.json').read_text())
    clones=json.loads((path/'floor_clone_audit.json').read_text())
    if collision['mode']!=override['mode'] or collision['added_shapes']!=0 or collision['original_usd_modified'] or collision['visible_geometry_modified'] or not clones['all_clones_verified'] or clones['collider_count']!=128:raise ValueError('Floor override scope mismatch')
    if override['mode']=='buffered' and (not clones.get('all_contact_and_rest_offsets_verified') or collision.get('contact_offset_m')!=.04 or collision.get('rest_offset_m')!=0.):raise ValueError('Floor contact buffer differs')
    for e in collision['edits']:
        if max(abs(e['upper_xyz_m'][j]-e['original_upper_xyz_m'][j]) for j in range(3))>1e-6 or max(abs(e['lower_xyz_m'][j]-e['original_lower_xyz_m'][j]) for j in range(2))>1e-6:raise ValueError('Floor top/XY changed')
        if abs(e['upper_xyz_m'][2]-.501)>1e-5 or abs(e['upper_xyz_m'][2]-e['lower_xyz_m'][2]-override['depth_m'])>1e-5:raise ValueError('Floor depth differs')
    if override['mode']=='original' and prefix>1e-6:raise ValueError('Original floor physical prefix changed: '+str(prefix))
    report['floor_collision_override_audited']=True
    report['physical_asset_intentionally_changed']=override['mode']!='original'
    report.update(schema='teacher60_floor_guarded_audit',native_policy_role=verified['role'],
        native_policy_sha256=verified['checkpoint_sha256'],actual_gain_scope_verified=True,
        posture_scope_verified=True,pre_native_prefix_max_difference=prefix,
        upstream_control_source_unchanged=True,
        comparison_note='Same32 height-v2 scenes, preserved pause/gain1/posture-position/deposit controls. Four closed-floor collision tiles explicitly modified; same models and guarded controls. Original actual stop/deposit gates unchanged; physical prefix may differ with collision cooking.')
    return report

def pressure_audit(path,run,contract,rows,episodes,report):
    from harvest_rl.pressure_compare import PressureSpec
    spec=PressureSpec(run['pressure_comparison']['goal_N'],run['pressure_comparison']['extra_close_deg'],run['pressure_comparison']['rate_deg_s']).validate()
    if run['pressure_comparison']!=contract['pressure_comparison']:raise ValueError('Pressure contract differs')
    reference=Path(run['pressure_comparison']['reference'])
    original=json.loads((reference/'evaluation.json').read_text())
    original_run=json.loads((reference/'run.json').read_text())
    if original_run['split']!=run['split'] or original_run['task']!=run['task']:raise ValueError('Pressure reference domain differs')
    if json.loads((path/'initial_samples.json').read_text())!=json.loads((reference/'initial_samples.json').read_text()):raise ValueError('Pressure trials differ from original failed scenes')
    old_success={e['trial_id'] for e in original['episodes'] if e['success']}
    new_success={e['trial_id'] for e in episodes if e['success']}
    old_fail=set(range(32))-old_success
    pressure_metrics=[]
    for e in episodes:
        i=e['trial_id'];rr=rows[i];last_spent=0.;origin=None
        before_pull=[x for x in rr if x['pressure_scope'] and not x['chain_pull_active']]
        handoff=next((x for x in rr if x['chain_handoff']),None)
        for x in rr:
            spent=x['pressure_spent_rad'];inc=x['pressure_increment_rad']
            if spent<-1e-7 or spent>math.radians(spec.extra_close_deg)+1e-6 or spent<last_spent-1e-7:raise ValueError('Pressure budget renewed/exceeded')
            if inc>math.radians(spec.rate_deg_s)*.05+1e-7 or inc<-1e-7:raise ValueError('Pressure rate exceeded')
            if inc>1e-7 and (not x['pressure_scope'] or not x['pressure_feedback_qualified'] or x['pressure_normal_before_N']>=spec.goal_N):raise ValueError('Pressure outside qualification/weak-force scope')
            if x['pressure_scope'] and spec.goal_N:
                origin=x['pressure_origin_before_rad'] if origin is None else origin
                if abs(x['pressure_origin_before_rad']-origin)>1e-6:raise ValueError('Pressure origin rebase')
                if x['pressure_target_rad']<x['pressure_measured_before_rad']-run['task']['gripper_max_error']-1e-6:raise ValueError('Pressure tracking error bound')
            if not x['pressure_scope'] and abs(x['pressure_target_rad']-x['pressure_base_target_rad'])>1e-6:raise ValueError('Pressure altered approach/transport/release')
            if inc>1e-7 and abs(spent-last_spent-inc)>1e-6:raise ValueError('Pressure increment not charged once')
            last_spent=spent
        min_at_handoff=None if handoff is None else min(handoff['loaded_fixed_normal_N'],handoff['loaded_moving_normal_N'])
        pressure_metrics.append(dict(trial_id=i,previously_failed=i in old_fail,success=e['success'],retained=any(x['transport_handoff'] for x in rr),
            handoff_normal_min_N=min_at_handoff,goal_reached_at_handoff=None if handoff is None else min_at_handoff>=spec.goal_N,
            max_pre_pull_normal_min_N=max((min(x['loaded_fixed_normal_N'],x['loaded_moving_normal_N']) for x in before_pull),default=0.),
            spent_deg=last_spent*180/math.pi,max_attached_force_N=max((x['applied_stem_force_norm_N'] for x in rr if x['attached']),default=0.),
            max_attached_torque_Nm=max((x['applied_stem_torque_norm_Nm'] for x in rr if x['attached']),default=0.)))
    report.update(pressure_comparison=run['pressure_comparison'],paired_scene_comparison=True,
        original_failed_ids=sorted(old_fail),recovered_failed_ids=sorted(new_success-old_success),regressed_ids=sorted(old_success-new_success),
        baseline_success=len(old_success),failure_subset_success=len(new_success & old_fail),
        original_success_preserved=old_success<=new_success,pressure_metrics=pressure_metrics,
        comparison_note='Exactly the original32 sampled poses. Score the eight original failures;24 original successes are regression controls. Force targets are normal-force feedback triggers, not injected or guaranteed constant forces.')
    return report


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__); p.add_argument('output', type=Path)
    a = p.parse_args(); report = analyze(a.output)
    (a.output/'height_v2_analysis.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k != 'metrics'}, indent=2))
