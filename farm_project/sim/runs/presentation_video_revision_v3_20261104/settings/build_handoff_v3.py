"""발표 V3 04/05/06 재현 설정. 운영 제어와 무관한 세션 애니메이션이다."""
from __future__ import annotations
import copy
import json
import math
from pathlib import Path
import sys
import numpy as np
from scipy.spatial.transform import Rotation
from scipy.spatial import ConvexHull

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(ROOT / 'sim/tools'))
from presentation_video_frames import state_at
from presentation_scene_v3 import HANDOFF_SOURCES

FPS = 30
SEED = 20261104
CLONES = [f'/World/PresentationFruits/Handoff_{i:02d}' for i in range(1, 8)]
MESHES = {x['source']: x for x in json.loads((HERE / 'handoff_mesh_points.json').read_text())}
FLOOR_Z = .506000022
LOWER_FLOOR_Z = .257999995

def write(name: str, data: dict) -> None:
    (HERE / name).write_text(json.dumps(data, indent=2, ensure_ascii=False) + '\n')

def mat(xyz: list, yaw: float = 0.) -> np.ndarray:
    out = np.eye(4)
    out[:3, :3] = Rotation.from_euler('z', yaw).as_matrix()
    out[:3, 3] = xyz
    return out

def mesh_points(source: str) -> np.ndarray:
    return np.asarray(MESHES[source]['root_local_points'], float)

def clean(request: dict) -> dict:
    for state in [request['base'], *[x['state'] for x in request['keyframes']]]:
        if 'hide' in state:
            state['hide'] = [p for p in state['hide'] if not p.startswith(('/World/farm_framechanged', '/World/AprilTags'))]
    request['preview_only'] = True
    request['preview_warmup_frames'] = 48
    request['preview_frames'] = [0, int(request['duration_s'] * FPS / 2), int(request['duration_s'] * FPS) - 1]
    return request

def build_deposit() -> dict:
    source = ROOT / 'sim/runs/presentation_video_retake_20261104/settings/candidates/04_deposit_a_refined.json'
    old = json.loads(source.read_text())
    req = clean(copy.deepcopy(old)); req['name'] = '04_deposit'
    fruit = '/World/Vegetation/Bed_02/Fruits/Pepper_0003_red'
    release_t = 3.15
    release = np.asarray(state_at(old, release_t)['placements'][fruit]['matrix'])
    offsets = mesh_points(fruit) @ release[:3, :3].T
    resting_z = FLOOR_Z - offsets[:, 2].min()
    impact_t = release_t + math.sqrt(2 * (release[2, 3] - resting_z) / 9.81)
    req['base']['joints'].update(box_bottom_left_joint=0., box_bottom_right_joint=0., harvest_lid_pinion_joint=0.)
    req['easing'] = 'linear'
    frames = []
    for t in sorted(set([i / FPS for i in range(151)] + [release_t, impact_t])):
        current = state_at(old, t)
        patch = {'joints': current['joints']}
        if t >= release_t:
            pose = release.copy()
            age = t - release_t
            pose[2, 3] = max(resting_z, release[2, 3] - .5 * 9.81 * age * age)
            patch.update(attach_fruits=[], placements={fruit: {'matrix': pose.tolist()}})
        frames.append({'time': t, 'state': patch})
    req['keyframes'] = frames
    req['preview_frames'] = [0, 75, 99, 103, 149]
    req['provenance'] = {'scope': '촬영 세션 애니메이션, 자율 시험 결과 아님', 'source': str(source.relative_to(ROOT)),
        '03_to_04_grip_and_joint_continuity': 'unchanged', 'camera_pitch_deg': 44,
        'floor_top_z_m': FLOOR_Z, 'fruit_rest_root_z_m': float(resting_z),
        'actual_mesh_bottom_at_rest_m': float(resting_z + offsets[:, 2].min()),
        'release_time_s': release_t, 'impact_time_s': impact_t,
        'drop': '9.81 m/s² ballistic, per-render-frame bake; actual mesh lowest vertex on restored floor',
        'limits': '낙하 메시-바닥 최저점 검증. 전체 팔/과실 충돌 물리 시험 아님.'}
    write('04_deposit.json', req)
    return req

