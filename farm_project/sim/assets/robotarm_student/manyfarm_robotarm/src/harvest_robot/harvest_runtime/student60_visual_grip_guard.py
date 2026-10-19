"""Preserve visible grasp alignment across brief occlusion, using policy output.

Loaded-grip intent comes from the neural servo prediction, not evaluator phase.
No simulator grip/contact/fruit pose is read and no success is declared here.
"""
import numpy as np
from .student60_visual_servo import VisualServoController
from .student60 import encode_command,decode_command


class GuardedVisualServoController(VisualServoController):
    def start(self,target_id,initial_target_rad):
        super().start(target_id,initial_target_rad)
        self.last_near_time=-float('inf');self.last_near_distance=None
        self.loaded_since=None;self.hold_until=None;self.hold_arm=None;self.guard_finished=False

    def step(self,frames,q_rad,qd_rad_s,tcp_arm,target,now,capture):
        command,note=super().step(frames,q_rad,qd_rad_s,tcp_arm,target,now,capture)
        report=note['visual_servo'];distance=report.get('observed_target_distance_m')
        if distance is not None and distance<.05:
            self.last_near_time=now;self.last_near_distance=distance
        goal,servo=decode_command(command,self.contract['lower_rad'],self.contract['upper_rad'])
        near_recent=now-self.last_near_time<=.75
        loaded_hint=servo[1]<.4 and near_recent
        self.loaded_since=(now if self.loaded_since is None else self.loaded_since) if loaded_hint else None
        if not self.guard_finished and self.hold_until is None and self.loaded_since is not None and now-self.loaded_since>=.1-1e-6:
            self.hold_until=now+2.1;self.hold_arm=self.inner.previous_q[:5].copy()
        if self.hold_until is not None and now<self.hold_until:
            goal[:5]=self.hold_arm
            command=encode_command(goal,servo,self.contract['lower_rad'],self.contract['upper_rad'])
            report.update(active=True,neural_loaded_grip_hold=True,hold_remaining_s=self.hold_until-now)
        elif self.hold_until is not None:
            self.guard_finished=True;self.captured=True
            report['neural_loaded_grip_hold_completed']=True
        elif not note['target']['valid'] and near_recent and not self.guard_finished:
            # Keep command targets, but preserve invalid/zero target observations
            # and continue updating the network with the real camera stream.
            goal[:5]=self.inner.previous_q[:5]
            command=encode_command(goal,servo,self.contract['lower_rad'],self.contract['upper_rad'])
            report.update(active=True,brief_occlusion_arm_hold=True)
        return command,note
