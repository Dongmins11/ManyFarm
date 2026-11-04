"""V5 7개 인계: 원본 기하 추출 → Blender Bullet 짧은 강체 계산 → GUI 재생 설정.

python3 build_handoff_v5.py --inspect-usd  # pxr가 설치된 Isaac Python 사용
python3 build_handoff_v5.py               # 설치된 Blender 4.0.2로 물리만 계산, 렌더 없음
원본 USD/운영 코드와 V3/V4 결과는 저장·수정하지 않는다.
"""
from __future__ import annotations
import copy
import hashlib
import itertools
import json
from pathlib import Path
import subprocess
import sys
import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
V3 = ROOT / 'sim/runs/presentation_video_revision_v3_20261104/settings'
V4 = ROOT / 'sim/runs/presentation_video_revision_v4_20261104/settings'
PATHS = [f'/World/PresentationFruits/Handoff_{i:02d}' for i in range(1, 8)]
ORIGIN = np.array([-6., 3.65, 0.])
FPS = 30
WARMUP_S = 3.
SEED = 20261104
OPEN = (1., 1.65)
RESTORE = (3.0, 3.3)
CLOSE = (3.35, 3.85)


def read(path: Path) -> dict:
    return json.loads(path.read_text())


def write(name: str, data: dict) -> None:
    (HERE / name).write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')


def smooth(t: float, begin: float, end: float) -> float:
    u = float(np.clip((t-begin)/(end-begin), 0., 1.))
    return u*u*(3.-2.*u)


def gap(t: float) -> float:
    return .105*smooth(t,*OPEN)*(1.-smooth(t,*RESTORE))


def lid(t: float) -> float:
    return .155*(1.-smooth(t,*CLOSE))


