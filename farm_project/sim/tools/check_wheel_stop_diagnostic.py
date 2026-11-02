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


def replay_arm(world: object, base: object, report: dict, stage: object,
               body: object, control: np.ndarray, trace: Path, output: Path, *, switch: bool = False) -> None:
    """실패한 팔 drive 명령을 재생해 solver별 정지 차체의 이동을 비교한다."""
    from pxr import UsdGeom
    from isaacsim.core.utils.types import ArticulationAction
    from farm_sim_runtime.harvest_physics import initialize_arm_travel
    commands = [json.loads(line) for line in trace.open()]
    start = commands[0]['time_s']
    commands = [row for row in commands if row['event'] == 'STUDENT_CONTROL']
    duration = commands[-1]['time_s']-start
    cases = []
    for iterations in ((12,) if switch else (64, 12, 64)):
        world.reset();base.initialize();initialize_arm_travel(base.robot, report)
        indices = np.array([base.robot.get_dof_index(name) for name in report['joint_names']], dtype=np.int32)
        base.robot.set_solver_position_iteration_count(64 if switch else iterations)
        base.robot.set_solver_velocity_iteration_count(4)
        for _ in range(180):
            base.command(0., 0.);world.step(render=False)
        if switch:
            from farm_sim_runtime.teacher_arm_alignment import update_arm_solver_mode
            update_arm_solver_mode(base.robot, dict(solver_position_iterations=64,
                harvest_solver_position_iterations=12), arm_active=True)
        def pose():
            return np.asarray(UsdGeom.XformCache().GetLocalToWorldTransform(body), float).T@control
        origin = pose();rows=[];index=0
        for tick in range(math.ceil(duration*60)+1):
            elapsed=tick/60
            while index < len(commands) and commands[index]['time_s']-start <= elapsed+1e-6:
                row=commands[index];act=row['applied_actuator'];view=base.robot._articulation_view
                view.set_gains(kps=np.asarray(act['stiffness'],np.float32)[None],joint_indices=indices)
                view.set_max_joint_velocities(np.asarray(act['velocity_limits'],np.float32)[None],joint_indices=indices)
                base.robot.apply_action(ArticulationAction(joint_positions=np.asarray(row['final_joint_targets'],np.float32),joint_indices=indices))
                index+=1
            base.command(0.,0.);world.step(render=False)
            if tick%6 == 0:
                current=pose()
                rows.append(dict(time_s=elapsed, displacement_mm=1000*float(np.linalg.norm(current[:3,3]-origin[:3,3])),
                    yaw_deg=math.degrees(math.remainder(math.atan2(current[1,0],current[0,0])-math.atan2(origin[1,0],origin[0,0]),2*math.pi)),
                    world_base=current.tolist(), wheel_positions=base.positions().tolist()))
        label=f'arm_position{iterations}_{len(cases)+1}'
        (output/(label+'.json')).write_text(json.dumps(rows)+'\n')
        cases.append(dict(case=label,position_iterations=iterations,duration_s=duration,
            switched_from_drive_solver=switch,
            max_base_displacement_mm=max(row['displacement_mm'] for row in rows), final_base_displacement_mm=rows[-1]['displacement_mm'],
            final_yaw_deg=rows[-1]['yaw_deg']))
        (output/'summary.json').write_text(json.dumps(dict(scope='recorded arm drives, default plane, no fruit/ROS/cameras; base world pose is evaluation only',trace=str(trace),cases=cases),indent=2)+'\n')
        print(json.dumps(cases[-1]),flush=True)
    world.stop()


