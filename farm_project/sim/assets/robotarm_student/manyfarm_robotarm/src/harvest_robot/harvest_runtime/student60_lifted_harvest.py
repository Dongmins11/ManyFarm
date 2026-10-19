"""Lift clear of the work surface before lateral camera-guided placement."""
import numpy as np
from scipy.spatial.transform import Rotation
from .student60_active_view import ActiveViewCameraHarvestController
from .student60_observed_closure import ObservedClosureController
from .student60 import encode_command,decode_command


class LiftedCameraHarvestController(ActiveViewCameraHarvestController):
    def start(self,*args):
        super().start(*args)
        self.transfer_phase=None;self.transfer_dwell=0.;self.transfer_last=None
        self.transfer_origin=None;self.transfer_rotation=None;self.transfer_stop_arm=None;self.place_open=False

    def step(self,frames,q,qd,tcp,target,now,capture):
        if self.pull_started is None or now-self.pull_started<3.5:
            return super().step(frames,q,qd,tcp,target,now,capture)
        self.tray_release=self.place_open
        command,note=ObservedClosureController.step(self,frames,q,qd,tcp,target,now,capture)
        self.tray_release=self.place_open
        goal,servo=decode_command(command,self.contract['lower_rad'],self.contract['upper_rad'])
        pose=self.tool_pose(q);position=pose[:3,3]
        world_from_arm=np.asarray(self.contract['box_from_arm']);arm_from_world=np.linalg.inv(world_from_arm)
        current_world=(world_from_arm@np.r_[position,1])[:3]
        lo=np.asarray(self.contract['box_min']);hi=np.asarray(self.contract['box_max'])
        if self.transfer_phase is None:
            self.transfer_phase='lift';self.transfer_origin=current_world.copy();self.transfer_rotation=pose[:3,:3].copy()
        speed=float('inf') if self.transfer_last is None else float(np.linalg.norm(position-self.transfer_last)/.05)
        self.transfer_last=position.copy()
        high=max(float(self.transfer_origin[2]),float(hi[2]+.20))
        world=np.r_[self.transfer_origin[:2],high] if self.transfer_phase=='lift' else np.r_[(lo[:2]+hi[:2])/2,high if self.transfer_phase=='across' else hi[2]+.075]
        wanted=(arm_from_world@np.r_[world,1])[:3]
        error=float(np.linalg.norm(wanted-position));_,vertical=self.pose(q);pitch=float(pose[:3,2]@self.up)
        lifting=self.transfer_phase=='lift'
        rotation_error=Rotation.from_matrix(self.transfer_rotation@pose[:3,:3].T).as_rotvec()
        orientation_ok=np.linalg.norm(rotation_error)<.10 if lifting else abs(vertical)<.10 and abs(pitch+.35)<.12
        if self.transfer_phase=='lower' and self.transfer_stop_arm is None and error<.010 and orientation_ok and speed<.025:
            self.transfer_stop_arm=self.inner.previous_q[:5].copy()
        reached=(error<(.020 if self.transfer_stop_arm is not None else .006) and orientation_ok and speed<.02)
        self.transfer_dwell=self.transfer_dwell+.05 if reached else 0.
        if self.transfer_phase in ['lift','across'] and self.transfer_dwell>=.15-1e-6:
            self.transfer_phase='across' if lifting else 'lower';self.transfer_dwell=0.
        elif self.transfer_phase=='lower' and self.transfer_dwell>=.6-1e-6:
            self.place_open=True;self.tray_release=True;self.release_begun=True
        if not self.place_open:
            rows=6 if lifting else 5;jac=np.zeros((rows,5));eps=1e-4;length=.04
            for j in range(5):
                moved=np.asarray(q,float).copy();moved[j]+=eps;p=self.tool_pose(moved);_,v=self.pose(moved)
                jac[:3,j]=(p[:3,3]-position)/eps
                if lifting:jac[3:,j]=length*Rotation.from_matrix(p[:3,:3]@pose[:3,:3].T).as_rotvec()/eps
                else:
                    jac[3,j]=length*(v-vertical)/eps;jac[4,j]=length*(float(p[:3,2]@self.up)-pitch)/eps
            linear=(wanted-position)*.25;linear*=min(1.,.0025/max(np.linalg.norm(linear),1e-12))
            if lifting:
                angular=rotation_error*.25;angular*=min(1.,.025/max(np.linalg.norm(angular),1e-12));rhs=np.r_[linear,length*angular]
            else:rhs=np.r_[linear,length*np.clip([-vertical,-.35-pitch],-.025,.025)]
            delta=np.linalg.solve(jac.T@jac+.004**2*np.eye(5),jac.T@rhs)
            delta*=min(1.,.02/max(np.max(np.abs(delta)),1e-12),.0025/max(np.linalg.norm(jac[:3]@delta),1e-12))
            goal[:5]=np.clip(self.inner.previous_q[:5]+delta,self.contract['lower_rad'][:5],self.contract['upper_rad'][:5])
            if self.transfer_stop_arm is not None:goal[:5]=self.transfer_stop_arm
            goal[-1]=self.holding_jaw_target(q,now);servo=np.array([8.,.15])
        else:
            goal[:5]=self.transfer_stop_arm
            goal[-1]=min(1.5,self.inner.previous_q[-1]+.015);servo=np.array([1.,.3])
        note['visual_servo'].update(observed_transfer_phase=self.transfer_phase,
            observed_transfer_error_m=error,observed_transfer_dwell_s=self.transfer_dwell,
            observed_transfer_speed_m_s=speed,lift_clearance_world_m=high,observed_stopped_tray_opening=self.place_open)
        return encode_command(goal,servo,self.contract['lower_rad'],self.contract['upper_rad']),note
