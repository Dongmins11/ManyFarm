"""Active clear-view acquisition and gentle position-based camera harvesting.

Uses only fresh image detections, measured joints and public URDF/task geometry.
The camera prior is acquired after a bounded retract/side-step of the arm. Near
the nominal fruit width, close slowly and freeze at observed motor deceleration
instead of waiting for a complete motor stall against a compliant object.
"""
import numpy as np
from scipy.optimize import least_squares
from .student60_clear_view import ClearViewCameraHarvestController,ClearViewAcquisition,ClearViewAnchor
from .student60 import encode_command,decode_command


def nominal_jaw_gap(q):
    # Public SO101 opposing-pad pivot geometry; no fruit/contact state.
    return .0281*(1-np.cos(q))+.0616*np.sin(q)


class GentleContactObserver:
    def __init__(self):self.previous=None;self.hold_s=0.
    def update(self,q,previous_goal,diameter):
        rate=None if self.previous is None else (float(q)-self.previous)/.05
        self.previous=float(q)
        loaded=(rate is not None and -.10<rate<.10 and q-previous_goal>.010
                and q>.25 and nominal_jaw_gap(q)<diameter+.006)
        self.hold_s=self.hold_s+.05 if loaded else 0.
        return self.hold_s>=.10-1e-6


class ActiveViewCameraHarvestController(ClearViewCameraHarvestController):
    def __init__(self,*args,**kwargs):
        kwargs['entry_tolerance_m']=.003
        super().__init__(*args,**kwargs)

    def start(self,*args):
        super().start(*args)
        reference=self.inner.previous_q.copy();reference[-1]=1.5
        wanted=np.array([.12,.08,.35])
        def residual(arm):
            q=np.r_[arm,1.5];point=self.tool_pose(q)[:3,3]
            return np.r_[point-wanted,.002*(arm-reference[:5])]
        solved=least_squares(residual,reference[:5],bounds=(self.contract['lower_rad'][:5],self.contract['upper_rad'][:5]),
            max_nfev=300,xtol=1e-10,ftol=1e-10,gtol=1e-10)
        if np.linalg.norm(residual(solved.x)[:3])>.004:raise ValueError('Public clear-view posture is unreachable')
        self.view_goal=solved.x;self.view_reached=False;self.view_q_history=[]
        self.gentle_contact=GentleContactObserver()

    def holding_jaw_target(self,q,now):
        desired=self.hold_jaw-min(.008,.008*max(0.,now-self.hold_start))
        desired=max(desired,float(q[-1])-.04)
        return float(np.clip(desired,self.inner.previous_q[-1]-.015,self.inner.previous_q[-1]+.015))

    def step(self,frames,q,qd,tcp,target,now,capture):
        viewing=not self.view_reached
        if viewing:
            # Prevent acquisition of the hand-occluded HOME fruit while the
            # camera-clearing move is still being commanded.
            self.acquisition=ClearViewAcquisition();self.inner.anchor=ClearViewAnchor()
        elif self.entry_ready and self.hold_start is None:
            loaded=self.gentle_contact.update(q[-1],self.inner.previous_q[-1],self.contract['task']['diameter'])
            if loaded:
                self.hold_start=now;self.hold_arm=self.inner.previous_q[:5].copy()
                self.hold_jaw=float(self.inner.previous_q[-1]);self.captured=True
        else:self.gentle_contact.previous=float(q[-1])
        command,note=super().step(frames,q,qd,tcp,target,now,capture)
        goal,servo=decode_command(command,self.contract['lower_rad'],self.contract['upper_rad'])
        if viewing:
            delta=self.view_goal-self.inner.previous_q[:5]
            delta*=min(1.,.025/max(np.max(np.abs(delta)),1e-12))
            goal[:5]=self.inner.previous_q[:5]+delta
            goal[-1]=np.clip(1.5,self.inner.previous_q[-1]-.1,self.inner.previous_q[-1]+.1)
            self.acquisition_arm=goal[:5].copy()
            self.pregrasp_plan=None;self.insertion_start=None;self.pregrasp_settle_s=0.
            self.view_q_history.append(np.asarray(q,float)[:5].copy());self.view_q_history=self.view_q_history[-5:]
            stopped=(len(self.view_q_history)==5 and np.max(np.ptp(self.view_q_history,axis=0))<.004)
            self.view_reached=bool(np.max(np.abs(goal[:5]-self.view_goal))<1e-5 and stopped)
            if self.view_reached:self.acquisition=ClearViewAcquisition();self.inner.anchor=ClearViewAnchor()
        elif self.entry_ready and self.hold_start is None:
            slow=bool(nominal_jaw_gap(q[-1])<self.contract['task']['diameter']+.010)
            speed=.15 if slow else .4;lead=.015 if slow else .04
            if self.entry_arm_hold is not None:goal[:5]=self.entry_arm_hold
            goal[-1]=np.clip(q[-1]-lead,self.inner.previous_q[-1]-speed*.05,self.inner.previous_q[-1]+speed*.05)
            servo=np.array([8.,speed])
            note['visual_servo'].update(geometry_gentle_closing=slow,commanded_closing_speed_rad_s=speed)
        elif self.hold_start is not None and now-self.hold_start<2.6:
            # This controller's own observed contact clock includes acquisition
            # and settling margin. Parent proposals never reach the plant here.
            self.guard_finished=False;self.pull_started=None;self.pull_origin=None;self.pull_rotation=None
            goal[:5]=self.hold_arm;goal[-1]=self.holding_jaw_target(q,now);servo=np.array([8.,.15])
            note['visual_servo']['gentle_stable_hold_remaining_s']=2.6-(now-self.hold_start)
        goal[-1]=np.clip(goal[-1],self.contract['lower_rad'][-1],self.contract['upper_rad'][-1])
        note['visual_servo'].update(active_view_pose_reached=self.view_reached,
            active_view_joint_step_max_rad=.025,gentle_contact_proxy_s=self.gentle_contact.hold_s)
        return encode_command(goal,servo,self.contract['lower_rad'],self.contract['upper_rad']),note
