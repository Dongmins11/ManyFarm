"""Original force/retention/deposit audit plus paired stability intervention audit."""
import json
from pathlib import Path
from analyze_teacher60_pressure import analyze as original_audit
from analyze_teacher60_transport_servo import trace_rows


def analyze(path):
    path=Path(path); report=original_audit(path)
    run=json.loads((path/'run.json').read_text())
    contract=json.loads((path/'bridge_pull_contract.json').read_text())
    if run['pull_stability'] != contract['pull_stability']:
        raise ValueError('Stability contract mismatch')
    rows=trace_rows(path)
    reference=trace_rows(Path(run['pull_stability']['reference']))
    first=min((j for rr in rows.values() for j,x in enumerate(rr)
               if x['stability_pause'] or x['stability_early_trigger']), default=10**9)
    maximum=0.; metrics=[]
    for i,rr in rows.items():
        for x in rr:
            if x['stability_pause']:
                if not x['stability_scope'] or x['stability_qualified_before']:
                    raise ValueError('Pause outside failed qualification')
                if x['stability_pause_target_error_rad']>1e-7 or max(abs(x[f'arm_command_{k}']) for k in range(5))>1e-7:
                    raise ValueError('Nonzero arm command while paused')
        for x,y in zip(rr[:first],reference[i][:first]):
            for key in [f'arm_q_{k}_rad' for k in range(5)]+['fruit_x_m','fruit_y_m','fruit_z_m','jaw_target_rad']:
                maximum=max(maximum,abs(x[key]-y[key]))
        metrics.append(dict(trial_id=i,pause_steps=sum(bool(x['stability_pause']) for x in rr),
            early_intervention=any(x['stability_early_trigger'] for x in rr),
            unqualified_command_steps=sum(bool(x['stability_scope'] and not x['stability_qualified_before'] and max(abs(x[f'arm_command_{k}']) for k in range(5))>1e-7) for x in rr)))
    if maximum>1e-6:raise ValueError('Pre-intervention physical prefix changed: '+str(maximum))
    report.update(pull_stability=run['pull_stability'],stability_metrics=metrics,
        prefix_before_intervention_max_difference=maximum,original_gates_unchanged=True,
        comparison_note='Paired original32 scenes; early path and/or qualification pause only. Pressure stays original. No training.')
    return report
