"""Encoder/vision closure and finite preload around the learned camera policy.

A learned low-speed hint alone cannot prove contact. Require a measured closing
stall after observed open-jaw entry. Keep a bounded motor tracking error while
holding, and let the original physical grader decide actual grasp/harvest.
"""
import numpy as np
from collections import deque
from .student60_pregrasp import PregraspCameraController
from .student60 import encode_command,decode_command


class ObservedClosureController(PregraspCameraController):
    def holding_jaw_target(self,q,now):
        # Hold a captured goal, rather than ratcheting measured-angle minus
        # error on every tick. Continuous re-closing displaced the Yellow fruit
        # during the physical bridge. This bounded position law is portable to
        # a calibrated position driver; simulator stiffness is a separate layer.
        elapsed=max(0.,now-self.hold_start)
        wanted=self.hold_jaw-min(.015,.015*elapsed)
        wanted=max(wanted,float(q[-1])-.06)
        return float(np.clip(wanted,self.inner.previous_q[-1]-.02,self.inner.previous_q[-1]+.02))

    def start(self,*args):
        super().start(*args);self.motor_stall_s=0.;self.release_still_s=0.;self.release_previous_tcp=None
        self.jaw_samples=deque(maxlen=5)

    def step(self,frames,q,qd,tcp,target,now,capture):
        if not hasattr(self,'jaw_samples'):self.jaw_samples=deque(maxlen=5)
        self.jaw_samples.append(float(q[-1]))
        # A substep velocity can alias at the drive limit while the measured
        # 20Hz position is stationary. Require a full 0.2s position window for
        # that alternative, plus a persistent closing tracking error.
        sampled_stop=(len(self.jaw_samples)==5 and np.ptp(self.jaw_samples)<.006
                      and abs(self.jaw_samples[-1]-self.jaw_samples[0])/.2<.02)
        if self.entry_ready and self.hold_start is None:
            stalled=(q[-1]>.25 and q[-1]-self.inner.previous_q[-1]>.015
                     and (abs(qd[-1])<.10 or sampled_stop))
            self.motor_stall_s=self.motor_stall_s+.05 if stalled else 0.
            if self.motor_stall_s>=.20-1e-6:
                self.hold_start=now;self.hold_arm=self.inner.previous_q[:5].copy()
                self.hold_jaw=float(self.inner.previous_q[-1]);self.captured=True
        tcp_array=np.asarray(tcp,float)
        previous_tcp=getattr(self,'release_previous_tcp',None)
        speed=np.linalg.norm(tcp_array-previous_tcp)/.05 if previous_tcp is not None else float('inf')
        self.release_previous_tcp=tcp_array.copy()
        point=(np.asarray(self.contract.get('box_from_arm',np.eye(4)))@np.r_[tcp_array,1])[:3]
        if 'box_min' in self.contract:
            lo=np.asarray(self.contract['box_min']);hi=np.asarray(self.contract['box_max']);radius=self.contract['task']['diameter']/2
            zone=bool(np.all(point[:2]>=lo[:2]+radius+.005) and np.all(point[:2]<=hi[:2]-radius-.005)
                      and hi[2]+radius+.005<=point[2]<=hi[2]+radius+.075)
        else:zone=False
        self.release_still_s=getattr(self,'release_still_s',0.)+.05 if zone and speed<.03 else 0.
        previous_hold=self.hold_start
        command,note=super().step(frames,q,qd,tcp,target,now,capture)
        # Reject a time/servo prediction that starts a hold before the observed
        # jaw has actually stopped closing. No force/contact flag is consulted.
        if previous_hold is None and self.hold_start is not None and self.motor_stall_s<.20-1e-6:
            self.hold_start=None;self.hold_arm=None;self.hold_jaw=None;self.loaded_since=None
            note['visual_servo']['premature_neural_hold_rejected']=True
        if self.tray_release and self.release_still_s<.4-1e-6:
            self.tray_release=False;note['visual_servo']['release_waits_for_measured_stop']=True
        goal,servo=decode_command(command,self.contract['lower_rad'],self.contract['upper_rad'])
        if self.entry_ready and self.hold_start is None:
            if self.entry_arm_hold is not None:goal[:5]=self.entry_arm_hold
            goal[-1]=np.clip(q[-1]-.04,self.inner.previous_q[-1]-.04,self.inner.previous_q[-1]+.04)
            servo=np.array([8.,.4]);note['visual_servo']['measured_closing_drive']=True
        elif self.hold_start is not None and not self.tray_release:
            goal[-1]=self.holding_jaw_target(q,now)
            servo=np.array([8.,.15]);note['visual_servo'].update(bounded_position_retention=True,
                captured_jaw_origin_rad=self.hold_jaw,maximum_additional_close_rad=.015)
        if self.guard_finished:
            previous=self.inner.previous_q;before=self.tool_pose(previous);after=self.tool_pose(goal)
            movement=float(np.linalg.norm(after[:3,3]-before[:3,3]));delta=goal[:5]-previous[:5]
            scale=min(1.,.00175/max(movement,1e-12),.015/max(np.max(np.abs(delta)),1e-12))
            goal[:5]=previous[:5]+delta*scale
            note['visual_servo'].update(postgrip_command_tcp_step_m=movement*scale,postgrip_command_scale=scale)
        goal[-1]=np.clip(goal[-1],self.contract['lower_rad'][-1],self.contract['upper_rad'][-1])
        note['visual_servo']['measured_closing_stall_s']=self.motor_stall_s
        note['visual_servo']['sampled_jaw_position_stopped']=bool(sampled_stop)
        return encode_command(goal,servo,self.contract['lower_rad'],self.contract['upper_rad']),note
