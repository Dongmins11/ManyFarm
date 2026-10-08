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

    def received(self, robot_id: str, message: dict, accepted: bool) -> None:
        state = self.states.setdefault(robot_id, dict(received=0, accepted=0, rejected=0))
        state['received'] += 1
        state['accepted' if accepted else 'rejected'] += 1
        state['last_packet'] = {k: message.get(k) for k in ('kind','session','seq','sent','linear','angular')}
        state['last_receive_monotonic_s'] = time.monotonic()

    def describe(self, stage, config: dict, robot_path: str) -> None:
        from pxr import Usd
        names = set(config['base']['wheel_joints'])
        joints = []
        for prim in Usd.PrimRange(stage.GetPrimAtPath(robot_path)):
            if prim.GetName() not in names:
                continue
            fields = {}
            for name in ('drive:angular:physics:stiffness','drive:angular:physics:damping',
                         'drive:angular:physics:maxForce','drive:angular:physics:type',
                         'physics:jointEnabled','physxJoint:maxJointVelocity'):
                attr = prim.GetAttribute(name)
                value = attr.Get() if attr else None
                if isinstance(value, float) and not math.isfinite(value): value = str(value)
                fields[name] = value
            joints.append(dict(path=str(prim.GetPath()), attributes=fields))
        record = dict(robot_id=config['robot_id'], robot_path=robot_path, base_config=config['base'],
                      ports=config['runtime'], wheel_joints=joints)
        (self.directory/(config['robot_id']+'_setup.json')).write_text(json.dumps(record,ensure_ascii=False,indent=2))
        print('[drive_diag_setup] '+json.dumps(record,ensure_ascii=False),flush=True)

    def sample(self, robot: dict, sim_time: float, odom, positions, velocities) -> None:
        from farm_common.kinematics import wheel_targets
        now = time.monotonic()
        rid = robot['cfg']['robot_id']
        if now - self.last.get(rid, -math.inf) < 1.0: return
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
        with (self.directory/(rid+'.jsonl')).open('a') as stream:
            stream.write(json.dumps(record,ensure_ascii=False,allow_nan=False)+'\n')
        # 자세 행렬은 파일에 저장하고 터미널에는 주요 값만 표시합니다.
        summary = {k:v for k,v in record.items() if k not in ('T_world_base','measured_control_wheel_position_rad')}
        print('[drive_diag] '+json.dumps(summary,ensure_ascii=False,allow_nan=False),flush=True)
