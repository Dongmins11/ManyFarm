"""Audit only bounded, qualified transport posture intervention."""
import json
from pathlib import Path
from analyze_teacher60_settle_compliance_v2 import analyze as audit_parent
from analyze_teacher60_transport_servo import trace_rows


def analyze(path):
    path=Path(path);report=audit_parent(path)
    run=json.loads((path/'run.json').read_text());contract=json.loads((path/'bridge_pull_contract.json').read_text())
    if run['posture_comparison']!=contract['posture_comparison']:raise ValueError('Posture metadata differs')
    rows=trace_rows(path);old=trace_rows(Path(run['pressure_comparison']['reference']))
    first=min((j for rr in rows.values() for j,x in enumerate(rr) if x['posture_changed']),default=10**9)
    maximum=0.;metrics=[]
    for i,rr in rows.items():
        for j,x in enumerate(rr):
            if x['posture_changed'] and (not x['posture_scope'] or not x['transport_action_active'] or x['deposit_action_active']):raise ValueError('Invalid posture scope')
            if x['posture_first'] and (j<9 or any(not y['posture_stall'] for y in rr[j-9:j+1])):raise ValueError('Unconfirmed posture stall')
            if x['posture_active'] and (x['posture_angle_rad']>=.6+1e-6 or x['posture_predicted_angular_rad_s']>.08+1e-6):raise ValueError('Posture angle/speed exceeded')
            if x['posture_center_path_m']>.002+1e-6:raise ValueError('Center correction budget exceeded')
        for x,y in zip(rr[:first],old[i][:first]):
            for k in [f'arm_q_{j}_rad' for j in range(5)]+[f'arm_target_{j}_rad' for j in range(5)]+['jaw_target_rad','fruit_x_m','fruit_y_m','fruit_z_m']:
                maximum=max(maximum,abs(x[k]-y[k]))
        metrics.append(dict(trial_id=i,active_ticks=sum(bool(x['posture_active']) for x in rr),center_ticks=sum(bool(x['posture_center_active']) for x in rr),max_angle_rad=max(x['posture_angle_rad'] for x in rr)))
    if maximum>1e-6:raise ValueError('Pre-posture physical prefix differs: '+str(maximum))
    report.update(posture_comparison=run['posture_comparison'],posture_metrics=metrics,posture_prefix_max_difference=maximum)
    return report
