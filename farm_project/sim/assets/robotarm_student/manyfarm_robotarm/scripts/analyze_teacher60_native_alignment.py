"""Audit physical pull outcomes plus the versioned, measured alignment costs."""
import json
import math
from pathlib import Path
import sys
from analyze_teacher60_bridge_training import analyze as audit_physical


def analyze(path):
    path = Path(path); report = audit_physical(path)
    run = json.loads((path/'run.json').read_text())
    contract = json.loads((path/'bridge_pull_contract.json').read_text())
    if contract['schema'] != 'teacher60_native_alignment_training_v1' or run['alignment'] != contract['alignment']:
        raise ValueError('Wrong alignment source contract')
    from harvest_rl.teacher_asset_reference import sha
    if sha(run['warm_checkpoint']) != run['warm_checkpoint_sha256']:
        raise ValueError('Warm checkpoint changed')
    traces = {i:[] for i in range(report['count'])}
    for line in (path/'trace.jsonl').open():
        d = json.loads(line)
        for i, values in zip(d['env_ids'], d['rows']):
            traces[i].append(dict(zip(d['columns'], values)))
    s = contract['alignment']; dt = run['actual_policy_dt_s']; metrics = []
    for i, rows in traces.items():
        start = next((j for j, r in enumerate(rows) if r['chain_handoff']), None)
        for j, r in enumerate(rows):
            costs = [r['native_alignment_'+k+'_cost'] for k in ('lateral','rotation','center','slip','extra_loss')]
            if not all(math.isfinite(v) and v >= 0 for v in costs):
                raise ValueError('Invalid reward cost')
            if abs(sum(costs)-r['native_alignment_total_cost']) > 2e-5:
                raise ValueError('Reward cost sum differs')
            if not r['ppo_active'] and r['native_alignment_total_cost'] > 1e-8:
                raise ValueError('HOME/bridge receives native reward')
            scope = bool(r['ppo_active'] and start is not None)
            pulling = scope and r['attached']
            expected = [dt*s['lateral_weight']*min(4., (r['native_alignment_lateral_m']/s['lateral_scale_m'])**2)*pulling,
                dt*s['rotation_weight']*min(4., (r['native_alignment_rotation_rad']/s['rotation_scale_rad'])**2)*pulling,
                dt*s['center_weight']*min(4., (max(0., r['distance_m']-s['center_margin_m'])/(s['center_limit_m']-s['center_margin_m']))**2)*scope,
                dt*s['slip_weight']*min(4., (r['slip_m']/s['slip_scale_m'])**2)*scope]
            if any(abs(a-b) > 2e-5 for a,b in zip(costs[:4], expected)):
                raise ValueError('Reward calculation differs from measured diagnostic')
            if r['native_pause']:
                if any(abs(r[f'arm_command_{k}']) > 1e-7 for k in range(5)):
                    raise ValueError('Arm still advances after qualification loss')
                if j and any(abs(r[f'arm_target_{k}_rad']-rows[j-1][f'arm_target_{k}_rad']) > 1e-6 for k in range(5)):
                    raise ValueError('Paused arm target changed')
        native = [r for r in rows if r['ppo_active']]
        early = [r for r in native if r['phase_elapsed_s'] < 3.]
        metrics.append(dict(trial_id=i, peak_early_lateral_mm=max((r['native_alignment_lateral_m']*1000 for r in early), default=0.),
            peak_early_hand_rotation_deg=max((math.degrees(r['native_alignment_rotation_rad']) for r in early), default=0.),
            summed_alignment_cost=sum(r['native_alignment_total_cost'] for r in native),
            contact_loss_events=sum(r['native_alignment_extra_loss_cost'] > 0 for r in native)))
    report.update(schema='teacher60_native_alignment_audit_v1', alignment_cost_verified=True,
        original_physical_gates=True, box_deposit_included=False, alignment_metrics=metrics)
    return report


if __name__ == '__main__':
    if len(sys.argv) != 2:
        raise SystemExit('Usage: analyze_teacher60_native_alignment.py OUTPUT')
    path = Path(sys.argv[1]); result = analyze(path)
    (path/'analysis.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k not in ('metrics','alignment_metrics')}, indent=2))