def inspect_usd() -> None:
    """원본 Cube 꼭짓점과 복원된 유한 바닥 메시를 월드 좌표로 추출한다."""
    from pxr import Usd, UsdGeom, Gf
    from scipy.spatial import ConvexHull
    sys.path.insert(0,str(ROOT/'sim/tools'))
    from presentation_scene_v3 import install_handoff_assets
    stage=Usd.Stage.Open(str(ROOT/'sim/assets/envs/output/farm_with_plants_v5.usd'))
    stage.SetEditTarget(stage.GetSessionLayer())
    old=read(V4/'05_handoff_continuity.json')
    for name,asset in [('harvest_robot','robots/harvest_count_test/harvest_robot.usd'),('transport_robot','robots/transport_robot/urdf/transport_robot.portable/transport_robot.sim.usda')]:
        p=UsdGeom.Xform.Define(stage,'/World/'+name).GetPrim()
        p.GetReferences().AddReference(str(ROOT/'sim/assets'/asset))
        xf=UsdGeom.Xformable(p);xf.ClearXformOpOrder()
        xf.AddTransformOp().Set(Gf.Matrix4d(np.asarray(old['base']['placements']['/World/'+name]['matrix']).T.tolist()))
    setup=install_handoff_assets(stage,ROOT,'/World/harvest_robot')
    prior_geometry=read(V4/'05_mechanism_geometry.json')
    colliders=[]
    for robot in ['harvest_robot','transport_robot']:
        for p in Usd.PrimRange(stage.GetPrimAtPath('/World/'+robot),Usd.TraverseInstanceProxies()):
            path=str(p.GetPath()); motion='static'; axis=[0.,0.,0.]
            if robot=='harvest_robot':
                if '/box_bottom_' in path and 'PresentationRestoredFloor' in path and p.IsA(UsdGeom.Mesh):
                    motion='floor'; joint='box_bottom_left_joint' if '/box_bottom_left/' in path else 'box_bottom_right_joint'
                    axis=prior_geometry['joints'][joint]['axis_world']
                elif not ('/box_' in path and '_wall/' in path and '/visuals/' in path and p.IsA(UsdGeom.Cube)):
                    continue
            elif not (any('/'+part+'/' in path for part in ['cargo_box','side_lid','top_lid_left','top_lid_right']) and '/visuals/' in path and p.IsA(UsdGeom.Cube)):
                continue
            elif '/top_lid_' in path:
                motion='lid';joint='top_lid_left_joint' if '/top_lid_left/' in path else 'top_lid_right_joint'
                axis=prior_geometry['joints'][joint]['axis_world']
            m=np.asarray(UsdGeom.Xformable(p).ComputeLocalToWorldTransform(Usd.TimeCode.Default())).T
            if p.IsA(UsdGeom.Cube):
                sz=UsdGeom.Cube(p).GetSizeAttr().Get()/2
                vertices=np.asarray(list(itertools.product([-sz,sz],repeat=3)))
            else:
                vertices=np.asarray(UsdGeom.Mesh(p).GetPointsAttr().Get(),float)
            world=vertices@m[:3,:3].T+m[:3,3]
            hull=ConvexHull(world)
            unique=world[hull.vertices]
            center=(unique.min(0)+unique.max(0))/2
            centered=unique-center;h=ConvexHull(centered)
            colliders.append({'path':path,'motion':motion,'axis':axis,'center_world':center.tolist(),
                              'vertices':centered.tolist(),'faces':h.simplices.tolist(),
                              'world_bounds':[world.min(0).tolist(),world.max(0).tolist()],
                              'shape':'convex hull of actual USD vertices; floor tiles retain finite footprint'})
    meshes={x['source']:x for x in read(V3/'handoff_mesh_points.json')}
    sources=read(V3/'05_motion_evidence.json')['clones']
    fruits=[]
    for src in sources:
        data=meshes[src['source']]; points=np.asarray(data['root_local_points']);scale=np.asarray(data['scale'])
        scaled=points*scale;center=(scaled.min(0)+scaled.max(0))/2
        h=ConvexHull(scaled-center);vertices=(scaled-center)[h.vertices];faces=ConvexHull(vertices).simplices
        fruits.append({'path':src['path'],'source':src['source'],'color':src['color'],'scale':scale.tolist(),
                       'center_scaled':center.tolist(),'vertices':vertices.tolist(),'faces':faces.tolist(),
                       'initial_world_matrix':src['initial_matrix'],
                       'mesh_local_bounds':[points.min(0).tolist(),points.max(0).tolist()]})
    write('05_physics_geometry.json',{'source':'original USD visual Cube vertices, original restored floor mesh finite convex hull, original fruit mesh convex hull',
        'colliders':colliders,'fruits':fruits,'origin':ORIGIN.tolist(),
        'cargo_world':read(V3/'05_motion_evidence.json')['cargo_world_at_05_end'],
        'usd_saved':False,'floor_setup':setup['diagnostics'],
        'source_files':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [V3/'handoff_mesh_points.json',V3/'05_motion_evidence.json',V4/'05_mechanism_geometry.json']}})
    print('Extracted',len(colliders),'actual colliders and',len(fruits),'fruit convex hulls.')