def main() -> None:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output',type=Path)
    parser.add_argument('--isolated-robot', action='store_true',
                        help='병행 진단용: 수확 모델과 평면만 사용, 카메라/농장 렌더 없음')
    parser.add_argument('--arc-stop', action='store_true', help='후진 원호→정지와 회전→정지를 함께 대조')
    parser.add_argument('--position-sweep', action='store_true', help='속도 반복 대신 구동기/접촉 위치 반복 수 비교')
    parser.add_argument('--idle-seconds', type=float, help='장시간 정지 제동 비교: 주행 solver64, 기준/감쇠10배/기준 재시험')
    parser.add_argument('--idle-position-hold', action='store_true', help='정지 바퀴 엔코더 위치를 joint drive 목표로 유지하는 단일 비교')
    parser.add_argument('--spin-goal', type=float,
                        help='인계 Spin과 같은 ±0.03rad/s/20Hz 및 0.1초 관측 지연으로 지정 rad 회전 후 정지')
    parser.add_argument('--arm-trace', type=Path, help='저장된 Student 팔 명령으로 정지 차체 이동을 대조')
    parser.add_argument('--arm-switch', action='store_true', help='주행64→팔12 실제 PhysX 전환 후 저장 명령 재생')
    args=parser.parse_args();args.output.mkdir(parents=True,exist_ok=False)
    root=Path(__file__).resolve().parents[2]
    cfg=json.loads((root/'sim/ros_ws/src/farm_sim_config/config/harvest.json').read_text())
    cfg['base']['wheel_position_hold'] = args.idle_position_hold
    profile=json.loads((root/cfg['runtime']['robotarm_physics_config']).read_text())
    from isaacsim import SimulationApp
    sys.argv=[sys.argv[0]]
    app=SimulationApp({'headless':True,'disable_viewport_updates':args.isolated_robot,
                      'renderer':'RayTracedLighting','fast_shutdown':args.isolated_robot})
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
        if args.isolated_robot:
            from isaacsim.core.utils.stage import create_new_stage
            create_new_stage()
        else:
            open_stage(str(root/'sim/assets'/cfg['scene']))
        stage=omni.usd.get_context().get_stage();stage.SetEditTarget(stage.GetSessionLayer())
        if not args.isolated_robot:ensure_bed_collisions(stage)
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
        if args.isolated_robot:world.scene.add_default_ground_plane()
        align_teacher_scene(world);pc=world.get_physics_context();pc.enable_gpu_dynamics(False);pc.set_broadphase_type('MBP')
        base=BaseSim(world,str(body.GetPath()),cfg['base'],name='stop_diagnostic')
        if args.arm_trace is not None:
            replay_arm(world,base,report,stage,body,T_control,args.arm_trace,args.output,switch=args.arm_switch)
            return
        results=[]
        cases=[('baseline',1.,4),('damping10',10.,4),('velocity16',1.,16),('baseline_repeat',1.,4)]
        if args.idle_seconds is not None:
            if not math.isfinite(args.idle_seconds) or args.idle_seconds <= 0:
                raise ValueError('정지 시험 시간은 양의 유한한 초여야 합니다.')
            cases=[('idle_baseline',1.,4),('idle_damping10',10.,4),('idle_baseline_repeat',1.,4)]
            if args.idle_position_hold:cases=[('idle_position_hold',1.,4)]
        if args.arc_stop:
            cases=[(f'{mode}_{label}',1.,iterations) for mode in ('arc','spin')
                   for label,iterations in [('baseline',4),('velocity16',16),('velocity32',32),('baseline_repeat',4)]]
            if args.position_sweep:
                cases=[(f'{mode}_{label}',1.,4) for mode in ('arc','spin')
                       for label in ('baseline','position32','position64','baseline_repeat')]
        if args.spin_goal is not None:
            if not math.isfinite(args.spin_goal) or not 0 < abs(args.spin_goal) <= .1:
                raise ValueError('진단 Spin 목표는 0 초과 0.1rad 이하입니다.')
            cases=[(label,1.,4) for label in ('spin_baseline','spin_position64','spin_position128',
                                             'spin_baseline_repeat','spin_position64_repeat','spin_position128_repeat')]
        for label,mult,iterations in cases:
            world.reset();base.initialize();initialize_arm_travel(base.robot,report)
            ctl=base.robot.get_articulation_controller();kp,kd=ctl.get_gains();kp=np.asarray(kp).copy();kd=np.asarray(kd).copy()
            # reset이 이전 gain을 유지할 수 있어 첫 기준값을 명시적으로 보존한다.
            if not results:original_kp=kp.copy();original_kd=kd.copy()
            kp=original_kp.copy();kd=original_kd.copy();kd[base.indices]*=mult
            ctl.set_gains(kps=kp,kds=kd)
            base.robot.set_solver_velocity_iteration_count(iterations)
            position_iterations=(128 if 'position128' in label else 64 if 'position64' in label
                                 else 32 if 'position32' in label else 12)
            if args.idle_seconds is not None:position_iterations=64
            base.robot.set_solver_position_iteration_count(position_iterations)
            rows=[]
            spin_finished=False;spin_command=0.
            for tick in range(max(720,math.ceil(args.idle_seconds*60)) if args.idle_seconds is not None else 720):
                # 정지3초 → 0.03rad/s 회전3초 → 정지6초. 모든 조건 동일.
                moving=180<=tick<360
                cmd=(.1 if label.startswith('arc_') else .03) if moving else 0.
                linear=-.01 if moving and label.startswith('arc_') else 0.
                if args.idle_seconds is not None:linear=cmd=0.
                if args.spin_goal is not None:
                    linear=0.
                    if tick>=180 and tick%3==0 and not spin_finished:
                        delta=math.remainder(rows[tick-7]['odom'][2]-rows[173]['odom'][2],2*math.pi)
                        spin_finished=abs(args.spin_goal)-abs(delta)<1e-6
                        spin_command=0. if spin_finished else math.copysign(.03,args.spin_goal)
                    cmd=spin_command
                base.command(linear,cmd);world.step(render=False)
                if not args.isolated_robot and tick%2==0:world.render()
                od,pos,vel=base.sample(1/60)
                T=np.asarray(UsdGeom.XformCache().GetLocalToWorldTransform(body),float).T@T_control
                rows.append(dict(tick=tick,time_s=tick/60,cmd=cmd,linear=linear,wheels=pos,velocities=vel,targets=base.last_joint_targets.tolist(),yaw=math.atan2(T[1,0],T[0,0]),xyz=T[:3,3].tolist(),odom=list(od)))
            (args.output/(label+'.json')).write_text(json.dumps(rows)+'\n')
            a,b=rows[390],rows[540]
            delta=np.array(b['wheels'])-a['wheels'];wheel_yaw=cfg['base']['wheel_radius_m']*(delta[1]-delta[0])/cfg['base']['wheel_separation_m']
            result=dict(case=label,wheel_kp=kp[base.indices].tolist(),wheel_kd=kd[base.indices].tolist(),solver_velocity_iterations=iterations,post_stop_interval_s=[.5,3.],wheel_yaw_deg=math.degrees(wheel_yaw),world_yaw_deg=math.degrees(math.atan2(math.sin(b['yaw']-a['yaw']),math.cos(b['yaw']-a['yaw']))))
            result['solver_position_iterations']=position_iterations
            origin=rows[179]['odom'];stopped=rows[359]['odom'];end=rows[540]['odom']
            result.update(stop_travel_mm=1000*math.dist(stopped[:2],end[:2]),
                          stop_rotation_deg=math.degrees(math.remainder(end[2]-stopped[2],2*math.pi)))
            if args.idle_seconds is not None:
                result.update(idle_seconds=args.idle_seconds,
                    idle_world_travel_mm=1000*math.dist(rows[180]['xyz'][:2],rows[-1]['xyz'][:2]),
                    idle_odom_travel_mm=1000*math.dist(rows[180]['odom'][:2],rows[-1]['odom'][:2]))
            if args.spin_goal is not None:
                result.update(spin_goal_rad=args.spin_goal,spin_finished=spin_finished,
                    final_goal_error_deg=math.degrees(math.remainder(
                        rows[-1]['odom'][2]-rows[173]['odom'][2]-args.spin_goal,2*math.pi)))
            if label.startswith('arc_'):
                deviations=[]
                for row in rows[180:541]:
                    x,y,yaw=row['odom'][:3];angle=math.remainder(yaw-origin[2],2*math.pi)
                    dx,dy=-.1*math.sin(angle),-.1*(1-math.cos(angle))
                    c,s=math.cos(origin[2]),math.sin(origin[2])
                    deviations.append(1000*math.hypot(x-origin[0]-c*dx+s*dy,y-origin[1]-s*dx-c*dy))
                result['max_arc_deviation_mm']=max(deviations)
            results.append(result);print(json.dumps(result),flush=True)
            scope=('isolated robot/default plane; ' if args.isolated_robot else 'farm scene; ')
            (args.output/'summary.json').write_text(json.dumps(dict(scope=scope+'harvest body+travel arms; no ROS/sensors/transport/fruit runtime; prescribed motion-stop, not failed trajectory replay',cases=results),indent=2)+'\n')
        world.stop()
    finally:
        # 작은 무통신 진단은 결과 저장 후 SDK의 즉시 종료를 사용한다.
        # 전체 농장/ROS 프로세스와 공유하는 자원이나 제어 포트가 없다.
        app.close(skip_cleanup=args.isolated_robot)


if __name__=='__main__':main()
