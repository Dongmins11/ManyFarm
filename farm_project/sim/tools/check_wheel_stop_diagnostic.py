"""원본 USD를 유지하는 축소 물리 시험. 감쇠/solver 영향만 세션에서 비교한다.

Isaac Python에서 실행한다. ROS/작업 성공판정은 실행하지 않는다.
"""
import argparse
import copy
import json
import math
from pathlib import Path
import sys
import numpy as np


def main() -> None:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output',type=Path)
    args=parser.parse_args();args.output.mkdir(parents=True,exist_ok=False)
    root=Path(__file__).resolve().parents[2]
    cfg=json.loads((root/'sim/ros_ws/src/farm_sim_config/config/harvest.json').read_text())
    profile=json.loads((root/cfg['runtime']['robotarm_physics_config']).read_text())
    from isaacsim import SimulationApp
    sys.argv=[sys.argv[0]]
    app=SimulationApp({'headless':True,'renderer':'RayTracedLighting','fast_shutdown':False})
    try:
        import omni.usd
        from pxr import Gf,Usd,UsdGeom,UsdPhysics,PhysxSchema
        from isaacsim.core.api import World
        from isaacsim.core.utils.stage import open_stage
        from farm_sim_runtime.robotarm_asset_setup import configure_harvest_arm
        from farm_sim_runtime.harvest_physics import initialize_arm_travel
        from farm_sim_runtime.teacher_arm_alignment import align_teacher_scene
        from farm_sim_devices.base_sim import BaseSim
        from farm_sim_devices.control_frame import asset_from_control,station_root_transform
        from farm_sim_runtime.bed_collisions import ensure_bed_collisions
        open_stage(str(root/'sim/assets'/cfg['scene']))
        stage=omni.usd.get_context().get_stage();stage.SetEditTarget(stage.GetSessionLayer())
        ensure_bed_collisions(stage)
        binding=cfg['scene_binding'];rp=next((v for v in binding['robot_prim_candidates'] if stage.GetPrimAtPath(v).IsValid()),binding['robot_prim'])
        robot=stage.GetPrimAtPath(rp)
        if not robot.IsValid():
            robot=UsdGeom.Xform.Define(stage,rp).GetPrim();robot.GetReferences().AddReference(str(root/'sim/assets'/binding['asset_file']))
        stage.Load(rp)
        arm_cfg=copy.deepcopy(profile)
        for key in ('box_floor','teacher_alignment'):
            if 'asset_path' in arm_cfg[key]:arm_cfg[key]['asset_path']=str(root/arm_cfg[key]['asset_path'])
        report=configure_harvest_arm(stage,rp,arm_cfg)
        body=stage.GetPrimAtPath(rp+'/'+binding['articulation_relative'])
        cache=UsdGeom.XformCache()
        matrix=lambda p:np.asarray(cache.GetLocalToWorldTransform(p),float).T
        T_control=asset_from_control(binding)
        # 실제 실패 구간 시작 자세를 초기 배치에만 사용. 실행 중 정답 제어 없음.
        raw=root/'sim/runs/drive_diagnostics/16f78511388b4a9bb86fb520f5c6d2b7/harvest_01.jsonl'
        records=[json.loads(l) for l in raw.open()]
        reference=min(records,key=lambda v:abs(v['sim_time_s']-60.))
        desired=np.array(reference['T_world_base'])
        newroot=station_root_transform(desired,matrix(body),matrix(robot),T_control)
        parent=robot.GetParent();local=np.linalg.inv(matrix(parent))@newroot
        xf=UsdGeom.Xformable(robot);xf.ClearXformOpOrder();xf.AddTransformOp().Set(Gf.Matrix4d(*local.T.flatten()))
        scenes=[str(p.GetPath()) for p in stage.Traverse() if p.IsA(UsdPhysics.Scene)]
        world=World(physics_dt=1/60,rendering_dt=1/30,stage_units_in_meters=1.,physics_prim_path=scenes[0] if scenes else '/World/physicsScene',backend='numpy')
        align_teacher_scene(world);pc=world.get_physics_context();pc.enable_gpu_dynamics(False);pc.set_broadphase_type('MBP')
        base=BaseSim(world,str(body.GetPath()),cfg['base'],name='stop_diagnostic')
        results=[]
        for label,mult,iterations in [('baseline',1.,4),('damping10',10.,4),('velocity16',1.,16),('baseline_repeat',1.,4)]:
            world.reset();base.initialize();initialize_arm_travel(base.robot,report)
            ctl=base.robot.get_articulation_controller();kp,kd=ctl.get_gains();kp=np.asarray(kp).copy();kd=np.asarray(kd).copy()
            # reset이 이전 gain을 유지할 수 있어 첫 기준값을 명시적으로 보존한다.
            if not results:original_kp=kp.copy();original_kd=kd.copy()
            kp=original_kp.copy();kd=original_kd.copy();kd[base.indices]*=mult
            ctl.set_gains(kps=kp,kds=kd)
            base.robot.set_solver_velocity_iteration_count(iterations)
            rows=[]
            for tick in range(720):
                # 정지3초 → 0.03rad/s 회전3초 → 정지6초. 모든 조건 동일.
                cmd=.03 if 180<=tick<360 else 0.
                base.command(0.,cmd);world.step(render=False)
                if tick%2==0:world.render()
                od,pos,vel=base.sample(1/60)
                T=np.asarray(UsdGeom.XformCache().GetLocalToWorldTransform(body),float).T@T_control
                rows.append(dict(tick=tick,time_s=tick/60,cmd=cmd,wheels=pos,velocities=vel,targets=base.last_joint_targets.tolist(),yaw=math.atan2(T[1,0],T[0,0]),xyz=T[:3,3].tolist()))
            (args.output/(label+'.json')).write_text(json.dumps(rows)+'\n')
            a,b=rows[390],rows[540]
            delta=np.array(b['wheels'])-a['wheels'];wheel_yaw=cfg['base']['wheel_radius_m']*(delta[1]-delta[0])/cfg['base']['wheel_separation_m']
            result=dict(case=label,wheel_kp=kp[base.indices].tolist(),wheel_kd=kd[base.indices].tolist(),solver_velocity_iterations=iterations,post_stop_interval_s=[.5,3.],wheel_yaw_deg=math.degrees(wheel_yaw),world_yaw_deg=math.degrees(math.atan2(math.sin(b['yaw']-a['yaw']),math.cos(b['yaw']-a['yaw']))))
            results.append(result);print(json.dumps(result),flush=True)
            (args.output/'summary.json').write_text(json.dumps(dict(scope='farm scene, harvest body+travel arms; no ROS/sensors/transport/fruit runtime; prescribed turn-stop, not failed trajectory replay',cases=results),indent=2)+'\n')
        world.stop()
    finally:app.close()


if __name__=='__main__':main()
