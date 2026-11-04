"""V5 촬영 전용 12초 연속 동작. 원본 USD/운영 제어를 변경하지 않는다.

USD joint frame FK와 원본 과실 메시/실제 레인 평면을 사용한 결정적 기하 베이크.
물리 엔진의 접촉 동역학 검증이나 실제 자율 하역 성공 기록은 아니다.
"""
from __future__ import annotations
import copy
import itertools
import json
import math
from pathlib import Path
import numpy as np
from scipy.spatial import ConvexHull
from scipy.spatial.transform import Rotation
from scipy.optimize import least_squares, linprog


HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[3]
V3=ROOT/'sim/runs/presentation_video_revision_v3_20261104/settings'
V4=ROOT/'sim/runs/presentation_video_revision_v4_20261104/settings'
FPS=30
DT=1/240
FRONT=.72
TRAVEL=.23

def read(p: Path) -> dict:
    return json.loads(p.read_text())

def write(name: str, obj: object) -> None:
    (HERE/name).write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n')

def pose(p: list, yaw: float=0.) -> np.ndarray:
    t=np.eye(4);t[:3,:3]=Rotation.from_euler('z',yaw).as_matrix();t[:3,3]=p
    return t

def smooth(t: float, start: float, end: float) -> float:
    u=float(np.clip((t-start)/(end-start),0,1));return u*u*(3-2*u)

def plan_routes(clones: list[dict], cargo: list[np.ndarray]) -> dict:
    """최종 적재 Y에 가까운 혼합 3+4 묶음과 낮은 앞쪽 우선 배출 순서를 고른다."""
    best = None
    count = len(clones)
    for three in itertools.combinations(range(count), 3):
        groups = {'B': list(three), 'C': [i for i in range(count) if i not in three]}
        if any(len({clones[i]['color'] for i in group}) < 2 for group in groups.values()):
            continue
        cost = sum((cargo[i][1,3] - (-.0625 if lane=='B' else .0625))**2
                   for lane, group in groups.items() for i in group)
        if best is None or cost < best[0]:
            best = (cost, groups)
    assert best is not None
    plan = {}
    for lane, group in best[1].items():
        order = sorted(group, key=lambda i: (round(cargo[i][2,3]/.055), -cargo[i][0,3]))
        xs = [.315, .420, .515, .610] if len(group)==4 else [.315, .425, .535]
        times = [3.02, 3.43, 3.79, 4.10] if len(group)==4 else [3.09, 3.43, 3.96]
        for rank, i in enumerate(order):
            plan[i] = dict(id=clones[i]['path'], color=clones[i]['color'], lane=lane,
                slot_x_m=xs[rank], release_time_s=times[rank], rank=rank,
                initial_cargo_xyz_m=cargo[i][:3,3].tolist(),
                method='새 7개 적재의 Y 최단 분리·색 혼합 제약, 낮은 층/앞쪽 우선')
    return plan

def joint_data(role: str) -> tuple[dict, dict]:
    data = read(HERE / '06_07_source_joint_geometry.json')[role]
    for joint in data.values():
        joint['f0'] = np.asarray(joint['f0']); joint['f1'] = np.asarray(joint['f1'])
    geometry = read(HERE.parent / 'qa/06_07_actual_robot_cubes.json')[role]
    initial = {p: np.asarray(m) for p, m in geometry['initial_links'].items()}
    return data, initial


def fk(data: dict, initial: dict, link: str, q: dict) -> np.ndarray:
    by_child={j['b']:(name,j) for name,j in data.items()}
    def recur(path):
        if path not in by_child:return initial[path].copy()
        name,j=by_child[path];d=np.eye(4);value=q.get(name,0.)
        if j['kind']=='PhysicsRevoluteJoint':d[:3,:3]=Rotation.from_rotvec(np.eye(3)[j['axis']]*value).as_matrix()
        elif j['kind']=='PhysicsPrismaticJoint':d[j['axis'],3]=value
        return recur(j['a'])@j['f0']@d@np.linalg.inv(j['f1'])
    return recur(link)

