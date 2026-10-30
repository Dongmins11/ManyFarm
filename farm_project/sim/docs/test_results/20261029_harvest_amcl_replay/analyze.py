"""격리 재생 AMCL과 원본 출력·USD를 같은 stamp로 비교. 실제 위치는 평가 전용."""
import json,math,sys
from pathlib import Path
import numpy as np
root=Path.cwd();base=root/'sim/runs/harvest_amcl_replay_20261029';trial=root/'sim/runs/transport_full_resume_20261029_attempt02'
drive=[json.loads(x) for x in (root/'sim/runs/drive_diagnostics/89508b4e79c6490c97f41f7ff044dae2/harvest_01.jsonl').open()];times=np.array([r['sim_time_s'] for r in drive]);xy=np.array([[r['T_world_base'][i][3] for i in (0,1)] for r in drive])
def stamp(d):s=d['header']['stamp'];return s['sec']+s['nanosec']/1e9
def pos(d):p=d['pose']['pose']['position'];return [p['x'],p['y']]
original=[json.loads(x)['data'] for x in (trial/'events.jsonl').open() if '"kind": "harvest_amcl"' in x]
for name in sys.argv[1:]:
 folder=base/name;data=json.loads((folder/'poses.json').read_text());rows=[];deltas=[]
 for d in data:
  t=stamp(d);actual=np.array([np.interp(t,times,xy[:,i]) for i in range(2)]);estimated=pos(d);rows.append(dict(sim=t,estimated_xy=estimated,actual_xy=actual.tolist(),error_m=float(np.linalg.norm(actual-estimated))))
  o=next((o for o in original if abs(stamp(o)-t)<1e-6),None)
  if o is not None:deltas.append(math.dist(pos(o),estimated))
 report=dict(replay=name,pose_count=len(data),matching_original_stamps=len(deltas),max_original_difference_m=max(deltas) if deltas else None,final=rows[-1] if rows else None,max_error_m=max(r['error_m'] for r in rows),mean_error_m=float(np.mean([r['error_m'] for r in rows])),rows=rows)
 (folder/'analysis.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({k:v for k,v in report.items() if k!='rows'},indent=2))
