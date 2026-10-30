"""실제 위치는 사후 평가에만 사용. AMCL 측정 stamp에 USD를 선형 보간한다."""
import json, math
from bisect import bisect_left
from pathlib import Path
base=Path(__file__).resolve().parent
root=base.parents[2]
session='245e670a6ec74fdcbc67164ec8578197'
drive=[json.loads(line) for line in (root/'sim/runs/drive_diagnostics'/session/'harvest_01.jsonl').read_text().splitlines()]
times=[row['sim_time_s'] for row in drive]
rows=[]
for line in (base/'events.jsonl').open():
    event=json.loads(line)
    if event['kind']!='harvest_amcl': continue
    data=event['data']; stamp=data['header']['stamp']; t=stamp['sec']+stamp['nanosec']/1e9
    i=bisect_left(times,t)
    if i==0 or i==len(times): continue
    a,b=drive[i-1],drive[i]; fraction=(t-times[i-1])/(times[i]-times[i-1])
    actual=[a['T_world_base'][j][3]*(1-fraction)+b['T_world_base'][j][3]*fraction for j in (0,1)]
    p=data['pose']['pose']['position']; estimated=[p['x'],p['y']]
    rows.append(dict(at=event['at'],sim=t,estimated_xy=estimated,actual_xy=actual,error_m=math.dist(actual,estimated)))
report=dict(session=session,count=len(rows),final=rows[-1] if rows else None,max_error_m=max((x['error_m'] for x in rows),default=None),rows=rows)
(base/'localization_analysis.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({k:v for k,v in report.items() if k!='rows'},indent=2))
