"""V5 물리 베이크의 실제 메시-원본 평판 접촉과 7개 수량을 별도 검산한다."""
from pathlib import Path
import hashlib,json,itertools
import numpy as np
from scipy.optimize import linprog
from scipy.spatial import ConvexHull
from scipy.spatial.transform import Rotation
from build_handoff_v5 import HERE,ROOT,PATHS,FPS,gap,lid

def audit() -> dict:
    data=json.loads((HERE/'05_physics_geometry.json').read_text())
    bake=json.loads((HERE/'05_physics_bake.json').read_text())
    meshes={x['source']:np.asarray(x['root_local_points']) for x in json.loads((ROOT/'sim/runs/presentation_video_revision_v3_20261104/settings/handoff_mesh_points.json').read_text())}
    max_cube=0.;cube_events=[];max_pair=0.;pair_events=[]
    stable=[];positions=[];rotations=[]
    for frame in bake['frames']:
        cloud=[];hulls=[];bounds=[];pos=[];rots=[]
        t=frame['time']
        for fruit in data['fruits']:
            m=np.asarray(frame['placements'][fruit['path']]);w=meshes[fruit['source']]@m[:3,:3].T+m[:3,3]
            cloud.append(w);bounds.append([w.min(0),w.max(0)]);hulls.append(ConvexHull(w).equations)
            pos.append(m[:3,3]);rots.append(m[:3,:3]/np.asarray(fruit['scale']))
        positions.append(pos);rotations.append(rots)
        for i,w in enumerate(cloud):
            for c in data['colliders']:
                delta=np.asarray(c['axis'])*(gap(t) if c['motion']=='floor' else lid(t) if c['motion']=='lid' else 0.)
                lo,hi=np.asarray(c['world_bounds'])+delta
                if np.any(bounds[i][1]<lo) or np.any(bounds[i][0]>hi):continue
                depth=np.minimum(w-lo,hi-w).min(1).max()
                max_cube=max(max_cube,float(depth))
                if depth>.0005:cube_events.append({'frame':round(t*FPS),'time_s':t,'fruit':PATHS[i],'collider':c['path'],'actual_vertex_penetration_m':float(depth)})
        for i,j in itertools.combinations(range(7),2):
            if np.min(np.minimum(bounds[i][1],bounds[j][1])-np.maximum(bounds[i][0],bounds[j][0]))<=0:continue
            eq=np.vstack([hulls[i],hulls[j]])
            # 공통 내접구 반경: 두 볼록 외피가 함께 차지하는 체적의 보수적 척도다.
            fit=linprog([0,0,0,-1],A_ub=np.c_[eq[:,:3],np.ones(len(eq))],b_ub=-eq[:,3],bounds=[(None,None)]*3+[(0,None)],method='highs')
            if fit.success:
                depth=float(fit.x[3]);max_pair=max(max_pair,depth)
                if depth>.0005:pair_events.append({'frame':round(t*FPS),'fruits':[PATHS[i],PATHS[j]],'convex_intersection_insphere_radius_m':depth})
    positions=np.asarray(positions);rotations=np.asarray(rotations)
    speed=np.linalg.norm(np.diff(positions,axis=0),axis=2)*FPS
    omega=np.array([(Rotation.from_matrix(rotations[:-1,i]).inv()*Rotation.from_matrix(rotations[1:,i])).magnitude()*FPS for i in range(7)]).T
    # 5 mm/s 및 0.1 rad/s 이하가 이후 전 구간 유지되는 최초 시각. 닫힘 전/후 모두 검사한다.
    quiet=(speed.max(1)<.005)&(omega.max(1)<.1)
    settled=next((bake['frames'][i]['time'] for i in range(len(quiet)) if all(quiet[i:]) and bake['frames'][i]['time']>1.65),None)
    result={'scope':'151 discrete baked frames; actual fruit vertex-vs-source-box penetration and conservative fruit convex intersection; not swept/full robot/dynamic certification',
        'input_sha256':{n:hashlib.sha256((HERE/n).read_bytes()).hexdigest() for n in ['05_physics_geometry.json','05_physics_bake.json','05_handoff_continuity.json']},
        'actual_vertex_penetration_max_m':max_cube,'actual_vertex_penetration_over_0_5mm_events':cube_events,
        'pair_convex_intersection_insphere_radius_max_m':max_pair,'pair_convex_intersection_over_0_5mm_events':pair_events,
        'settle_definition':{'max_linear_speed_m_s':.005,'max_angular_speed_rad_s':.1,'must_hold_through_raw5':True},
        'all_settled_s':settled,'max_linear_speed_after_raw3_m_s':float(speed[90:].max()),'max_angular_speed_after_raw3_rad_s':float(omega[90:].max()),
        'passed':not cube_events and not pair_events and settled is not None and settled<3.}
    path=HERE.parent/'qa/05_independent_bake_geometry_audit.json';path.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(result,ensure_ascii=False,indent=2));return result

if __name__=='__main__':audit()