def bake_handoff() -> tuple[list, dict]:
    """240 Hz 중력/보수적 회전 AABB 접촉 계산을 렌더 프레임으로 베이크한다."""
    rng = np.random.default_rng(SEED)
    points = []; centers = []; scales = []; rotations = []
    for i, source in enumerate(HANDOFF_SOURCES):
        scale = np.asarray(MESHES[source]['scale'])
        scaled = mesh_points(source) * scale
        center = (scaled.min(0) + scaled.max(0)) * .5
        hull = ConvexHull(scaled)
        points.append(scaled[hull.vertices] - center)
        centers.append(center); scales.append(scale)
        rotations.append(Rotation.from_euler('xyz', [.025 * (-1)**i, .02 * ((i % 3)-1), .05 * (i-3)]))
    xy = np.array([[-.016,-.045],[.056,-.045],[-.016,.045],[.056,.045],[-.027,-.032],[.045,-.032],[-.016,.045]])
    position = np.zeros((7, 3)); position[:, :2] = xy
    velocity = np.zeros((7, 3)); omega = rng.uniform(-.55, .55, (7,3))
    motion = []; first_release = [None] * 7; first_contact = [None] * 7
    def extents() -> tuple[np.ndarray, np.ndarray]:
        cloud = [p @ r.as_matrix().T for p, r in zip(points, rotations)]
        return np.array([p.min(0) for p in cloud]), np.array([p.max(0) for p in cloud])
    lo, hi = extents()
    position[:4, 2] = FLOOR_Z - lo[:4, 2]
    for i in range(4, 7):
        overlaps = [j for j in range(i) if np.all(position[i,:2]+hi[i,:2] > position[j,:2]+lo[j,:2]) and np.all(position[i,:2]+lo[i,:2] < position[j,:2]+hi[j,:2])]
        position[i,2] = max(position[j,2]+hi[j,2] for j in overlaps) - lo[i,2] + .0002
    initial = position.copy()
    dt = 1/240
    min_pair_overlap = 0.; max_wall_excess = 0.
    side_impulse = np.array([[-.075,-.055],[.075,-.055],[-.065,.05],[.07,.06],[-.13,-.025],[.13,-.02],[0.,.14]])
    max_omega = 0.
    def record(t: float, gap: float) -> dict:
        poses = {}
        for i, path in enumerate(CLONES):
            R = rotations[i].as_matrix(); f = np.eye(4)
            f[:3,:3] = R * scales[i]
            f[:3,3] = position[i] + np.array([-6.,3.65,0.]) - R @ centers[i]
            poses[path] = {'matrix': f.tolist()}
        return {'time': float(t), 'state': {'placements': poses,
            'joints': {'box_bottom_left_joint': float(gap), 'box_bottom_right_joint': float(gap), 'harvest_lid_pinion_joint': float(gap * 23.8095238095)}}}
    motion.append(record(0.,0.))
    for step in range(1, 1201):
        t = step * dt
        u = np.clip((t-1.)/.65, 0., 1.); gap = .105 * u*u*(3-2*u)
        if t <= 1.:
            if step % 8 == 0: motion.append(record(t,gap))
            continue
        previous = position.copy()
        velocity[:,2] -= 9.81 * dt
        position += velocity * dt
        for i in range(7):
            if first_release[i] is not None:
                rotations[i] = Rotation.from_rotvec(omega[i] * dt) * rotations[i]
        lo, hi = extents()
        for iteration in range(10):
            for i in range(7):
                bottom, top = position[i,2]+lo[i,2], position[i,2]+hi[i,2]
                # 상부 벽이 있는 높이에서는 실제 내부 190 mm 폭을 지킨다.
                if top > FLOOR_Z + .0001:
                    for axis in (0,1):
                        low, high = -.095-lo[i,axis], .095-hi[i,axis]
                        if position[i,axis] < low:
                            position[i,axis] = low; velocity[i,axis] = max(0., velocity[i,axis])
                        if position[i,axis] > high:
                            position[i,axis] = high; velocity[i,axis] = min(0., velocity[i,axis])
                # 양 슬라이드 판의 실제 열린 구멍 [-gap,+gap]을 전부 통과할 때 낙하.
                panel_support = (position[i,0]+lo[i,0] < -gap or position[i,0]+hi[i,0] > gap)
                near_upper_floor = bottom < FLOOR_Z and top > FLOOR_Z - .006 and previous[i,2]+lo[i,2] >= FLOOR_Z-.004
                if panel_support and near_upper_floor:
                    position[i,2] = FLOOR_Z-lo[i,2]; velocity[i,2] = max(0.,velocity[i,2])
                # 하부 운송함의 실제 메시 바닥 및 내측 벽.
                if position[i,2]+lo[i,2] < LOWER_FLOOR_Z:
                    position[i,2] = LOWER_FLOOR_Z-lo[i,2]
                    if velocity[i,2] < -.1:
                        velocity[i,2] *= -.12
                    else: velocity[i,2] = 0.
                    velocity[i,:2] *= .84; omega[i] *= .90
                    if first_contact[i] is None: first_contact[i] = t
                if position[i,2]+lo[i,2] < .445:
                    for axis in (0,1):
                        low, high = -.147-lo[i,axis], .147-hi[i,axis]
                        if position[i,axis] < low:
                            position[i,axis] = low; velocity[i,axis] = abs(velocity[i,axis])*.1
                        if position[i,axis] > high:
                            position[i,axis] = high; velocity[i,axis] = -abs(velocity[i,axis])*.1
            # 회전된 실제 메시의 AABB를 보수적 충돌 외피로 사용한다.
            for i in range(7):
                for j in range(i+1,7):
                    overlap = np.minimum(position[i]+hi[i],position[j]+hi[j])-np.maximum(position[i]+lo[i],position[j]+lo[j])
                    if np.min(overlap) <= 0: continue
                    axis = int(np.argmin(overlap)); depth = overlap[axis]+1e-6
                    direction = 1. if position[i,axis] >= position[j,axis] else -1.
                    position[i,axis] += direction * depth*.5
                    position[j,axis] -= direction * depth*.5
                    approaching = (velocity[i,axis]-velocity[j,axis])*direction
                    if approaching < 0:
                        impulse = -.51 * approaching
                        velocity[i,axis] += direction*impulse
                        velocity[j,axis] -= direction*impulse
                        if axis == 2:
                            omega[i] *= .97; omega[j] *= .97
                    if axis == 2 and abs(velocity[i,2]-velocity[j,2]) < .12:
                        velocity[i,:2] *= .94; velocity[j,:2] *= .94
                        omega[i] *= .99; omega[j] *= .99
            # 적재함 접촉 뒤 회전/수평속도는 마찰로 감쇠한다.
        for i in range(7):
            if first_release[i] is None and position[i,2] < initial[i,2] - .002:
                first_release[i] = t
                velocity[i,:2] += side_impulse[i]
            if first_contact[i] is not None:
                velocity[i,:2] *= math.exp(-1.9*dt); omega[i] *= math.exp(-2.2*dt)
            elif first_release[i] is not None:
                omega[i] *= math.exp(-.15*dt)
        max_omega = max(max_omega,float(np.max(np.linalg.norm(omega,axis=1))))
        if step % 8 == 0: motion.append(record(t,gap))
    # 마지막 1초는 계산된 안착 자세를 고정한다. 별도 순간 위치 변경 없음.
    settled_index = 120
    settled = copy.deepcopy(motion[settled_index]['state'])
    for k in range(settled_index+1,len(motion)): motion[k]['state'] = copy.deepcopy(settled)
    final_matrices = {p: settled['placements'][p]['matrix'] for p in CLONES}
    frame_bounds = []
    for key in motion:
        boxes=[]
        for i,p in enumerate(CLONES):
            f = np.asarray(key['state']['placements'][p]['matrix']); world = mesh_points(HANDOFF_SOURCES[i]) @ f[:3,:3].T + f[:3,3]
            boxes.append([world.min(0),world.max(0)])
        frame_bounds.append(boxes)
    max_pair_intersection = 0.
    for boxes in frame_bounds:
        for i in range(7):
            for j in range(i+1,7):
                overlap = np.minimum(boxes[i][1],boxes[j][1])-np.maximum(boxes[i][0],boxes[j][0])
                if np.min(overlap)>0:max_pair_intersection=max(max_pair_intersection,float(np.min(overlap)))
    evidence = {'seed': SEED, 'gravity_m_s2':9.81, 'solver_hz':240, 'render_fps':30,
        'method':'Per-frame baked conservative rotating-mesh AABB contacts, finite sliding panels, gravity, 0.12 floor restitution, friction damping. Not PhysX or operational test.',
        'floor_top_z_m':FLOOR_Z,'lower_floor_z_m':LOWER_FLOOR_Z,
        'floor_asset':'sim/assets/robots/harvest_physics/box_floor_v3.usd',
        'floor_motion':'existing box_bottom_left/right_joint 0..0.105 m over 0.65 s, actual USD world directions +X/-X',
        'first_release_s':first_release,'first_lower_floor_contact_s':first_contact,
        'maximum_baked_pair_AABB_overlap_depth_m':max_pair_intersection,
        'limits':'보수적 메시 AABB 접촉 근사로 과실 실제 표면 간 미세 간격은 가능. 전체 로봇 충돌·실시간 PhysX 검증 아님. GUI 접촉 시점 검수 필요.',
        'clones':[{'path':p,'source':s,'color':s.rsplit('_',1)[-1],'source_scale':scales[i].tolist(),
                   'initial_matrix':motion[0]['state']['placements'][p]['matrix'],'final_matrix':final_matrices[p],
                   'final_actual_mesh_bounds':np.asarray(frame_bounds[-1][i]).tolist()}
                  for i,(p,s) in enumerate(zip(CLONES,HANDOFF_SOURCES))]}
    return motion,evidence

