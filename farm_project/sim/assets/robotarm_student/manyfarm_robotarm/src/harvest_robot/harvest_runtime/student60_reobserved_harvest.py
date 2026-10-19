"""Reobserve from a stationary pregrasp before committing to insertion.

The camera policy receives its actual current observation throughout. A separate
servo prior is measured again after the arm has moved out of the HOME view. No
simulator object poses, contacts, attachment flags, or Teacher are consulted.
"""
import numpy as np
from scipy.optimize import least_squares
from scipy.spatial.transform import Rotation
from .student60_lifted_harvest import LiftedCameraHarvestController
from .student60_clear_view import ClearViewAnchor
from .student60_approach_anchor import iou
from .student60 import encode_command, decode_command


class PregraspObservation:
    def __init__(self):
        self.joints=[];self.samples=[];self.last_stamp=None;self.position=None;self.record=None

    def update(self,q,target,records,now,reference,label,assigned_record=None):
        self.joints.append(np.asarray(q,float)[:5].copy());self.joints=self.joints[-5:]
        if (len(self.joints)<5 or np.max(np.ptp(self.joints,axis=0))>=.004
                or q[-1]<1.4 or not target['valid'] or not 0<=target['age_s']<=.050001):
            self.samples=[];return False
        point=np.asarray(target['position_m'],float)
        if np.linalg.norm(point-reference)>.04:return False
        records=[assigned_record] if assigned_record is not None else records
        confidence=.5 if assigned_record is not None else .65
        candidates=[r for r in records if r.get('label')==label and r.get('candidate_valid')
            and r.get('confidence',0)>=confidence and r.get('grasp_estimate_arm_m') is not None
            and np.linalg.norm(np.asarray(r['grasp_estimate_arm_m'])-point)<.035
            and 0<=now-r.get('stamp_s',-100)<=.050001]
        if len(candidates)!=1:return False
        record=candidates[0];stamp=record['stamp_s']
        if self.last_stamp is not None and stamp<=self.last_stamp:return False
        self.last_stamp=stamp;self.samples.append(point.copy());self.samples=self.samples[-12:]
        if len(self.samples)<8:return False
        points=np.stack(self.samples);median=np.median(points,axis=0)
        inliers=np.linalg.norm(points-median,axis=1)<.008
        if inliers.sum()<8 or inliers.mean()<.8:return False
        points=points[inliers];median=np.median(points,axis=0)
        if np.median(np.linalg.norm(points-median,axis=1))>.003:return False
        self.position=median;self.record=record
        return True


class AssignedViewAnchor(ClearViewAnchor):
    assigned_record=None

    def update(self,target,tcp,qjaw,records,now,finished):
        point,note=super().update(target,tcp,qjaw,records,now,finished)
        if point is not None or self.position is None or finished or now-self.stamp>12.:
            return point,note
        r=self.assigned_record
        if (r is None or r.get('label')!=self.label or not r.get('candidate_valid')
                or r.get('confidence',0)<.5 or not 0<=now-r.get('stamp_s',-100)<=.050001
                or r.get('bbox') is None or iou(r['bbox'],self.box)<.12):return None,note
        self.box=r['bbox'];note.update(active=True,bbox_stamp_s=r['stamp_s'],
            source='fresh_tracker_assigned_bbox_supports_private_reobserved_servo_prior')
        return self.position.copy(),note