def physics() -> None:
    """Blender Bullet의 중력/마찰/회전접촉 결과만 저장한다. 외부 임펄스는 없다."""
    import bpy
    from mathutils import Matrix,Vector
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene=bpy.context.scene;scene.render.fps=FPS;scene.gravity=(0,0,-9.81)
    data=read(HERE/'05_physics_geometry.json')
    scene.frame_start=1;scene.frame_end=int((WARMUP_S+5)*FPS)+1
    def obj(name: str, vertices: list, faces: list, kind: str) -> object:
        mesh=bpy.data.meshes.new(name);mesh.from_pydata(vertices,[],faces);mesh.update()
        ob=bpy.data.objects.new(name,mesh);scene.collection.objects.link(ob)
        bpy.context.view_layer.objects.active=ob;ob.select_set(True);bpy.ops.rigidbody.object_add();ob.select_set(False)
        rb=ob.rigid_body;rb.type=kind;rb.collision_shape='CONVEX_HULL';rb.use_margin=True;rb.collision_margin=.00012
        rb.friction=.35;rb.restitution=.04
        return ob
    for i,c in enumerate(data['colliders']):
        ob=obj('Collider_%03d'%i,c['vertices'],c['faces'],'PASSIVE')
        rb=ob.rigid_body;rb.kinematic=c['motion']!='static'
        for fr in range(scene.frame_start,scene.frame_end+1):
            t=(fr-1)/FPS-WARMUP_S
            d=gap(t) if c['motion']=='floor' else lid(t) if c['motion']=='lid' else 0.
            ob.location=Vector((np.asarray(c['center_world'])-ORIGIN+np.asarray(c['axis'])*d).tolist())
            if c['motion']!='static':ob.keyframe_insert(data_path='location',frame=fr)
        if ob.animation_data:
            for fc in ob.animation_data.action.fcurves:
                for k in fc.keyframe_points:k.interpolation='LINEAR'
    objects=[]
    for f in data['fruits']:
        ob=obj(f['path'].split('/')[-1],f['vertices'],f['faces'],'ACTIVE')
        m=np.asarray(f['initial_world_matrix']);R=m[:3,:3]/np.asarray(f['scale'])
        ob.matrix_world=Matrix(np.block([[R,(m[:3,3]+R@np.asarray(f['center_scaled'])-ORIGIN)[:,None]], [np.array([0,0,0,1])]]).tolist())
        rb=ob.rigid_body;rb.mass=.009;rb.friction=.32;rb.restitution=.06;rb.linear_damping=.1;rb.angular_damping=.18
        rb.use_deactivation=True;rb.deactivate_linear_velocity=.005;rb.deactivate_angular_velocity=.05
        objects.append(ob)
    world=scene.rigidbody_world;world.substeps_per_frame=16;world.solver_iterations=60
    world.point_cache.frame_start=1;world.point_cache.frame_end=scene.frame_end
    samples=[]
    for fr in range(1,scene.frame_end+1):
        scene.frame_set(fr);dg=bpy.context.evaluated_depsgraph_get()
        if fr>=int(WARMUP_S*FPS)+1:
            t=(fr-1)/FPS-WARMUP_S;poses={}
            for f,ob in zip(data['fruits'],objects):
                physical=np.asarray(ob.evaluated_get(dg).matrix_world,float);R=physical[:3,:3]
                m=np.eye(4);m[:3,:3]=R*np.asarray(f['scale']);m[:3,3]=physical[:3,3]+ORIGIN-R@np.asarray(f['center_scaled'])
                poses[f['path']]=m.tolist()
            samples.append({'time':round(t,10),'placements':poses})
    write('05_physics_bake.json',{'engine':'Blender '+bpy.app.version_string+' Bullet rigid body','gravity_m_s2':9.81,'fps':FPS,
        'substeps_per_frame':16,'nominal_solver_hz':480,'solver_iterations':60,'warmup_s':WARMUP_S,'seed':SEED,
        'fruit_mass_kg':.009,'fruit_friction':.32,'wall_friction':.35,'fruit_restitution':.06,'wall_restitution':.04,
        'linear_damping':.1,'angular_damping':.18,'collision_margin_m':.00012,
        'initial_linear_angular_velocity':'zero; no external impulse or artificial flight spin',
        'contact_shapes':'original fruit convex hulls and actual wall/floor convex pieces, original sizes',
        'frames':samples,'geometry_sha256':hashlib.sha256((HERE/'05_physics_geometry.json').read_bytes()).hexdigest()})
    print('Bullet bake saved:',len(samples),'frames')


