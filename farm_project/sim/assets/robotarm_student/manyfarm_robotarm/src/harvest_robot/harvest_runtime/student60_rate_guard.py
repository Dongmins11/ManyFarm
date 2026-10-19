"""Bound absolute Student goals by the recorded Teacher command slew only.

No target pose, contacts, phase, IK, or simulator truth is consulted. Physical
actuators and success predicates are unchanged. Feedback uses applied goals.
"""
import numpy as np
from .student60 import decode_command,encode_command
from .student60_controller import Student60Controller


def limit_command(command,previous_q,contract):
    q,servo=decode_command(command,contract['lower_rad'],contract['upper_rad'])
    previous=np.asarray(previous_q,dtype=float)
    if previous.shape!=(6,) or not np.isfinite(previous).all():raise ValueError('Invalid previous applied goals')
    settings=contract['task'];dt=float(contract['control_dt'])
    if abs(dt-.05)>1e-9:raise ValueError('Require recorded20Hz command clock')
    speed=np.array([float(settings['action_speed'])]*5+[float(settings['gripper_speed'])])
    if not np.isfinite(speed).all() or np.any(speed<=0):raise ValueError('Invalid recorded command speed')
    step=speed*dt
    bounded=previous+np.clip(q-previous,-step,step)
    bounded=np.clip(bounded,contract['lower_rad'],contract['upper_rad'])
    applied=encode_command(bounded,servo,contract['lower_rad'],contract['upper_rad'])
    return applied,dict(raw_predicted_command=np.asarray(command).tolist(),previous_applied_q_rad=previous.tolist(),
        raw_delta_rad=(q-previous).tolist(),applied_delta_rad=(bounded-previous).tolist(),
        maximum_delta_rad=step.tolist(),limited=bool(np.any(np.abs(q-bounded)>2e-7)),
        source='recorded_task_action_speed_and_gripper_speed',privileged_state_used=False)


class RateGuardedStudent60Controller(Student60Controller):
    def step(self,*args,**kwargs):
        command,note=super().step(*args,**kwargs)
        bounded,guard=limit_command(command,self.previous_q,self.contract)
        note['command_guard']=guard
        return bounded,note
