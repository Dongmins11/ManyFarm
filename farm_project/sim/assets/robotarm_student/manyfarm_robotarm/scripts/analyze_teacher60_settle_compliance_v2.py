"""Verify actual phase-local drive gain, existing stop and release gates."""
import json
from pathlib import Path
from analyze_teacher60_pull_stability import analyze as audit_stability
from analyze_teacher60_transport_servo import trace_rows


def analyze(path):
    path=Path(path);report=audit_stability(path)
    run=json.loads((path/'run.json').read_text());contract=json.loads((path/'bridge_pull_contract.json').read_text())
    if run['settle_compliance']!=contract['settle_compliance']:raise ValueError('Compliance contract mismatch')
    final=run['settle_compliance']['final_gain_Nm_rad']
    for rr in trace_rows(path).values():
        for j,x in enumerate(rr):
            gain=x['transport_jaw_stiffness_Nm_rad']
            if not final-1e-6<=gain<=8+1e-6:raise ValueError('Actual gain outside finite range')
            if not x['transport_gain_active'] and abs(gain-8)>1e-6:raise ValueError('Gain changed before plateau trigger')
            if x['transport_gain_active'] and 'transport_gain_started' not in x:
                raise ValueError('Missing active gain diagnostics')
            if x.get('transport_gain_started',0.):
                if j<5 or any(not y.get('transport_gain_eligible',0.) for y in rr[j-5:j+1]):raise ValueError('Unqualified gain transition')
    report.update(settle_compliance=run['settle_compliance'],actual_gain_scope_verified=True)
    return report

if __name__=='__main__':
    import argparse,hashlib
    p=argparse.ArgumentParser();p.add_argument('output',type=Path);a=p.parse_args()
    report=analyze(a.output)
    report['post_audit_source_sha256']=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    (a.output/'analysis_v2.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:report[k] for k in ['success','retained_handoffs','recovered_failed_ids','regressed_ids','actual_gain_scope_verified']}))