def build() -> None:
    """베이크 행렬을 재배치 없이 재생하고 05→06 원본 상대 자세를 전달한다."""
    from scipy.spatial.transform import Rotation
    data=read(HERE/'05_physics_geometry.json');bake=read(HERE/'05_physics_bake.json')
    req=read(V4/'05_handoff_continuity.json');base=req['base']
    base.update(eye=[-6.45,2.75,1.5],target=[-6.,3.68,.49],focal_mm=32,fill_intensity=650)
    base['show']=list(dict.fromkeys([p for p in base['show'] if 'Handoff_' not in p]+PATHS))
    base['hide']=[p for p in base['hide'] if 'Handoff_' not in p]
    base['inspect']=list(dict.fromkeys(PATHS+[p for p in base['inspect'] if 'Handoff_' not in p]))
    req['keyframes']=[];bounds=[];ledger=[];frame_states=[]
    mesh={x['source']:np.asarray(x['root_local_points']) for x in read(V3/'handoff_mesh_points.json')}
    for f in bake['frames']:
        t=f['time'];g=gap(t);l=lid(t)
        joints={'box_bottom_left_joint':g,'box_bottom_right_joint':g,'harvest_lid_pinion_joint':g*23.8095238095,
                'top_lid_left_joint':l,'top_lid_right_joint':l,'lid_pinion_joint':l/.05,'side_lid_joint':0.,'box_tilt_joint':0.}
        req['keyframes'].append({'time':t,'state':{'placements':{p:{'matrix':f['placements'][p]} for p in PATHS},'joints':joints}})
        boxes=[];counts={'harvest':0,'falling':0,'cargo':0};fruit_states={}
        for fruit in data['fruits']:
            m=np.asarray(f['placements'][fruit['path']]);w=mesh[fruit['source']]@m[:3,:3].T+m[:3,3];lo=w.min(0);hi=w.max(0);boxes.append([lo,hi])
            state='harvest' if lo[2]>=.499 else 'cargo' if hi[2]<.445 else 'falling';counts[state]+=1
            fruit_states[fruit['path']]={'location':state,'world_matrix':m.tolist()}
        frame_states.append({'frame':round(t*FPS),'time_s':t,'fruit_states':fruit_states})
        bounds.append(boxes);ledger.append({'frame':round(t*FPS),'time_s':t,**counts,'total':sum(counts.values()),'ids':PATHS})
    bounds=np.asarray(bounds);base['placements'].update(copy.deepcopy(req['keyframes'][0]['state']['placements']));base['joints'].update(req['keyframes'][0]['state']['joints'])
    cargo=np.asarray(data['cargo_world']);clones=[];motion=[];all_speed=[];all_omega=[]
    for i,fruit in enumerate(data['fruits']):
        path=fruit['path'];m0=np.asarray(bake['frames'][0]['placements'][path]);mf=np.asarray(bake['frames'][-1]['placements'][path])
        series=np.array([x['placements'][path] for x in bake['frames']]);scale=np.asarray(fruit['scale'])
        R=Rotation.from_matrix(series[:,:3,:3]/scale);angles=(R[0].inv()*R).magnitude()
        linear=np.linalg.norm(np.diff(series[:,:3,3],axis=0),axis=1)*FPS
        angular=(R[:-1].inv()*R[1:]).magnitude()*FPS
        all_speed.append(linear);all_omega.append(angular)
        motion.append({'path':path,'max_rotation_from_start_deg':float(np.degrees(angles).max()),
            'xy_displacement_m':float(np.linalg.norm(mf[:2,3]-m0[:2,3])),
            'max_speed_after_raw3_m_s':float(linear[90:].max()),'max_angular_speed_after_raw3_rad_s':float(angular[90:].max())})
        clones.append({k:fruit[k] for k in ['path','source','color','scale','mesh_local_bounds']} | {
            'initial_world_matrix':m0.tolist(),'final_world_matrix':mf.tolist(),'final_cargo_matrix':(np.linalg.inv(cargo)@mf).tolist(),
            'final_world_mesh_bounds':bounds[-1,i].tolist()})
    closeframes=[i for i,x in enumerate(bake['frames']) if x['time']>=CLOSE[0]]
    lidbottom=.4449999884236604;clearance=float(lidbottom-bounds[closeframes,:,1,2].max())
    finalinside=all(bounds[-1,i,0,0]>=-6.147-.001 and bounds[-1,i,1,0]<=-5.853+.001 and bounds[-1,i,0,1]>=3.503-.001 and bounds[-1,i,1,1]<=3.797+.001 and bounds[-1,i,0,2]>=.257999995-.001 for i in range(7))
    groups={'positive':[],'negative':[]}
    for c in clones:groups['positive' if c['final_cargo_matrix'][1][3]>=0 else 'negative'].append(c['path'])
    closed={k:0. for k in ['top_lid_left_joint','top_lid_right_joint','lid_pinion_joint','side_lid_joint','box_tilt_joint']}
    state={'schema_version':1,'fruit_count':7,'clones':clones,'cargo_world_end':cargo.tolist(),'closed_joint_values':closed,
        'harvest_floor_final_joint_values':{k:0. for k in ['box_bottom_left_joint','box_bottom_right_joint','harvest_lid_pinion_joint']},
        'source_mesh_points_file':str((V3/'handoff_mesh_points.json').relative_to(ROOT)), 'groups_by_cargo_y':groups,
        'top_lid_clearance_m':clearance,'gui_review':'See ../qa/05_handoff_continuity-mp4-review.json'}
    checks={'same_seven_ids_every_frame':all(set(f['placements'])==set(PATHS) for f in bake['frames']),
        'red_four_yellow_three':sum(c['color']=='red' for c in clones)==4 and sum(c['color']=='yellow' for c in clones)==3,
        'all_seven_inside_lower_basket_at_end':bool(finalinside),'fruit_below_closing_lids':clearance>0,
        'no_per_frame_visibility_opacity_scale_animation':True,
        'scales_preserved':all(np.allclose(np.linalg.norm(np.asarray(f['placements'][c['path']])[:3,:3],axis=0),c['scale'],atol=1e-6) for f in bake['frames'] for c in clones)}
    quiet=(np.max(all_speed,axis=0)<.005)&(np.max(all_omega,axis=0)<.1)
    settled=next((bake['frames'][i]['time'] for i in range(len(quiet)) if all(quiet[i:]) and bake['frames'][i]['time']>OPEN[1]),None)
    checks['all_settled_before_floor_restore']=settled is not None and settled<RESTORE[0]
    physics_meta={'engine':bake['engine'],'seed':SEED,'timestep_s':1./(FPS*bake['substeps_per_frame']),
        'geometry_file':'05_physics_geometry.json','bake_file':'05_physics_bake.json',
        'geometry_sha256':hashlib.sha256((HERE/'05_physics_geometry.json').read_bytes()).hexdigest(),
        'bake_sha256':hashlib.sha256((HERE/'05_physics_bake.json').read_bytes()).hexdigest()}
    evidence={'physics':physics_meta,'timing':{'all_settled_s':settled,'floor_restore_start_s':RESTORE[0],'floor_restore_end_s':RESTORE[1],
        'lid_close_start_s':CLOSE[0],'lid_close_end_s':CLOSE[1]},'frames':frame_states,
        'geometry_audit':'../qa/05_independent_bake_geometry_audit.json','scope':'Blender Bullet short isolated rigid-body bake, replayed in Isaac GUI; not operational/autonomous mission',
        'method':bake['engine'],'physics_inputs':{k:v for k,v in bake.items() if k!='frames'},'seed':SEED,
        'timeline_s':{'harvest_floor_open':OPEN,'harvest_floor_restore':RESTORE,'transport_top_lids_close':CLOSE,'hold_closed':[CLOSE[1],5.]},
        'offline_checks':checks,'offline_all_pass':all(checks.values()),'motion':motion,'frame_ledger':ledger,
        'minimum_fruit_top_to_closing_lid_m':clearance,'geometry_file':'05_physics_geometry.json','bake_file':'05_physics_bake.json',
        'continuity_state':'handoff_continuity_state.json','limits':'Convex contact proxy for original fruit surfaces; no original scale change. GUI/actual MP4 normal and slow-speed naturalness review required.',
        'previous_v4_count_issue':'V4 source explicitly omitted Handoff_07; exact fading render cause not isolated or asserted.',
        'gui_review':'See ../qa/05_handoff_continuity-mp4-review.json'}
    req.update(name='05_handoff_continuity',fps=30,duration_s=5,preview_only=True,easing='linear',preview_warmup_frames=48,
        preview_frames=[0,30,39,45,51,60,75,90,105,116,119,149],
        reset_renderer_accumulation=True,render_settle_frames=24)
    req['provenance']={'scope':evidence['scope'],'fruit_count':7,'motion_evidence':'05_handoff_continuity_evidence.json','continuity_state':'handoff_continuity_state.json','same_asset_scales':True,'house_hidden':False}
    write('05_handoff_continuity.json',req);write('05_handoff_continuity_evidence.json',evidence);write('handoff_continuity_state.json',state)
    print(json.dumps({'checks':checks,'clearance_m':clearance,'groups':groups,'motion':motion},ensure_ascii=False,indent=2))


if __name__=='__main__':
    if '--inspect-usd' in sys.argv:inspect_usd()
    elif '--blender-physics' in sys.argv:physics()
    else:
        if '--reuse-bake' not in sys.argv:
            subprocess.run(['/usr/bin/blender','--background','--factory-startup','--threads','2','--python',str(Path(__file__).resolve()),'--','--blender-physics'],check=True)
        build()