class ReobservedCameraHarvestController(LiftedCameraHarvestController):
    def start(self,*args):
        super().start(*args)
        # Public arm-frame pose: retract to the other side and below the fruit
        # region. The previous elevated pose put the wrist camera over Yellow.
        reference=self.inner.previous_q[:5].copy();wanted=np.array([.10,-.16,.18])
        def residual(arm):
            return np.r_[self.tool_pose(np.r_[arm,1.5])[:3,3]-wanted,.002*(arm-reference)]
        solved=least_squares(residual,reference,bounds=(self.contract['lower_rad'][:5],self.contract['upper_rad'][:5]),
            max_nfev=300,xtol=1e-10,ftol=1e-10,gtol=1e-10)
        if np.linalg.norm(residual(solved.x)[:3])>.004:raise ValueError('Reobservation posture is unreachable')
        self.view_goal=solved.x;self.refined=False;self.refining=False
        self.refinement=PregraspObservation();self.refinement_started=None
        self.waypoint_complete=False

    def plan(self,q,root):
        # Select the established elbow-up grasp branch independently of the
        # sideways viewing posture. Five joints cannot maintain an arbitrary
        # six-dimensional tool pose along the whole sideways Cartesian line.
        reference=np.array([-.7,-1.5,.6,.5,.2,1.5])
        plan=super().plan(reference,root)
        def residual(arm):
            pose=self.tool_pose(np.r_[arm,1.5])
            rotation=Rotation.from_matrix(plan['rotation']@pose[:3,:3].T).as_rotvec()
            return np.r_[pose[:3,3]-plan['pregrasp'],.04*rotation,.00005*(arm-reference[:5])]
        solved=least_squares(residual,reference[:5],bounds=(self.contract['lower_rad'][:5],self.contract['upper_rad'][:5]),
            max_nfev=300,xtol=1e-10,ftol=1e-10,gtol=1e-10)
        error=residual(solved.x)
        plan.update(valid=bool(plan['valid'] and np.linalg.norm(error[:3])<.003
            and np.linalg.norm(error[3:6])/.04<.08),pregrasp_joint_goal=solved.x.copy(),
            pregrasp_waypoint_fk_error_m=float(np.linalg.norm(error[:3])))
        self.waypoint_complete=False
        return plan

    def step(self,frames,q,qd,tcp,target,now,capture):
        if not isinstance(self.inner.anchor,AssignedViewAnchor):
            anchor=AssignedViewAnchor();anchor.__dict__.update(vars(self.inner.anchor));self.inner.anchor=anchor
        self.inner.anchor.assigned_record=capture.get('student_assigned_detection')
        # Parent first reaches its 60mm pregrasp; insertion is then held until
        # a new stationary multiframe measurement has been accepted.
        if self.refining and not self.refined:
            self.insertion_start=None
        command,note=super().step(frames,q,qd,tcp,target,now,capture)
        plan=self.pregrasp_plan
        if (not self.entry_ready and self.acquisition.complete and plan is not None
                and plan['valid'] and not self.waypoint_complete):
            goal,servo=decode_command(command,self.contract['lower_rad'],self.contract['upper_rad'])
            previous=self.inner.previous_q.copy();delta=plan['pregrasp_joint_goal']-previous[:5]
            delta*=min(1.,.025/max(np.max(np.abs(delta)),1e-12))
            proposal=previous.copy();proposal[:5]+=delta
            travel=np.linalg.norm(self.tool_pose(proposal)[:3,3]-self.tool_pose(previous)[:3,3])
            delta*=min(1.,.003/max(travel,1e-12))
            goal[:5]=previous[:5]+delta;goal[-1]=1.5
            self.waypoint_complete=bool(np.max(np.abs(goal[:5]-plan['pregrasp_joint_goal']))<1e-5)
            self.insertion_start=None;self.pregrasp_settle_s=0.
            note['visual_servo'].update(pregrasp_joint_waypoint=True,
                pregrasp_waypoint_command_complete=self.waypoint_complete,
                pregrasp_waypoint_fk_error_m=plan['pregrasp_waypoint_fk_error_m'])
            command=encode_command(goal,servo,self.contract['lower_rad'],self.contract['upper_rad'])
        if not self.refined and (self.refining or self.insertion_start is not None) and not self.entry_ready:
            if not self.refining:
                self.refining=True;self.refinement_started=now
            anchor=self.inner.anchor
            ready=self.refinement.update(q,note['target'],capture.get('student_target_detections',[]),now,
                anchor.position,anchor.label,assigned_record=capture.get('student_assigned_detection'))
            goal,servo=decode_command(command,self.contract['lower_rad'],self.contract['upper_rad'])
            goal[:5]=self.inner.previous_q[:5];goal[-1]=1.5
            self.insertion_start=None;self.pregrasp_settle_s=0.
            if ready:
                anchor.position=self.refinement.position.copy();anchor.stamp=now
                anchor.box=self.refinement.record['bbox'];anchor.label=self.refinement.record['label']
                self.pregrasp_plan=self.plan(q,anchor.position)
                self.refined=True
            command=encode_command(goal,servo,self.contract['lower_rad'],self.contract['upper_rad'])
        note['visual_servo'].update(pregrasp_reobserved=self.refined,
            pregrasp_reobservation_active=self.refining and not self.refined,
            pregrasp_reobservation_samples=len(self.refinement.samples),
            pregrasp_reobservation_position_m=None if self.refinement.position is None else self.refinement.position.tolist())
        return command,note
