"""실제 인계→선별장 시험 결과와 정답 좌표 오차를 별도 보존한다."""
import argparse
import json
import math
import shutil
from pathlib import Path
import numpy as np

ROOT=Path(__file__).resolve().parents[2]

def main() -> None:
    parser=argparse.ArgumentParser();parser.add_argument('trial',type=Path);parser.add_argument('output',type=Path);args=parser.parse_args()
    trial=args.trial.resolve();out=args.output.resolve();out.mkdir(parents=True,exist_ok=True)
    events=[json.loads(line) for line in (trial/'events.jsonl').read_text().splitlines()]
    begin=next(x for x in events if x['kind']=='handoff_begin')
    session=begin['proof']['session'];diag=ROOT/'sim/runs/drive_diagnostics'/session
    records=[json.loads(line) for line in (diag/'transport_01.jsonl').read_text().splitlines()]
    result=json.loads((trial/'result.json').read_text());goal=result.get('sorter',{}).get('goal_xy')
    last=records[-1];matrix=np.asarray(last['T_world_base']);yaw=math.atan2(matrix[1,0],matrix[0,0])
    state=[x for x in events if x['kind']=='robot_status']
    start=next((x for x in events if x['kind']=='sorter_goal'),None)
    end=next((x for x in events if x['kind']=='sorter_result'),None)
    isaac=(trial/'isaac.log').read_text();exit_lines=[l for l in isaac.splitlines() if 'process has died' in l]
    summary=dict(scope='actual DOCK41 -> virtual handoff/common states -> CLEAR -> TransportNode CheckRoute/AMCL/RPP -> sorter approach',
        session=session,result=result,transfer_proof=next(x['proof'] for x in events if x['kind']=='sim_transfer_complete'),
        navigation_wall_s=end['wall']-start['wall'] if end and start else None,
        sequence_wall_s=end['wall']-next(x['wall'] for x in events if x['kind']=='goal') if end else None,
        final_ground_truth_xy=matrix[:2,3].tolist(),final_ground_truth_yaw=yaw,
        ground_truth_position_error_m=math.dist(matrix[:2,3],goal) if goal else None,
        ground_truth_heading_error_rad=abs(math.remainder(yaw-result['sorter']['goal_yaw'],2*math.pi)) if goal else None,
        final_wheel_velocity=last['wheel_odom'][3:],final_status=state[-1] if state else None,
        ground_truth_usage='evaluation only, not control/AMCL input',count_valid=False,loaded_count=None,
        process_exit=json.loads((trial/'process_exit.json').read_text()),isaac_child_exit_messages=exit_lines,
        freshness=json.loads((trial/'freshness_trace.summary.json').read_text()),
        environment=dict(domain=13,discovery='SUBNET',physics='CPU MBP 60Hz'),
        limits=['post-harvest fixture; no SEC survey/harvest this run','TRANSFER_COMPLETE calls common session directly; DDS peer relay not tested',
                'CheckRoute succeeds at approach; sorter docking/unloading not included','GT error is separate from AMCL-based arrival decision'])
    if state and goal:
        summary['estimated_position_error_m']=math.dist(state[-1]['xy'],goal)
    (out/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
    kinds={'goal','result','robot_status','sorter_goal','sorter_result','sorter_feedback','contact'}
    selected=[e for e in events if e['kind'] in kinds or e['kind'].startswith(('handoff','sim_transfer'))]
    (out/'events.jsonl').write_text(''.join(json.dumps(e,ensure_ascii=False)+'\n' for e in selected))
    samples=[dict(sim_time_s=r['sim_time_s'],xy=np.asarray(r['T_world_base'])[:2,3].tolist(),wheel_odom=r['wheel_odom']) for r in records[::10]]
    samples.append(dict(sim_time_s=last['sim_time_s'],xy=matrix[:2,3].tolist(),wheel_odom=last['wheel_odom']))
    (out/'trajectory.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in samples))
    for name in ['result.json','process_exit.json','navigation.log','probe.log','precision.log','transport_adapter.log','effective_controller.yaml','cmd_publishers.txt','effective_odom_topic.txt']:
        if (trial/name).is_file():
            shutil.copy2(trial/name,out/name)
            if name in ('cmd_publishers.txt','effective_controller.yaml'):
                (out/name).write_text((out/name).read_text().rstrip()+'\n')
    fixture=out/'fixture';fixture.mkdir(exist_ok=True)
    for name in ['transport_runtime.yaml','nav2_transport.yaml','stations.json','trial_geometry.json']:
        shutil.copy2(trial/name,fixture/name)
    (out/'isaac_exit.txt').write_text('\n'.join(exit_lines)+'\n')
    if goal:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        import yaml
        from PIL import Image
        mapdir=ROOT/'sim/ros_ws/src/farm_sim_config/maps';cfg=yaml.safe_load((mapdir/'count_test_farm_map.yaml').read_text())
        im=np.asarray(Image.open(mapdir/cfg['image']));h,w=im.shape[:2];x,y,_=cfg['origin'];res=cfg['resolution']
        fig,ax=plt.subplots(figsize=(12,5));ax.imshow(im,extent=[x,x+w*res,y,y+h*res],origin='upper')
        xy=np.array([np.asarray(r['T_world_base'])[:2,3] for r in records]);ax.plot(xy[:,0],xy[:,1],label='Actual robot (evaluation)',lw=2)
        valid=[s for s in state if all(math.isfinite(v) for v in s['xy'])]
        if valid:
            estimated=np.array([s['xy'] for s in valid]);ax.plot(estimated[:,0],estimated[:,1],label='AMCL estimate',alpha=.7)
        ax.scatter(*goal,marker='x',s=100,c='red',label='Sorter approach goal');model=yaml.safe_load((ROOT/'sim/ros_ws/src/farm_sim_config/config/transport_destinations.yaml').read_text())['destinations']['SORT_01']['model_reference']['world_xy_m'];ax.scatter(*model,marker='s',s=70,c='purple',label='Existing sorter')
        bounds=np.vstack([xy,goal,model]);lo=bounds.min(axis=0)-.7;hi=bounds.max(axis=0)+.7
        ax.set(xlim=(lo[0],hi[0]),ylim=(lo[1],hi[1]),xlabel='Map X (m)',ylabel='Map Y (m)',title='Dock / handoff / clear / sorter approach')
        ax.set_aspect('equal');ax.grid(alpha=.2);ax.legend(loc='upper right');fig.tight_layout();fig.savefig(out/'route.png',dpi=160);plt.close(fig)
    print(json.dumps({k:summary[k] for k in ['session','navigation_wall_s','ground_truth_position_error_m','final_wheel_velocity']},ensure_ascii=False))

if __name__=='__main__':main()