def main() -> None:
    continuity=read(HERE/'handoff_continuity_state.json')
    clones=continuity['clones'];ids=[c['path'] for c in clones]
    assert len(ids)==7 and sum(c['color']=='red' for c in clones)==4 and sum(c['color']=='yellow' for c in clones)==3
    count=len(ids)
    meshes={d['source']:d for d in read(V3/'handoff_mesh_points.json')}
    scales=[np.asarray(c['scale']) for c in clones]
    points=[];full_points=[]
    for c,s in zip(clones,scales):
        p=np.asarray(meshes[c['source']]['root_local_points'])*s
        full_points.append(p)
        points.append(p[ConvexHull(p).vertices])
    cargo_initial=[np.asarray(c['final_cargo_matrix']) for c in clones]
    initial_R=[p[:3,:3]/s for p,s in zip(cargo_initial,scales)]
    radii=[float((np.ptp(p[:,0])+np.ptp(p[:,2]))/4) for p in points]
    cfg=read(ROOT/'sim/vendor/hcr3a_20261008/HCR3A_SIM_TEAM_20261008/workspace/src/smartfarm_description/config/hcr3a_random8_validation.json')
    intake=cfg['intake'];run=math.sqrt(intake['slope_length']**2-intake['rise']**2)
    slope=intake['rise']/run;high=intake['low_x']+run
    correction=intake['board']/2*(math.sqrt(1+slope*slope)-1)
    plane=lambda x: cfg['base_z']+(x-intake['low_x'])*slope+correction
    def intake_surface(x):
        z=plane(x)
        for center in (intake['low_x']+.10,high-.02):
            height=max(.015,cfg['base_z']+(center-intake['low_x'])*slope-.003)
            z=np.where(abs(x-center)<=.0125,np.maximum(z,height),z)
        return z
    scene=read(HERE/'06_07_scene.json')
    candidate={'base':copy.deepcopy(read(V4/'06_07_transport_sorting.json')['base'])}
    candidate['base']['placements']={p:v for p,v in candidate['base']['placements'].items() if not p.startswith('/World/PresentationFruits/')}
    for field,value in scene['base'].items():
        if field=='placements': candidate['base'][field].update(value)
        else: candidate['base'][field]=copy.deepcopy(value)
    T=np.asarray(candidate['base']['placements']['/World/HCRStation']['matrix'])
    Rz=Rotation.from_euler('z',math.pi).as_matrix()
    transport_data,transport_initial=joint_data('transport')
    arm_data,arm_initial=joint_data('arm')
    cargo_link=transport_data['box_tilt_joint']['b']
    tcp_link=arm_data['tcp_mount']['b']
    arm_mount=pose([0,0,cfg['base_z']])
    arm_names=[f'joint{i+1}' for i in range(6)]
    lower=np.array([math.radians(arm_data[n]['lower']) for n in arm_names]);upper=-lower
    def arm_fk(q):return arm_mount@fk(arm_data,arm_initial,tcp_link,dict(zip(arm_names,q)))
    def ik(point,seed,orientation):
        def residual(q):
            p=arm_fk(q);return np.r_[p[:3,3]-point,.15*Rotation.from_matrix(orientation@p[:3,:3].T).as_rotvec()]
        seed_fit=seed.copy()
        for j in (0,3,4,5):seed_fit[j]=(seed_fit[j]+math.pi)%(2*math.pi)-math.pi
        fit=least_squares(residual,np.clip(seed_fit,lower+1e-7,upper-1e-7),bounds=(lower,upper),max_nfev=250,ftol=1e-10,xtol=1e-10,gtol=1e-10)
        err=float(np.linalg.norm(residual(fit.x)))
        if err>.002:raise ValueError(f'USD FK IK unreachable {point}: {err}')
        q=fit.x.copy()
        for j in (0,3,4,5):
            values=[q[j]+k*2*math.pi for k in range(-2,3) if lower[j]<=q[j]+k*2*math.pi<=upper[j]]
            q[j]=min(values,key=lambda x:abs(x-seed[j]))
        return q,err
    def mechanism(t):
        x=FRONT+TRAVEL*(1-smooth(t,1.,1.8))
        gate=math.pi/2*smooth(t,1.8,2.3)*(1-smooth(t,5.15,5.6))
        tilt=math.pi/4*smooth(t,2.3,3.2)*(1-smooth(t,4.6,5.15))
        q=dict(top_lid_left_joint=0.,top_lid_right_joint=0.,lid_pinion_joint=0.,side_lid_joint=gate,box_tilt_joint=tilt,
               wheel_left_joint=(FRONT+TRAVEL-x)/.033,wheel_right_joint=(FRONT+TRAVEL-x)/.033)
        base=pose([x+.086,0,0],math.pi)
        cargo=base@fk(transport_data,transport_initial,cargo_link,q)
        return q,base,cargo
    # 새 인계의 7개 적재 위치·색상으로 두 레인과 배출 순서를 매번 구성한다.
    plan = plan_routes(clones, cargo_initial)
    lane_by_i = {int(i): v['lane'] for i, v in plan.items()}
    slots = {int(i): v['slot_x_m'] for i, v in plan.items()}
    release = {int(i): v['release_time_s'] for i, v in plan.items()}
    start = {i: release[i]-.64 for i in range(count)}
    end_slide={};end_rotation={};final_lane={};dump_frames=[]
    positions=np.array([p[:3,3] for p in cargo_initial]);vertical_speed=np.zeros(count)
    previous_world=[None]*count
    lid_excess_events=[];max_lid_excess=0.
    def support(i,x,y,R):
        cloud=full_points[i]@R.T
        return float(np.max(intake_surface(x+cloud[:,0])-cloud[:,2]))+.0011
    for step in range(12*240+1):
        t=step*DT;q,base,cargo=mechanism(t);world=[];phases=[]
        # cargo 좌표계의 실제 바닥/닫힌 뚜껑, 앞문 및 아래 과실을 보존한다.
        cargo_clouds={}
        for i in sorted(range(count),key=lambda k:cargo_initial[k][2,3]):
            if t>=release[i]:continue
            initial=cargo_initial[i][:3,3];u=smooth(t,start[i],release[i])
            positions[i,0]=initial[0]+(.075-initial[0])*u
            target_y=.0625 if lane_by_i[i]=='C' else -.0625
            # 뒤쪽 과실은 옆 이웃보다 먼저 앞쪽 여유로 나온 뒤 레인 방향으로 정렬한다.
            lateral_start=start[i]+(.15 if initial[0]<-.15 else 0.)
            lateral_end=start[i]+(.40 if initial[0]<-.15 else .38)
            lateral_u=smooth(t,lateral_start,lateral_end)
            positions[i,1]=initial[1]+(target_y-initial[1])*lateral_u
            if abs(initial[1])<.03 and initial[0]>-.15:
                # 중앙 앞 과실은 양쪽 이웃 사이를 먼저 벌리고 앞 여유에서 정렬한다.
                middle_y=.015 if target_y>0 else -.015
                positions[i,1]=initial[1]+(middle_y-initial[1])*smooth(t,start[i],start[i]+.14)
                positions[i,1]+=(target_y-middle_y)*smooth(t,start[i]+.24,start[i]+.29)
            cloud=points[i]@initial_R[i].T
            # V5 Bullet 안착은 전부 바닥 1층이다. AABB가 겹친다는 이유로
            # 옆에 누운 이웃을 상층 지지대로 취급해 위로 밀어 올리지 않는다.
            positions[i,2]=initial[2]
            full_cloud=full_points[i]@initial_R[i].T
            edge=intake['board']/2*math.sin(math.atan(slope))
            for _ in range(4):
                trial=(cargo[:3,:3]@(full_cloud+positions[i]).T).T+cargo[:3,3]
                active=(trial[:,0]>=intake['low_x']-edge)&(trial[:,0]<=high+edge)&(abs(trial[:,1])<intake['width']/2)
                if not active.any():break
                lift=float(np.max(intake_surface(trial[active,0])-trial[active,2]))+.0011
                if lift<=0:break
                positions[i,2]+=lift/max(.3,cargo[2,2])
            cargo_clouds[i]=cloud+positions[i]
            inside=cloud[:,0]+positions[i,0]<=0
            if inside.any():
                excess=float((cloud[inside,2]+positions[i,2]-.190).max())
                if excess>max_lid_excess:lid_excess_events.append([t,i,excess,positions[i].tolist()])
                max_lid_excess=max(max_lid_excess,excess)
            m=np.eye(4);m[:3,:3]=initial_R[i]*scales[i];m[:3,3]=positions[i]
            p=cargo@m;previous_world[i]=p
        for i in range(count):
            if t<release[i]:
                p=previous_world[i].copy();phase='cargo_hold' if t<=start[i] else 'cargo_slide_contact'
            else:
                if i not in end_slide:
                    p=previous_world[i].copy();end_slide[i]=p[:3,3].copy();end_rotation[i]=p[:3,:3]/scales[i]
                    end_slide[i][1]=.0625 if lane_by_i[i]=='B' else -.0625
                age=t-release[i];duration=.73
                u=float(np.clip(age/duration,0,1));distance=(end_slide[i][0]-slots[i])*(2*u-u*u)
                x=end_slide[i][0]-distance;y=end_slide[i][1]
                surface_distance=distance*math.sqrt(1+slope*slope)
                R=Rotation.from_rotvec([0,-surface_distance/radii[i],0]).as_matrix()@end_rotation[i]
                z=support(i,x,y,R)
                # 위층은 첫 접촉까지 중력으로 내려오고 바닥층은 경사면 접촉으로 연결된다.
                ballistic=end_slide[i][2]-.5*9.81*age*age
                if ballistic>z:
                    z=ballistic;phase='short_gravity_fall'
                else:phase='intake_roll' if u<1 else 'lane_stable'
                p=np.eye(4);p[:3,:3]=R*scales[i];p[:3,3]=[x,y,z]
                if u>=1:final_lane[i]=p.copy()
            world.append(p);phases.append(phase)
        if step%8==0:
            dump_frames.append({'time':t,'joints':q,'base':base,'poses':world,'phases':phases})
    assert len(final_lane)==count
    # 팔은 비어 있는 HOME에서 실제 USD TCP를 레인 과실로 내려 보낸다.
    down=Rotation.from_euler('y',math.pi/2).as_matrix()
    midway=Rotation.from_euler('y',3*math.pi/4).as_matrix()
    outward=Rotation.from_euler('y',math.radians(160)).as_matrix()
    qhome=np.asarray(read(ROOT/'sim/runs/presentation_video_revision_v3_20261104/sorting_poses.json')['HOME']['q'])
    red_i=min((i for i,c in enumerate(clones) if c['color']=='red'),key=lambda i:slots[i])
    yellow_i=min((i for i,c in enumerate(clones) if c['color']=='yellow'),key=lambda i:slots[i])
    key=[(0.,qhome,.01),(4.4,qhome,.01)];seed=qhome;ik_errors=[]
    grasp_plan={g['id']:g for g in read(HERE/'06_07_grasp_plan.json')}
    rg=grasp_plan[ids[red_i]];yg=grasp_plan[ids[yellow_i]]
    red=final_lane[red_i][:3,3].copy()+np.asarray(rg['center_offset_m'])
    yellow=final_lane[yellow_i][:3,3].copy()+np.asarray(yg['center_offset_m'])
    rd=np.asarray(rg['rotation']);yd=np.asarray(yg['rotation']);rj=rg['jaw_m'];yj=yg['jaw_m']
    # 과실 중심까지 집게를 내리고 닫은 뒤에만 같은 과실을 TCP에 고정한다.
    goals=[(5.0,red+[0,0,.13],rd,.01),(5.40,red+[0,0,.04],rd,.01),(5.50,red,rd,.01),(5.60,red,rd,rj),
           (5.68,red+[0,0,.06],rd,rj),(5.83,red+[0,0,.22],rd,rj),(6.02,[-.1,.1175,.70],midway,rj),
           (6.12,[-.1,.1175,.82],outward,rj),(6.35,[-.40,.1175,.82],outward,rj),
           (6.43,[-.40,.1175,.82],outward,.01),(6.56,[-.40,.1175,.82],outward,.01),(6.80,[-.1,.1175,.82],outward,.01),
           (7.08,yellow+[0,0,.13],yd,.01),(7.28,yellow,yd,.01),(7.38,yellow,yd,yj),
           (7.60,yellow+[0,0,.22],yd,yj),(7.78,[-.1,-.1175,.70],midway,yj),
           (7.88,[-.1,-.1175,.82],outward,yj),(8.08,[-.40,-.1175,.82],outward,yj),
           (8.16,[-.40,-.1175,.82],outward,.01),(8.29,[-.40,-.1175,.82],outward,.01),(8.53,[-.1,-.1175,.82],outward,.01),
           (8.88,[.10,0,.50],down,.01),(12.,[.10,0,.50],down,.01)]
    for t,p,R,jaw in goals:
        seed,err=ik(np.asarray(p),seed,R);ik_errors.append({'time_s':t,'residual':err});key.append((t,seed.copy(),jaw))
    def arm_state(t):
        for a,b in zip(key,key[1:]):
            if t<=b[0]:
                u=smooth(t,a[0],b[0]);return a[1]*(1-u)+b[1]*u,a[2]*(1-u)+b[2]*u
        return key[-1][1],key[-1][2]
    picks=[dict(i=red_i,attach=5.60,release=6.43,color='red'),dict(i=yellow_i,attach=7.38,release=8.16,color='yellow')]
    for p in picks:
        a,_=arm_state(p['attach']);p['relative']=np.linalg.inv(arm_fk(a))@final_lane[p['i']]
        a,_=arm_state(p['release']);p['release_pose']=arm_fk(a)@p['relative']
    storage=cfg['storage'];srun=math.sqrt(storage['ramp_length']**2-storage['ramp_rise']**2);slow=storage['drop_x']-srun
    angle=math.asin(storage['ramp_rise']/storage['ramp_length']);sz=storage['drop_z']-storage['ramp_rise']
    def storage_z(x):return np.where(x>=slow,storage['drop_z']+(x-storage['drop_x'])*math.tan(angle)+.0025/math.cos(angle)-.0025,sz)
    def sorted_pose(p,t):
        i=p['i'];m=p['release_pose'].copy();R0=m[:3,:3]/scales[i];start=m[:3,3].copy();age=t-p['release']
        def zsupport(x,R):
            cloud=points[i]@R.T;return float(np.max(storage_z(x+cloud[:,0])-cloud[:,2]))+.0007
        lo,hi=0.,.5
        for _ in range(40):
            f=(lo+hi)/2
            if start[2]-.5*9.81*f*f>zsupport(start[0],R0):lo=f
            else:hi=f
        fall=(lo+hi)/2
        if age<fall:m[2,3]-=.5*9.81*age*age;return m,'bin_gravity_fall'
        u=float(np.clip((age-fall)/.54,0,1));distance=(start[0]-slow+.105)*(2*u-u*u)
        ramp_distance=min(distance,start[0]-slow)/math.cos(angle)
        flat_distance=max(0.,distance-(start[0]-slow))
        x=start[0]-distance;R=Rotation.from_rotvec([0,-(ramp_distance+flat_distance)/radii[i],0]).as_matrix()@R0
        m[:3,:3]=R*scales[i];m[:3,3]=[x,start[1],zsupport(x,R)]
        return m,'bin_roll' if u<1 else 'bin_stable'
    request=copy.deepcopy(candidate)
    request.update(name='06_07_transport_sorting',fps=30,duration_s=12,easing='linear',preview_only=True,
                   reset_renderer_accumulation=True,render_settle_frames=24,
                   preview_frames=[0,54,69,99,126,138,165,168,193,219,222,245,270,329,359],preview_warmup_frames=48)
    base=request['base'];base['attach_fruits']=[];base['fruit_positions']={}
    base['show']=list(dict.fromkeys(base.get('show',[])+ids))
    base['hide']=[p for p in base.get('hide',[]) if p not in ids]
    assert not any('/Vegetation' in p or '/farm_frame' in p for p in base['hide'])
    base['inspect']=ids+['/World/transport_robot/cargo_box','/World/transport_robot/side_lid','/World/HCRRobot/tcp']
    frames=[];ledger=[]
    for n,dump in enumerate(dump_frames):
        t=dump['time'];q,jaw=arm_state(t);joints=dict(dump['joints'],**dict(zip(arm_names,q.tolist())),left_jaw=jaw,right_jaw=jaw)
        poses={};states={};attached=[]
        for i,id_ in enumerate(ids):
            p=dump['poses'][i].copy();phase=dump['phases'][i];location='cargo' if t<release[i] else 'lane'
            pick=next((p for p in picks if p['i']==i),None)
            if pick and t>=pick['attach']:
                if t<pick['release']:
                    p=arm_fk(q)@pick['relative'];location='gripper';phase='gripper_attached'
                    attached.append({'fruit':id_,'link':'/World/HCRRobot/tcp','matrix':pick['relative'].tolist()})
                else:p,phase=sorted_pose(pick,t);location='bin'
            world=T@p;poses[id_]={'matrix':world.tolist()}
            states[id_]=dict(location=location,phase=phase,lane=lane_by_i[i],station_local_matrix=p.tolist(),world_matrix=world.tolist())
        root_world=T@dump['base'];poses['/World/transport_robot']={'matrix':root_world.tolist()}
        state={'joints':joints,'placements':poses,'attach_fruits':attached}
        frames.append(dict(time=t,state=state));ledger.append(dict(frame=n,time_s=t,mechanism=dump['joints'],fruit_states=states))
    request['keyframes']=frames
    base['placements'].update(frames[0]['state']['placements']);base['joints'].update(frames[0]['state']['joints'])
    request['provenance']=dict(scope='Deterministic staged GUI animation, not physical/autonomous success',
        continuity='handoff_continuity_state.json',motion_evidence='06_07_motion_evidence.json',
        kinematics='Original USD joint axes/frame/limits; manual FK, SI units',station_local_front_pivot_m=FRONT,
        same_seven_fruits=True,all_top_lids_closed=True,physical_limit='Mesh-supported kinematic contact; no rigid-body contact solver validation')
    write('06_07_transport_sorting.json',request)
    evidence=dict(scope='Geometry bake, not dynamic/ROS proof',fruits=[dict(id=c['path'],source=c['source'],color=c['color'],scale=c['scale']) for c in clones],
        route_plan=plan,
        mechanism=dict(gate_open_start_s=1.8,gate_open_end_s=2.3,tilt_start_s=2.3,tilt_max_s=3.2,tilt_restore_start_s=4.6,tilt_restore_end_s=5.15,gate_close_start_s=5.15,gate_close_end_s=5.6),
        groups={l:[ids[i] for i in range(count) if lane_by_i[i]==l] for l in ('B','C')},
        picks=[dict(id=ids[p['i']],color=p['color'],attach_time_s=p['attach'],release_time_s=p['release'],bin=p['color']) for p in picks],
        station_transform=T.tolist(),cargo_initial_relative_matrices={ids[i]:cargo_initial[i].tolist() for i in range(count)},
        geometry=dict(intake_high_x_m=high,intake_plane_slope=slope,intake_plane_top_correction=correction,front_pivot_m=FRONT,
            cargo_floor_top_m=.258,cargo_lid_bottom_local_m=.190,upper_lid_max_excess_m=max_lid_excess,
            rollout_target_x_m={ids[i]:slots[i] for i in range(count)},rolling_radii_m=dict(zip(ids,radii))),
        qa=dict(ik_residuals=ik_errors,contact_model='rotated original mesh support on cargo floor/closed lid and intake/storage surfaces',
            full_collision_validation='See ../qa/06_07_independent_geometry_audit.json (discrete mesh scope)',
            gui_visual_validation='See ../qa/06_07_transport_sorting-mp4-review.json',hold_interval_s=[9,12]),frames=ledger)
    # 렌더 시점의 실제 회전된 메시 볼록체를 검사한다. AABB 겹침만으로 충돌을 판정하지 않는다.
    pair_candidates=0;pair_overlaps=[];lane_clearance=1.;intake_gap=1.;hold_delta=0.;bin_stable={}
    for frame in ledger:
        clouds=[]
        for i,id_ in enumerate(ids):
            item=frame['fruit_states'][id_];m=np.asarray(item['station_local_matrix'])
            cloud=points[i]@(m[:3,:3]/scales[i]).T+m[:3,3];clouds.append(cloud)
            if item['phase'] in ('intake_roll','lane_stable'):
                center=.0625 if lane_by_i[i]=='B' else -.0625
                lane_clearance=min(lane_clearance,float(.06-np.abs(cloud[:,1]-center).max()))
                intake_gap=min(intake_gap,float((cloud[:,2]-plane(cloud[:,0])).min()))
            if frame['frame']>=270:
                hold_delta=max(hold_delta,float(np.abs(m-np.asarray(ledger[270]['fruit_states'][id_]['station_local_matrix'])).max()))
            if item['phase']=='bin_stable' and id_ not in bin_stable:bin_stable[id_]=frame['time_s']
        for i in range(count):
            for j in range(i+1,count):
                overlap=np.minimum(clouds[i].max(0),clouds[j].max(0))-np.maximum(clouds[i].min(0),clouds[j].min(0))
                if not np.all(overlap>0):continue
                pair_candidates+=1
                eq=np.vstack((ConvexHull(clouds[i]).equations,ConvexHull(clouds[j]).equations))
                fit=linprog([0,0,0,-1],A_ub=np.c_[eq[:,:3],np.ones(len(eq))],b_ub=-eq[:,3],bounds=[(None,None)]*4,method='highs')
                if fit.success and fit.x[-1]>1e-6:
                    pair_overlaps.append(dict(frame=frame['frame'],ids=[ids[i],ids[j]],interior_radius_m=float(fit.x[-1])))
    audit=dict(method='30fps rotated original-mesh convex hull halfspace intersection; maximum common interior sphere',
        rendered_frames=360,keyframes_including_terminal=361,aabb_candidates=pair_candidates,positive_overlaps=pair_overlaps,
        min_lane_side_clearance_m=lane_clearance,min_intake_support_gap_m=intake_gap,hold_max_matrix_delta=hold_delta,
        first_bin_stable_s=bin_stable,scope_limit='Fruit pair/plane check only; equipment/arm mesh and GUI review separate')
    evidence['qa']['fruit_geometry_audit']=audit
    audit['passed']=not pair_overlaps and lane_clearance>0 and intake_gap>=0 and hold_delta<1e-9 and max_lid_excess<1e-6
    write('06_07_convex_fruit_audit.json',audit)
    evidence['qa']['lid_excess_events']=lid_excess_events
    write('06_07_motion_evidence.json',evidence)
    serial=lambda d:{n:{k:(v.tolist() if isinstance(v,np.ndarray) else v) for k,v in j.items()} for n,j in d.items()}
    write('06_07_source_joint_geometry.json',dict(transport=serial(transport_data),arm=serial(arm_data),
         note='USD angular joint limits are degrees; animation values are radians. Transport lid zero locks are preserved.'))
    assert audit['passed'], json.dumps(dict(pair_overlaps=len(pair_overlaps),lane_clearance_m=lane_clearance,
        intake_gap_m=intake_gap,hold_delta=hold_delta,lid_excess_m=max_lid_excess))
    print(json.dumps({'frames':len(frames),'max_lid_excess_m':max_lid_excess,'max_ik_residual':max(x['residual'] for x in ik_errors),'ready_for_preview':True}))

if __name__=='__main__':main()
