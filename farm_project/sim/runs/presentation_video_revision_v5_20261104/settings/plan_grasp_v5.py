"""누운 원본 과실에 맞는 집게 수평방향·벌림을 실제 정점으로 탐색한다."""
from pathlib import Path
import json
import numpy as np
from scipy.spatial.transform import Rotation
from build_continuous_v5 import joint_data, fk, read, V3

HERE=Path(__file__).resolve().parent

def main():
    evidence=read(HERE/'06_07_motion_evidence.json')
    geometry=read(HERE.parent/'qa/06_07_actual_robot_cubes.json')['arm']
    data,initial=joint_data('arm')
    points={x['source']:np.asarray(x['root_local_points']) for x in read(V3/'handoff_mesh_points.json')}
    result=[]
    for pick in evidence['picks']:
        fruit=next(x for x in evidence['fruits'] if x['id']==pick['id'])
        m=np.asarray(evidence['frames'][150]['fruit_states'][pick['id']]['station_local_matrix'])
        world=points[fruit['source']]@m[:3,:3].T+m[:3,3]
        best=None
        for yaw in np.arange(0,180,10):
            R=Rotation.from_euler('z',np.radians(yaw)).as_matrix()@Rotation.from_euler('y',np.pi/2).as_matrix()
            # 노랑 레인의 경사면 여유를 확보하고, 빨강은 앞쪽 집기 높이를 유지한다.
            for dz in ((.01,) if pick['color']=='yellow' else (0.,)):
                center=m[:3,3]+[0,0,dz]
                pc=(world-center)@R
                # 손가락 중앙 단면에서 몸통의 실제 좌우 외곽을 맞춘다.
                use=(pc[:,0]>=-.04)&(pc[:,0]<=.0)&(abs(pc[:,2])<=.014)
                if not use.any():continue
                shift=(pc[use,1].min()+pc[use,1].max())/2
                center=center+R[:,1]*shift;pc=(world-center)@R
                for jaw in np.arange(0,.01001,.0005):
                    q=dict(left_jaw=jaw,right_jaw=jaw)
                    tcp=fk(data,initial,data['tcp_mount']['b'],q)
                    depths={}
                    for cube in geometry['visual_cubes']:
                        if not any('/'+x+'/' in cube['path'] for x in ('left_pad','right_pad','left_finger','right_finger','tool')):continue
                        mat=np.linalg.inv(tcp)@fk(data,initial,cube['body'],q)@np.asarray(cube['body_relative_matrix'])
                        inv=np.linalg.inv(mat);p=pc@inv[:3,:3].T+inv[:3,3]
                        depth=(cube['size']/2-abs(p))*np.linalg.norm(mat[:3,:3],axis=0)
                        depths[cube['path'].split('/')[2]]=max(0.,float(depth.min(1).max()))
                    fingers=max(v for k,v in depths.items() if k not in ('left_pad','right_pad'))
                    pads=[depths['left_pad'],depths['right_pad']]
                    if fingers>.00005 or max(pads)>.00205 or min(pads)<.0001:continue
                    # 과도한 오프셋/벌림은 피하고 양쪽 패드의 접촉 균형을 우선한다.
                    score=abs(pads[0]-pads[1])+abs(dz)*.01+abs(shift)*.01+jaw*.001
                    if best is None or score<best[0]:
                        best=(score,dict(id=pick['id'],color=pick['color'],yaw_deg=float(yaw),
                            center_offset_m=(center-m[:3,3]).tolist(),jaw_m=float(jaw),
                            rotation=R.tolist(),depths_m=depths))
        if best is None:raise RuntimeError(f'No non-penetrating grip: {pick["id"]}')
        result.append(best[1]);print(json.dumps(best[1]))
    (HERE/'06_07_grasp_plan.json').write_text(json.dumps(result,indent=2)+'\n')

if __name__=='__main__':main()
