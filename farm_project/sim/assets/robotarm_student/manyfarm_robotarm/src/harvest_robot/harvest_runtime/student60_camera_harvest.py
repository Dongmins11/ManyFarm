"""Camera Student with explicit observed grasp and tray-servo assistance.

This is a hybrid controller, not a claim of pure neural harvest. Its transition
conditions use camera tracking, measured joints/TCP and public tray geometry.
No environment phase, grip/contact, fruit truth or attachment flags are read.
"""
import numpy as np
from .student60_observed_closure import ObservedClosureController
from .student60 import encode_command,decode_command


class CameraHarvestController(ObservedClosureController):
    def start(self,*args):
        super().start(*args)
        self.tray_waypoint=0;self.tray_settle_s=0.;self.tray_last_tcp=None
        self.release_begun=False;self.release_arm=None;self.final_stop_arm=None

    def step(self,frames,q,qd,tcp,target,now,capture):
        command,note=super().step(frames,q,qd,tcp,target,now,capture)
        if self.pull_started is None or now-self.pull_started<3.5:return command,note
        goal,servo=decode_command(command,self.contract['lower_rad'],self.contract['upper_rad'])
        pose=self.tool_pose(q);position=pose[:3,3]
        speed=np.linalg.norm(position-self.tray_last_tcp)/.05 if self.tray_last_tcp is not None else float('inf')
        self.tray_last_tcp=position.copy()
        if not self.release_begun:
            self.tray_release=False
            lo=np.asarray(self.contract['box_min']);hi=np.asarray(self.contract['box_max'])
            world=np.array([(lo[0]+hi[0])/2,(lo[1]+hi[1])/2,hi[2]+(.15 if self.tray_waypoint==0 else .07)])
            wanted=(np.linalg.inv(np.asarray(self.contract['box_from_arm']))@np.r_[world,1])[:3]
            _,vertical=self.pose(q);pitch=float(pose[:3,2]@self.up)
            error=float(np.linalg.norm(wanted-position))
            # Freeze a reached public tray window before accumulating stop
            # time. Continuing tiny corrections during the dwell had changed
            # the stopped hand position before the actual opening command.
            final=self.tray_waypoint==1
            aligned=abs(vertical)<.10 and abs(pitch+.35)<.12
            if final and self.final_stop_arm is None and error<.015 and aligned and speed<.025:
                self.final_stop_arm=self.inner.previous_q[:5].copy()
            reached=(error<(.025 if final else .004) and aligned and speed<.02
                     and (not final or self.final_stop_arm is not None))
            self.tray_settle_s=self.tray_settle_s+.05 if reached else 0.
            if self.tray_waypoint==0 and self.tray_settle_s>=.15-1e-6:
                self.tray_waypoint=1;self.tray_settle_s=0.
            elif self.tray_waypoint==1 and self.tray_settle_s>=.6-1e-6:
                self.release_begun=True;self.release_arm=self.inner.previous_q[:5].copy()
            jac=np.zeros((5,5));eps=1e-4
            for j in range(5):
                moved=np.asarray(q,float).copy();moved[j]+=eps;p=self.tool_pose(moved);_,v=self.pose(moved)
                jac[:3,j]=(p[:3,3]-position)/eps;jac[3,j]=.05*(v-vertical)/eps
                jac[4,j]=.05*(float(p[:3,2]@self.up)-pitch)/eps
            linear=(wanted-position)*.2;linear*=min(1.,.00175/max(np.linalg.norm(linear),1e-12))
            rotation=.05*np.clip(np.array([-vertical,-.35-pitch]),-.02,.02)
            delta=np.linalg.solve(jac.T@jac+.004**2*np.eye(5),jac.T@np.r_[linear,rotation])
            delta*=min(1.,.015/max(np.max(np.abs(delta)),1e-12),.00175/max(np.linalg.norm(jac[:3]@delta),1e-12))
            goal[:5]=np.clip(self.inner.previous_q[:5]+delta,self.contract['lower_rad'][:5],self.contract['upper_rad'][:5])
            if self.final_stop_arm is not None:goal[:5]=self.final_stop_arm
            goal[-1]=self.holding_jaw_target(q,now);servo=np.array([8.,.15])
            note['visual_servo'].update(observed_tray_servo=True,own_tray_waypoint=self.tray_waypoint,
                own_tray_error_m=error,own_measured_stop_s=self.tray_settle_s,
                own_tray_tcp_speed_m_s=float(speed),own_tool_pitch_vertical=pitch)
            note['visual_servo']['observed_tray_arm_frozen']=self.final_stop_arm is not None
        if self.release_begun:
            self.tray_release=True;goal[:5]=self.release_arm
            goal[-1]=min(1.5,self.inner.previous_q[-1]+.015);servo=np.array([1.,.3])
            note['visual_servo']['observed_stopped_tray_opening']=True
        goal[-1]=np.clip(goal[-1],self.contract['lower_rad'][-1],self.contract['upper_rad'][-1])
        return encode_command(goal,servo,self.contract['lower_rad'],self.contract['upper_rad']),note