def build_handoff_transport() -> None:
    motion, evidence = bake_handoff()
    old = json.loads((ROOT/'sim/runs/presentation_video_20261104/settings/05_handoff.json').read_text())
    req = clean(old);req['name']='05_handoff';req['easing']='linear'
    base=req['base'];base.pop('fruit_positions',None)
    base['show'] += CLONES
    base['placements']['/World/harvest_robot']={'matrix':mat([-6.,4.,0.]).tolist()}
    base['placements']['/World/transport_robot']={'matrix':mat([-6.,3.714,0.],math.pi/2).tolist()}
    base['placements'].update(motion[0]['state']['placements'])
    base['joints'].update(motion[0]['state']['joints'])
    base['eye']=[-7.05,2.7,1.85];base['target']=[-6.,3.78,.45];base['focal_mm']=25.
    base['fill_intensity']=500
    base['inspect']=[*CLONES,'/World/harvest_robot/box_bottom_left','/World/harvest_robot/box_bottom_right','/World/transport_robot/cargo_box']
    req['keyframes']=motion
    req['preview_frames']=[0,38,43,48,54,60,75,149]
    req['provenance']={'scope':'GUI staged seven-fruit handoff; no autonomous test claim','motion_evidence':'05_motion_evidence.json','same_asset_scales':True,'house_hidden':False}
    write('05_handoff.json',req)
    high = copy.deepcopy(req); high['name'] = '05_handoff_high'
    high['base'].update(eye=[-7.05,2.7,1.85], target=[-6.,3.78,.45], focal_mm=25.)
    write('05_handoff_high.json', high)
    cargo_root=np.asarray(json.loads((HERE/'handoff_asset_geometry.json').read_text())['cargo_box_root_matrix'])
    cargo_world=mat([-6.,3.714,0.],math.pi/2)@cargo_root
    relative={p:(np.linalg.inv(cargo_world)@np.asarray(motion[120]['state']['placements'][p]['matrix'])) for p in CLONES}
    transport=clean(json.loads((ROOT/'sim/runs/presentation_video_20261104/settings/06_transport.json').read_text()))
    transport['base']['show']+=CLONES
    transport['base']['placements'].update(json.loads((HERE/'station_transform.json').read_text())['placements'])
    transport['base']['attach_fruits']=[{'fruit':p,'link':'/World/transport_robot/cargo_box','matrix':relative[p].tolist()} for p in CLONES]
    transport['base']['inspect']=[*CLONES,'/World/transport_robot/cargo_box']
    transport['provenance'].update(cargo_note='05 최종 7개 과실의 cargo_box 상대행렬 그대로 연결. 원본 과실 스케일/색상/자세 보존.',fruit_count=7,station_transform='station_transform.json')
    # GUI 승인된 측면 필름 구도만 재사용한다. 새 05의 적재 상대행렬은 위 계산을 유지한다.
    camera_choice=json.loads((HERE/'06_transport_house.json').read_text())
    for key in ('eye','target','focal_mm'):
        transport['base'][key]=copy.deepcopy(camera_choice['base'][key])
    camera_states={item['time']:item['state'] for item in camera_choice['keyframes']}
    for item in transport['keyframes']:
        for key in ('eye','target'):
            if key in camera_states.get(item['time'],{}):
                item['state'][key]=copy.deepcopy(camera_states[item['time']][key])
    for key in ('framing_revision','camera_revision_v3'):
        transport['provenance'][key]=copy.deepcopy(camera_choice['provenance'][key])
    write('06_transport.json',transport)
    evidence['cargo_world_at_05_end']=cargo_world.tolist()
    evidence['cargo_relative_final_matrices']={p:f.tolist() for p,f in relative.items()}
    evidence['05_to_06_relative_pose_max_error']=max(float(np.max(np.abs(cargo_world@relative[p]-np.asarray(motion[120]['state']['placements'][p]['matrix'])))) for p in CLONES)
    write('05_motion_evidence.json',evidence)

if __name__ == '__main__':
    build_deposit()
    build_handoff_transport()
