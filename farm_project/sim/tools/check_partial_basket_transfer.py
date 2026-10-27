"""기록된 도킹 상대 자세에서 한 알 낙하·수용을 검사한다. 원본 USD/업무 판정은 불변.

수확 바닥과 운송 상단 덮개가 완전히 열린 조건으로 해당 덮개만 시험에서 제외한다.
바구니/벽의 원본 collision, 실제 과실을 참조하며 액추에이터·주행·동시 배출은 없다.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import time
import numpy as np

ROOT=Path(__file__).resolve().parents[2]


def write(path: Path, data: object) -> None:
    path.write_text(json.dumps(data,ensure_ascii=False,indent=2,allow_nan=False)+'\n')


def pose(prim: object, matrix: np.ndarray) -> None:
    from pxr import Gf,UsdGeom
    xf=UsdGeom.Xformable(prim);xf.ClearXformOpOrder()
    xf.AddTransformOp().Set(Gf.Matrix4d(matrix.T.tolist()))


def main() -> None:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--alignment',type=Path,default=ROOT/'sim/runs/docking_alignment_fix_20261027/41/basket_alignment.json')
    parser.add_argument('--output',type=Path,default=ROOT/'sim/runs/partial_basket_transfer_20261027')
    parser.add_argument('--hz',type=int,default=120)
    args=parser.parse_args();args.output.mkdir(parents=True,exist_ok=True)
    if args.hz not in (60,120):parser.error('비교할 물리 주기는 60 또는120Hz입니다.')
    if (args.output/'result.json').exists():raise FileExistsError('기존 시험 결과 보존')
    alignment=json.loads(args.alignment.read_text());diagnostics=Path(alignment['source'])
    if not diagnostics.is_absolute():diagnostics=ROOT/diagnostics
    def last(name):return json.loads((diagnostics/(name+'_01.jsonl')).read_text().splitlines()[-1])
    h,t=last('harvest'),last('transport');hf=h['T_world_evaluation_frames'];tf=t['T_world_evaluation_frames']
    harvest=np.array(hf['harvest_lid_fixed']);receiver=np.array(tf['cargo_box'])
    spec=alignment['spec'];hc=(harvest@[*spec['harvest']['center_local_m'],1.])[:3]
    tc=(receiver@[*spec['transport']['center_local_m'],1.])[:3]
    assets=dict(harvest=ROOT/'sim/assets/robots/harvest_count_test/harvest_robot.usd',
                transport=ROOT/'sim/assets/robots/transport_robot/urdf/transport_robot.portable/transport_robot.sim.usda',
                red=ROOT/'sim/assets/fruit/teacher_9g/pepper_red.usd',
                yellow=ROOT/'sim/assets/fruit/teacher_9g/pepper_yellow.usd')
    hashes={k:hashlib.sha256(p.read_bytes()).hexdigest() for k,p in assets.items()}
    from isaacsim import SimulationApp
    app=SimulationApp({'headless':True,'renderer':'RayTracedLighting','fast_shutdown':False})
    try:
        from pxr import Gf,Usd,UsdGeom,UsdPhysics,PhysxSchema
        from isaacsim.core.api import World
        from isaacsim.core.prims import SingleRigidPrim
        from scipy.spatial.transform import Rotation
        world=World(physics_dt=1/args.hz,rendering_dt=1/30,stage_units_in_meters=1.,backend='numpy',device='cpu')
        stage=world.stage
        physics=PhysxSchema.PhysxSceneAPI.Apply(stage.GetPrimAtPath('/physicsScene'))
        physics.CreateEnableGPUDynamicsAttr(False);physics.CreateBroadphaseTypeAttr('MBP');physics.CreateEnableCCDAttr(True)
        world.scene.add_default_ground_plane()
        sources={k:Usd.Stage.Open(str(p)) for k,p in assets.items()}
        roots={k:str(s.GetDefaultPrim().GetPath()) for k,s in sources.items()}
        cache=UsdGeom.XformCache()
        cargo_source=np.array(cache.GetLocalToWorldTransform(sources['transport'].GetPrimAtPath(roots['transport']+'/cargo_box'))).T
        side_source=np.array(cache.GetLocalToWorldTransform(sources['transport'].GetPrimAtPath(roots['transport']+'/side_lid'))).T
        side_relative=np.linalg.inv(cargo_source)@side_source
        def static_reference(path,source,link,matrix):
            prim=stage.DefinePrim(path,'Xform');prim.GetReferences().AddReference(str(assets[source]),roots[source]+'/'+link)
            prim.RemoveAPI(UsdPhysics.RigidBodyAPI);pose(prim,matrix)
            return prim
        # shape의 실제 cube size/변환을 검사한다. importer extent 메타데이터를 다시 곱하지 않는다.
        shape_checks=[]
        cases=[]
        for condition in ('overlap72','centered_control'):
            for orientation,euler in [('upright',[0,0,0]),('side_x',[90,0,0]),('side_y',[0,90,0])]:
                for x in np.linspace(-.055,.055,5):
                    for y in np.linspace(-.055,.055,5):
                        index=len(cases);offset=np.array([(index%15)*.8,(index//15)*.8,0.])
                        rec=receiver.copy()
                        if condition=='centered_control':rec[:2,3]+=(hc-tc)[:2]
                        rec[:3,3]+=offset
                        namespace=f'/World/Trial_{index:03d}'
                        basket=static_reference(namespace+'/cargo_box','transport','cargo_box',rec)
                        static_reference(namespace+'/side_lid','transport','side_lid',rec@side_relative)
                        for link in ['box_front_wall','box_rear_wall','box_left_wall','box_right_wall']:
                            mat=np.array(hf[link]);mat[:3,3]+=offset
                            static_reference(namespace+'/'+link,'harvest',link,mat)
                        rotation=Rotation.from_euler('xyz',euler,degrees=True)
                        color='red' if index%2==0 else 'yellow'
                        fruit=stage.DefinePrim(namespace+'/fruit','Xform');fruit.GetReferences().AddReference(str(assets[color]))
                        # 실제 collision vertices를 이용해 배출 평면 위2mm부터 시작한다.
                        mesh=sources[color].GetPrimAtPath(roots[color]+'/Collision')
                        vertices=np.array(UsdGeom.Mesh(mesh).GetPointsAttr().Get(),dtype=float)
                        rotated=rotation.apply(vertices)
                        point=(harvest@np.array([x,y,spec['harvest']['center_local_m'][2],1.]))[:3]
                        point[2]=hc[2]-rotated[:,2].min()+.002
                        point+=offset
                        mat=np.eye(4);mat[:3,:3]=rotation.as_matrix();mat[:3,3]=point;pose(fruit,mat)
                        rigid=world.scene.add(SingleRigidPrim(prim_path=str(fruit.GetPath()),name=f'fruit_{index}'))
                        cases.append(dict(id=index,condition=condition,orientation=orientation,color=color,
                            release_xy_m=[float(x),float(y)],offset=offset,receiver=rec,
                            rigid=rigid,vertices=vertices,samples=[],crossed_inlet=False))
                        if index==0:
                            for p in Usd.PrimRange(basket,Usd.TraverseInstanceProxies()):
                                if p.IsA(UsdGeom.Cube) and p.HasAPI(UsdPhysics.CollisionAPI):
                                    m=np.array(cache.GetLocalToWorldTransform(p)).T;size=float(UsdGeom.Cube(p).GetSizeAttr().Get())
                                    shape_checks.append(dict(path=str(p.GetPath()),size_m=(np.linalg.norm(m[:3,:3],axis=0)*size).tolist()))
        write(args.output/'setup.json',dict(scope=__doc__,alignment_source=str(args.alignment),diagnostics=str(diagnostics),
            overlap=alignment['final']['coverage'],center_delta_m=(hc-tc).tolist(),physics_hz=args.hz,physics_device='cpu',
            backend_broadphase='MBP',gravity_mps2=9.81,fruit_mass_kg=.009,initial_velocity_mps=[0,0,0],
            trials=len(cases),shape_checks=shape_checks,asset_hashes_before=hashes,
            assumptions=['한 알씩 독립 시험; 과실 간 충돌 없음','양쪽 배출/상단 덮개 완전 개방','차체 고정; 실제 바구니 충돌 형상/장착값 유지',
                         'release grid는 실제 적재 분포가 아닌 민감도 표본','centered_control만 비교를 위해 수용 바구니 전체를 수평 이동; 운영 자산 수정 없음']))
        world.reset()
        context=world.get_physics_context()
        actual_physics=dict(gpu_dynamics=context.is_gpu_dynamics_enabled(),broadphase=context.get_broadphase_type())
        if actual_physics['gpu_dynamics'] or actual_physics['broadphase']!='MBP':
            raise AssertionError('CPU/MBP 설정 확인 실패: '+str(actual_physics))
        print('DROP_TEST_READY',len(cases),flush=True)
        begin=time.monotonic()
        for step in range(args.hz*4):
            world.step(render=False)
            if step%max(1,args.hz//60):continue
            for case in cases:
                xyz,q=case['rigid'].get_world_pose();v=case['rigid'].get_linear_velocity()
                points=Rotation.from_quat([q[1],q[2],q[3],q[0]]).apply(case['vertices'])+xyz
                local=(np.linalg.inv(case['receiver'])@np.column_stack((points,np.ones(len(points)))).T).T[:,:3]
                center=(np.linalg.inv(case['receiver'])@[*xyz,1.])[:3]
                inside_xy=bool(local[:,0].min()>=-.297 and local[:,0].max()<=-.003 and local[:,1].min()>=-.147 and local[:,1].max()<=.147)
                settled=bool(inside_xy and local[:,2].min()>=-.003 and local[:,2].max()<=.19 and np.linalg.norm(v)<.02)
                if center[2]<.19 and -.297<center[0]<-.003 and abs(center[1])<.147:case['crossed_inlet']=True
                case['samples'].append(dict(time_s=float(world.current_time),position_world_m=(xyz-case['offset']).tolist(),
                    center_in_receiver_m=center.tolist(),speed_mps=float(np.linalg.norm(v)),inside_xy=inside_xy,settled=settled,
                    collision_bounds_in_receiver_m=[local.min(axis=0).tolist(),local.max(axis=0).tolist()]))
        results=[]
        with (args.output/'trajectories.jsonl').open('w') as stream:
            for case in cases:
                tail=[s for s in case['samples'] if s['time_s']>=3.5]
                captured=bool(tail and all(s['settled'] for s in tail))
                final=case['samples'][-1]
                outcome='captured' if captured else ('floor_loss' if final['position_world_m'][2]<.15 else 'not_settled_or_retained')
                row={k:case[k] for k in ('id','condition','orientation','color','release_xy_m','crossed_inlet')}
                row.update(outcome=outcome,captured=captured,final=final)
                results.append(row);stream.write(json.dumps(dict(id=case['id'],samples=case['samples']))+'\n')
        after={k:hashlib.sha256(p.read_bytes()).hexdigest() for k,p in assets.items()}
        summary=[]
        for condition in ('overlap72','centered_control'):
            subset=[r for r in results if r['condition']==condition]
            summary.append(dict(condition=condition,total=len(subset),captured=sum(r['captured'] for r in subset),
                floor_loss=sum(r['outcome']=='floor_loss' for r in subset),other=sum(r['outcome']=='not_settled_or_retained' for r in subset)))
        write(args.output/'result.json',dict(scope='isolated CPU PhysX gravity drop; not unload mechanism or fleet E2E',
            wall_seconds=time.monotonic()-begin,sim_seconds=world.current_time,asset_hashes_unchanged=hashes==after,actual_physics=actual_physics,
            summary=summary,cases=results))
        print('DROP_TEST_RESULT',json.dumps(summary),flush=True)
        if hashes!=after:raise AssertionError('원본 자산 변경')
        world.stop()
    finally:app.close()


if __name__=='__main__':main()
