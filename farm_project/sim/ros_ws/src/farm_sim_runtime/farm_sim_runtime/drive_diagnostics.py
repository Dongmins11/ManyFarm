"""시뮬 명령 수신·바퀴 목표·실측 기록. 구동값과 제어 설정은 변경하지 않습니다."""
import json
import math
from pathlib import Path
import time


class DriveDiagnostics:
    def __init__(self, directory: Path, session: str) -> None:
        self.directory, self.session = directory, session
        directory.mkdir(parents=True, exist_ok=True)
        self.states = {}
        self.last = {}
        self.frame_prims = {}
        self.contact_subscriptions = []

    def received(self, robot_id: str, message: dict, accepted: bool) -> None:
        state = self.states.setdefault(robot_id, dict(received=0, accepted=0, rejected=0))
        state['received'] += 1
        state['accepted' if accepted else 'rejected'] += 1
        state['last_packet'] = {k: message.get(k) for k in ('kind','session','seq','sent','linear','angular')}
        state['last_receive_monotonic_s'] = time.monotonic()

    def describe(self, stage, config: dict, robot_path: str) -> None:
        from pxr import Usd, UsdPhysics
        if config['runtime'].get('diagnostic_contacts', False):
            self.observe_contacts(stage, robot_path, config['robot_id'])
        frames = {}
        for relative in config['runtime'].get('diagnostic_frames', []):
            prim = stage.GetPrimAtPath(robot_path+'/'+relative)
            if not prim.IsValid():
                raise ValueError('평가용 프레임 없음: '+relative)
            frames[relative] = prim
        self.frame_prims[config['robot_id']] = frames
        names = set(config['base']['wheel_joints'])
        joints = []
        for prim in Usd.PrimRange(stage.GetPrimAtPath(robot_path)):
            if prim.GetName() not in names:
                continue
            fields = {}
            for name in ('drive:angular:physics:stiffness','drive:angular:physics:damping',
                         'drive:angular:physics:maxForce','drive:angular:physics:type',
                         'physics:jointEnabled','physxJoint:maxJointVelocity',
                         'physics:lowerLimit','physics:upperLimit'):
                attr = prim.GetAttribute(name)
                value = attr.Get() if attr else None
                if isinstance(value, float) and not math.isfinite(value): value = str(value)
                fields[name] = value
            joints.append(dict(path=str(prim.GetPath()), attributes=fields))
        record = dict(robot_id=config['robot_id'], robot_path=robot_path, base_config=config['base'],
                      ports=config['runtime'], wheel_joints=joints)
        record['articulation_solver'] = [dict(path=str(prim.GetPath()),
            position_iterations=prim.GetAttribute('physxArticulation:solverPositionIterationCount').Get(),
            velocity_iterations=prim.GetAttribute('physxArticulation:solverVelocityIterationCount').Get())
            for prim in Usd.PrimRange(stage.GetPrimAtPath(robot_path))
            if prim.HasAPI(UsdPhysics.ArticulationRootAPI)]
        (self.directory/(config['robot_id']+'_setup.json')).write_text(json.dumps(record,ensure_ascii=False,indent=2))
        print('[drive_diag_setup] '+json.dumps(record,ensure_ascii=False),flush=True)

    def observe_contacts(self, stage: object, robot_path: str, robot_id: str) -> None:
        """명시적 진단 시험에서만 접촉쌍/충격량을 기록한다. 제어·충돌값은 유지한다."""
        from pxr import Usd, UsdPhysics, PhysxSchema, PhysicsSchemaTools
        from omni.physx import get_physx_simulation_interface
        for prim in Usd.PrimRange(stage.GetPrimAtPath(robot_path)):
            if prim.HasAPI(UsdPhysics.RigidBodyAPI):
                PhysxSchema.PhysxContactReportAPI.Apply(prim).CreateThresholdAttr(0.)
        destination = self.directory/(robot_id+'_contacts.jsonl')
        def report(headers: object, points: object) -> None:
            rows = []
            for header in headers:
                actors = [str(PhysicsSchemaTools.intToSdfPath(getattr(header, key)))
                          for key in ('actor0', 'actor1')]
                if not any(a.startswith(robot_path+'/') for a in actors):
                    continue
                data = points[header.contact_data_offset:header.contact_data_offset+header.num_contact_data]
                rows.append(dict(monotonic_s=time.monotonic(), actors=actors,
                    colliders=[str(PhysicsSchemaTools.intToSdfPath(getattr(header, key)))
                               for key in ('collider0', 'collider1')],
                    contacts=[dict(position=list(p.position), normal=list(p.normal),
                                   impulse=list(p.impulse), separation=float(p.separation)) for p in data]))
            if rows:
                with destination.open('a') as stream:
                    stream.write(''.join(json.dumps(r)+'\n' for r in rows))
        self.contact_subscriptions.append(
            get_physx_simulation_interface().subscribe_contact_report_events(report))

    def sample(self, robot: dict, sim_time: float, odom, positions, velocities) -> None:
        from farm_common.kinematics import wheel_targets
        now = time.monotonic()
        rid = robot['cfg']['robot_id']
        period = robot['cfg']['runtime'].get('diagnostic_period_s', 1.0)
        if not math.isfinite(period) or period <= 0:
            raise ValueError('diagnostic_period_s는 양수여야 합니다.')
        if now - self.last.get(rid, -math.inf) < period: return
        self.last[rid] = now
        base, gate = robot['base'], robot['gate']
        cfg = robot['cfg']['base']
        linear, angular = robot['applied_cmd']
        target = wheel_targets(linear,angular,cfg['wheel_radius_m'],cfg['wheel_separation_m'],
                               cfg['max_linear_mps'],cfg['max_angular_rps'])
        record = dict(robot_id=rid,session=self.session,sim_time_s=sim_time,monotonic_s=now,
            transport=self.states.get(rid,dict(received=0,accepted=0,rejected=0)),
            last_accepted_age_s=now-gate.received if math.isfinite(gate.received) else None,
            applied_cmd_mps_rps=[float(linear),float(angular)],
            wheel_order=cfg['wheel_joints'],dof_indices=[int(v) for v in base.indices],
            target_joint_velocity_rad_s=[float(v*s) for v,s in zip(target,cfg['wheel_signs'])],
            applied_joint_velocity_rad_s=[float(v) for v in base.last_joint_targets],
            measured_joint_velocity_rad_s=[float(v*s) for v,s in zip(velocities,cfg['wheel_signs'])],
            measured_control_wheel_position_rad=[float(v) for v in positions],
            wheel_odom=[float(v) for v in odom],
            T_world_base=robot['T_world_base'].tolist())
        if robot['cfg']['runtime'].get('diagnostic_contacts', False):
            record['all_joint_names'] = list(base.robot.dof_names)
            record['all_joint_positions'] = base.robot.get_joint_positions().tolist()
        if self.frame_prims.get(rid):
            from pxr import UsdGeom
            import numpy as np
            cache = UsdGeom.XformCache()
            # USD 실위치는 진단 파일에만 기록한다. ROS/제어기로 전달하지 않는다.
            record['T_world_evaluation_frames'] = {
                name: np.asarray(cache.GetLocalToWorldTransform(prim)).T.tolist()
                for name, prim in self.frame_prims[rid].items()}
        with (self.directory/(rid+'.jsonl')).open('a') as stream:
            stream.write(json.dumps(record,ensure_ascii=False,allow_nan=False)+'\n')
        # 자세 행렬은 파일에 저장하고 터미널에는 주요 값만 표시합니다.
        if period >= 1.0:
            summary = {k:v for k,v in record.items() if k not in (
                'T_world_base','measured_control_wheel_position_rad','T_world_evaluation_frames')}
            print('[drive_diag] '+json.dumps(summary,ensure_ascii=False,allow_nan=False),flush=True)
