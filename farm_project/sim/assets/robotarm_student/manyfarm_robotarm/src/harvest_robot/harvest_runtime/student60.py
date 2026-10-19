"""Teacher60 command contract shared by offline labels and Student inference.

No simulator truth, phase, contact flag, or hardware access. Servo gain is an
Isaac position-drive parameter, NOT a calibrated STS3215 torque command.
"""
import numpy as np
from .student60_contract import encode_targets, decode_targets

VERSION = 'student60_executed_targets_servo_v1'
OBSERVATION = 'fresh50ms_release_latch_v1'
SERVO_LO = np.array([1., .15])
SERVO_HI = np.array([8., 1.5])


def encode_command(target, servo, lower, upper):
    servo = np.asarray(servo, dtype=float)
    if servo.shape != (2,) or not np.isfinite(servo).all() or np.any(servo < SERVO_LO-1e-6) or np.any(servo > SERVO_HI+1e-6):
        raise ValueError('Jaw stiffness/velocity outside recorded command contract')
    return np.r_[encode_targets(target, lower, upper), 2*(servo-SERVO_LO)/(SERVO_HI-SERVO_LO)-1].astype('float32')


def decode_command(command, lower, upper):
    x = np.asarray(command, dtype=float)
    if x.shape != (8,) or not np.isfinite(x).all() or np.any(np.abs(x)>1.000001):
        raise ValueError('Expected 6 normalized targets + 2 bounded jaw servo commands')
    # Reuse validation for joint bounds as well as for action.
    target = decode_targets(x[:6], lower, upper)
    encode_targets(target, lower, upper)
    return target, SERVO_LO+(x[6:]+1)*.5*(SERVO_HI-SERVO_LO)


class TargetFilter:
    """Fresh-only target; latch release using commanded opening + measured TCP.

Box coordinates and TCP must share the arm frame. Does not declare success.
The caller explicitly resets between assigned targets; no auto re-acquisition.
"""
    def __init__(self, box_from_arm, box_min, box_max):
        self.box_from_arm=np.asarray(box_from_arm,float)
        self.lo=np.asarray(box_min,float);self.hi=np.asarray(box_max,float)
        if self.box_from_arm.shape!=(4,4) or not np.isfinite(self.box_from_arm).all() or self.lo.shape!=(3,) or self.hi.shape!=(3,) or np.any(self.hi<=self.lo):
            raise ValueError('Invalid tray frame/bounds')
        self.reset()

    def reset(self):
        self.released=False;self.last=None;self.still_s=0.;self.opening=0.

    def observe_command(self, previous_target, target, tcp_arm, dt=.05):
        if abs(dt-.05)>1e-8:raise ValueError('Require 20Hz')
        p=(self.box_from_arm@np.r_[np.asarray(tcp_arm,float),1])[:3]
        # TCP can sit above or beside the fruit center; this is an observation
        # suppression region only, not an authorization to open or success gate.
        zone=bool(np.all(p[:2]>=self.lo[:2]-.06) and np.all(p[:2]<=self.hi[:2]+.06)
                  and self.hi[2]-.04 <= p[2] <= self.hi[2]+.18)
        speed=float('inf') if self.last is None else np.linalg.norm(p-self.last)/dt
        self.still_s=self.still_s+dt if zone and speed<=.03 else 0.
        self.last=p
        delta=float(target[-1]-previous_target[-1])
        self.opening=max(0., self.opening+delta) if zone and self.still_s>=.15 else 0.
        if self.opening>=.012: self.released=True

    def filter(self, target):
        result=dict(target)
        age=float(target['age_s'])
        fresh=bool(target['valid'] and np.isfinite(age) and 0<=age<=.050001)
        result['valid']=fresh and not self.released
        if not result['valid']:result['position_m']=[0.,0.,0.]
        result['age_s']=float(np.clip(age,0,.3)) if np.isfinite(age) else .3
        return result


def apply_sim_command(env, command):
    """Apply the same absolute goals/servo settings without Teacher controllers.

Only writes commands, never measured joint state, contact flags or fruit pose.
Other drive properties remain those of the pinned environment.
"""
    import torch
    if env.targets.shape != (1,6) or abs(env.physics_dt-1/60)>1e-10 or abs(env.step_dt-.05)>1e-10:
        raise ValueError('This adapter requires one environment,60Hz physics/20Hz control')
    q,servo=decode_command(command,env.lower.cpu().numpy(),env.upper.cpu().numpy())
    env.targets[0]=torch.as_tensor(q,device=env.device,dtype=env.targets.dtype)
    ids=torch.tensor([0],device=env.device)
    gain=torch.tensor([[servo[0]]],device=env.device,dtype=env.targets.dtype)
    limit=torch.tensor([[servo[1]]],device=env.device,dtype=env.targets.dtype)
    env.robot.write_joint_stiffness_to_sim(gain,joint_ids=[env.jids[-1]],env_ids=ids)
    env.robot.actuators['gripper'].stiffness[0,0]=gain[0,0]
    env.robot.write_joint_velocity_limit_to_sim(limit,joint_ids=[env.jids[-1]],env_ids=ids)
    env.robot.set_joint_position_target(env.targets,joint_ids=env.jids)
