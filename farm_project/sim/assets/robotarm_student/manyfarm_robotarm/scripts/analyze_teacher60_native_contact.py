"""Audit real bridge/retention gates and reward arithmetic from read-only traces."""
import json
import math
from pathlib import Path
import sys
from analyze_teacher60_bridge_training import analyze as physical_audit


def analyze(path):
    path = Path(path); report = physical_audit(path)
    run = json.loads((path/'run.json').read_text())
    contract = json.loads((path/'bridge_pull_contract.json').read_text())
    if contract['schema'] != 'teacher60_native_contact_training_v1' or run['contact_refine'] != contract['contact_refine']:
        raise ValueError('Wrong refinement contract')
    s = contract['contact_refine']; dt = run['actual_policy_dt_s']
    totals = {k:0. for k in ('transverse','angular','reserve','collision')}
    frames = 0
    for line in (path/'trace.jsonl').open():
        frame = json.loads(line)
        for values in frame['rows']:
            r = dict(zip(frame['columns'], values)); scope = bool(r['ppo_active'])
            values = [r['native_contact_'+k+'_cost'] for k in totals]
            if not all(math.isfinite(v) and v >= 0 for v in values):
                raise ValueError('Invalid contact reward')
            if abs(sum(values)-r['native_contact_total_cost']) > 3e-5:
                raise ValueError('Contact reward sum differs')
            if not scope and r['native_contact_total_cost'] > 1e-8:
                raise ValueError('HOME/bridge received learner reward')
            expected = [
                dt*s['transverse_weight']*min(s['cost_square_cap'], (r['native_contact_transverse_speed_m_s']/s['transverse_speed_m_s'])**2)*scope,
                dt*s['angular_weight']*min(s['cost_square_cap'], (r['native_contact_angular_speed_rad_s']/s['angular_speed_rad_s'])**2)*scope,
                dt*s['reserve_weight']*r['native_contact_reserve_shortage']**2*scope,
                dt*s['collision_weight']*min(s['cost_square_cap'], (max(0., r['arm_max_force_N']-s['collision_margin_N'])/s['collision_scale_N'])**2)*scope]
            if any(abs(v-e) > 3e-5 for v,e in zip(values, expected)):
                raise ValueError('Contact reward calculation differs')
            if scope and not s['reserve_min_N']-1e-6 <= r['native_contact_reserve_N'] <= s['reserve_max_N']+1e-6:
                raise ValueError('Invalid measured handoff reserve')
            for k, value in zip(totals, values): totals[k] += value
            frames += 1
    floor = json.loads((path/'floor_clone_audit.json').read_text())
    if not floor['all_clones_verified'] or floor['added_rigid_bodies'] or floor['active_floor_colliders'] != report['count']:
        raise ValueError('Selected floor not installed in all training clones')
    samples = json.loads((path/'initial_samples.json').read_text())
    if run['split'] == 'train' and any(not 0 <= row[0] < run['train_bank_end_exclusive'] for row in samples):
        raise ValueError('Held-out bank position leaked into training')
    report.update(contact_reward_verified=True, checked_frames=frames,
        reward_cost_sums=totals, floor_all_clones_verified=True,
        initial_priority_count=sum(int(row[0]) in run['priority_bank_ids'] for row in samples),
        training_gate_is_performance_proof=False, box_deposit_included=False)
    return report


if __name__ == '__main__':
    if len(sys.argv) != 2: raise SystemExit('Usage: analyze_teacher60_native_contact.py OUTPUT')
    path = Path(sys.argv[1]); report = analyze(path)
    (path/'analysis.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k != 'metrics'}, indent=2))
