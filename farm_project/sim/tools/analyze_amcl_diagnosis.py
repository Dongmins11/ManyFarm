"""AMCL 측정 stamp와 시뮬 진단 pose를 비교한다. 정답은 평가 파일로만 사용한다."""
import argparse
import json
import math
from pathlib import Path
import numpy as np

ROOT=Path(__file__).resolve().parents[2]


def analyze(trial: Path) -> dict:
    raw=[json.loads(l) for l in (trial/'localization.jsonl').read_text().splitlines()]
    events=[json.loads(l) for l in (trial/'events.jsonl').read_text().splitlines()]
    session=json.loads((trial/'sorting/runtime.json').read_text())['session']
    drive=[json.loads(l) for l in (ROOT/'sim/runs/drive_diagnostics'/session/'transport_01.jsonl').read_text().splitlines()]
    stamps=np.array([r['sim_time_s'] for r in drive]);monos=np.array([r['monotonic_s'] for r in drive])
    fixture=json.loads((trial/'fixture.json').read_text());yaw=fixture['initial_yaw']
    rotation=np.array([[math.cos(yaw),-math.sin(yaw)],[math.sin(yaw),math.cos(yaw)]])
    poses=[]
    for r in (r for r in raw if r['kind']=='amcl_pose'):
        p=r['data'];s=p['header']['stamp'];stamp=s['sec']+s['nanosec']/1e9
        d=drive[int(np.argmin(abs(stamps-stamp)))];T=np.array(d['T_world_base']);actual=T[:2,3]
        position=p['pose']['pose']['position'];estimated=np.array([position['x'],position['y']])
        q=p['pose']['pose']['orientation'];heading=math.atan2(2*(q['w']*q['z']+q['x']*q['y']),1-2*(q['y']**2+q['z']**2))
        odom=np.array(fixture['initial_xy'])+rotation@np.array(d['wheel_odom'][:2])
        poses.append(dict(stamp=stamp,truth_time_delta_s=abs(d['sim_time_s']-stamp),truth_xy=actual.tolist(),estimated_xy=estimated.tolist(),
            position_error_m=float(np.linalg.norm(actual-estimated)),heading_error_rad=abs(math.remainder(heading-math.atan2(T[1,0],T[0,0]),2*math.pi)),
            odom_error_m=float(np.linalg.norm(actual-odom)),covariance_xy=[p['pose']['covariance'][i] for i in (0,7)]))
    before_return=None
    goal=next((r for r in events if r['kind']=='return_goal'),None)
    if goal:
        s=[r for r in events if r['kind']=='robot_status' and r['mono']<goal['mono']][-1]
        d=drive[int(np.argmin(abs(monos-(s['mono']-.15))))];T=np.array(d['T_world_base']);p=s['data']['pose']['position'];actual=T[:2,3]
        odom=np.array(fixture['initial_xy'])+rotation@np.array(d['wheel_odom'][:2])
        before_return=dict(sim_time_s=d['sim_time_s'],truth_xy=actual.tolist(),estimated_xy=[p['x'],p['y']],
            position_error_m=math.dist(actual,[p['x'],p['y']]),odom_error_m=float(np.linalg.norm(actual-odom)),method='stationary status matched to wall-.15s')
    result=json.loads((trial/'result.json').read_text()) if (trial/'result.json').exists() else None
    return dict(trial=str(trial.relative_to(ROOT)),session=session,amcl_pose_count=len(poses),
        maximum_error_m=max(p['position_error_m'] for p in poses),mean_error_m=float(np.mean([p['position_error_m'] for p in poses])),
        before_return=before_return,final_amcl=poses[-1],result=result,poses=poses)


def main() -> None:
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('trial',type=Path);parser.add_argument('output',type=Path)
    args=parser.parse_args();report=analyze(args.trial.resolve());args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k not in ('result','poses')},ensure_ascii=False,indent=2))


if __name__=='__main__':main()
