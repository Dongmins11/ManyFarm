"""Optional visual position servo around the learned camera policy.

Uses observed target, measured joints and public robot kinematics only. No
Teacher actor/controller, simulator fruit pose, contact flags, or task phase.
Its results are reported as an assisted policy, separately from pure inference.
"""
import numpy as np
from .student60 import encode_command,decode_command


class VisualServoController:
    def __init__(self,controller,kin,contract,body_center=False):
        self.inner,self.kin,self.contract=controller,kin,contract
        self.body_center=body_center
        self.arm_from_robot=np.linalg.inv(kin.fk(np.zeros(6),'arm_2/base_link'))
        self.up=np.linalg.inv(np.asarray(contract['box_from_arm']))[:3,:3]@np.array([0.,0.,1.])
        self.policy=controller.policy

    def start(self,target_id,initial_target_rad):
        self.inner.start(target_id,initial_target_rad)
        self.capture_s=0.;self.captured=False

    def pose(self,q):
        tcp=self.arm_from_robot@self.kin.grasp_fk(q,self.contract['task']['diameter'])
        gripper=self.arm_from_robot@self.kin.fk(q,'arm_2/gripper_link')
        return tcp[:3,3],float(gripper[:3,0]@self.up)

    def step(self,frames,q_rad,qd_rad_s,tcp_arm,target,now,capture):
        command,note=self.inner.step(frames,q_rad,qd_rad_s,tcp_arm,target,now,capture)
        raw=command.copy();q=np.asarray(q_rad,float);qd=np.asarray(qd_rad_s,float)
        self.measured_jaw=float(q[-1])
        goal,servo=decode_command(command,self.contract['lower_rad'],self.contract['upper_rad'])
        filtered=note['target'];report=dict(active=False,captured_proxy=self.captured,raw_neural_command=raw.tolist())
        if not filtered['valid'] or self.captured:
            note['visual_servo']=report;return command,note
        desired=np.asarray(filtered['position_m'],float)
        body_center=self.body_center
        if self.body_center:
            candidates=[r for r in capture.get('student_target_detections',[]) if r.get('candidate_valid') and r.get('grasp_estimate_arm_m') is not None]
            if candidates:
                observed=min(candidates,key=lambda r:np.linalg.norm(np.asarray(r['grasp_estimate_arm_m'])-desired))
                body_center=bool(observed.get('body_center_fit',{}).get('valid',False))
        if not body_center:desired=desired-self.up*(self.contract['task']['length']*.08)
        position,vertical=self.pose(q)
        fk_error=float(np.linalg.norm(position-tcp_arm))
        if fk_error>5e-4:raise ValueError('Servo FK differs from measured TCP; do not correct from wrong geometry')
        distance=float(np.linalg.norm(desired-position))
        stalled=bool(q[-1]-goal[-1]>.015 and abs(qd[-1])<.08 and distance<.03)
        self.capture_s=self.capture_s+.05 if stalled else 0.
        if self.capture_s>=.25:
            self.captured=True;report.update(captured_proxy=True,capture_proxy_s=self.capture_s)
            note['visual_servo']=report;return command,note
        if stalled:
            # Let contact settle rather than chasing a depth-centre shift as
            # the fruit becomes occluded by the jaws. This is a motor/vision
            # proxy, not an environment grasp flag or a success declaration.
            goal[:5]=self.inner.previous_q[:5]
            goal[:5]=np.clip(goal[:5],self.contract['lower_rad'][:5],self.contract['upper_rad'][:5])
            command=encode_command(goal,servo,self.contract['lower_rad'],self.contract['upper_rad'])
            report.update(active=True,settling_from_observed_stall=True,capture_proxy_s=self.capture_s)
            note['visual_servo']=report;return command,note
        jac=np.zeros((4,5));epsilon=1e-4
        for j in range(5):
            perturbed=q.copy();perturbed[j]+=epsilon
            moved,rotated=self.pose(perturbed)
            jac[:3,j]=(moved-position)/epsilon;jac[3,j]=.05*(rotated-vertical)/epsilon
        error=desired-position
        if distance<.004:error=np.zeros(3)
        elif distance>.004:error=error*.004/distance
        wanted=np.r_[error,-.05*np.clip(vertical,-.04,.04)]
        damping=.006
        previous=self.inner.previous_q[:5]
        prior=np.clip(goal[:5]-previous,-.04,.04)
        delta=np.linalg.solve(jac.T@jac+damping**2*np.eye(5),jac.T@wanted+damping**2*prior)
        # Preserve the coupled Cartesian/rotation cancellation. Independent
        # clipping changes the direction and can move away near a singularity.
        delta*=min(1.,.04/max(np.max(np.abs(delta)),1e-12))
        # Integrate around the last commanded goal. Anchoring each new goal to
        # measured q repeatedly discards the drive's gravity/load offset.
        corrected=previous+delta
        corrected=np.clip(corrected,previous-.04,previous+.04)
        goal[:5]=np.clip(corrected,self.contract['lower_rad'][:5],self.contract['upper_rad'][:5])
        command=encode_command(goal,servo,self.contract['lower_rad'],self.contract['upper_rad'])
        report.update(active=True,observed_target_distance_m=distance,closing_vertical_component=vertical,
                      fk_error_m=fk_error,capture_proxy_s=self.capture_s)
        note['visual_servo']=report
        return command,note

    def acknowledge(self,command):
        filter_=getattr(self.inner,'target_filter',None)
        released_before=filter_.released if filter_ is not None else False
        self.inner.acknowledge(command)
        goal,_=decode_command(command,self.contract['lower_rad'],self.contract['upper_rad'])
        if filter_ is not None and not released_before and goal[-1]<=self.measured_jaw+1e-4:
            # A goal tracking an opening load while remaining below the actual
            # jaw angle is still a closing drive, not observable tray release.
            filter_.opening=0.;filter_.released=False
