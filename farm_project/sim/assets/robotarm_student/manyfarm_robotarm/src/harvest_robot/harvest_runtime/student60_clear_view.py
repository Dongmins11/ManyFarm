"""Acquire an unoccluded camera prior before moving the harvesting arm.

Only fresh assigned detections and measured joints are consumed. Cached geometry
is private to the approach servo; the neural policy still sees its real target.
"""
import numpy as np
from .student60_camera_harvest import CameraHarvestController
from .student60_approach_anchor import ApproachAnchor,iou
from .student60 import encode_command,decode_command


class ClearViewAcquisition:
    def __init__(self):
        self.samples=[];self.complete=False;self.position=None;self.record=None;self.last_stamp=None
        self.joint_history=[];self.arm_stationary=False

    def update(self,target,records,qd,tcp,now,q_rad=None):
        if self.complete:return True
        self.arm_stationary=bool(np.max(np.abs(qd[:5]))<=.05)
        if q_rad is not None:
            self.joint_history.append((now,np.asarray(q_rad,float)[:5].copy()))
            self.joint_history=self.joint_history[-5:]
            self.arm_stationary=False
            if len(self.joint_history)==5:
                times,joints=zip(*self.joint_history);joints=np.stack(joints);duration=times[-1]-times[0]
                self.arm_stationary=bool(duration>=.19 and np.max(np.ptp(joints,axis=0))<.004
                    and np.max(np.abs(joints[-1]-joints[0]))/duration<.02)
        if (now<.15 or not target['valid'] or not 0<=target['age_s']<=.050001
                or not self.arm_stationary):return False
        point=np.asarray(target['position_m'],float)
        if np.linalg.norm(point-tcp)<.10:return False
        candidates=[r for r in records if r.get('candidate_valid') and r.get('confidence',0)>=.6
            and r.get('grasp_estimate_arm_m') is not None
            and np.linalg.norm(np.asarray(r['grasp_estimate_arm_m'])-point)<.035
            and 0<=now-r.get('stamp_s',-100)<.050001]
        if len(candidates)!=1:return False
        observed=candidates[0];stamp=observed['stamp_s']
        if self.last_stamp is not None and stamp<=self.last_stamp:return False
        self.last_stamp=stamp;self.samples.append((point.copy(),dict(observed)));self.samples=self.samples[-12:]
        if now<.65 or len(self.samples)<6:return False
        points=np.stack([x[0] for x in self.samples]);median=np.median(points,axis=0)
        inliers=np.linalg.norm(points-median,axis=1)<.01
        if inliers.sum()<6 or inliers.mean()<.75:return False
        points=points[inliers];median=np.median(points,axis=0)
        if np.median(np.linalg.norm(points-median,axis=1))>.004:return False
        self.position=median;self.record=observed;self.complete=True
        return True


class ClearViewAnchor(ApproachAnchor):
    def update(self,target,tcp,qjaw,records,now,finished):
        point,note=super().update(target,tcp,qjaw,records,now,finished)
        if point is not None or self.position is None or finished or now-self.stamp>8.:
            return point,note
        # A partial fruit mask may shrink suddenly as fingers enter. Continue
        # only with a unique overlapping fresh box; never fabricate a new NN
        # observation or use this point after the bounded approach/grip stage.
        support=[r for r in records if r.get('label')==self.label and r.get('confidence',0)>=.65
            and r.get('bbox') is not None and iou(r['bbox'],self.box)>=.12
            and 0<=now-r.get('stamp_s',-100)<=.050001]
        if len(support)!=1:return None,note
        self.box=support[0]['bbox'];note.update(active=True,bbox_stamp_s=support[0]['stamp_s'],
            source='stationary_clear_depth_and_unique_partial_bbox_for_servo_only')
        return self.position.copy(),note


class ClearViewCameraHarvestController(CameraHarvestController):
    def start(self,*args):
        super().start(*args)
        self.acquisition=ClearViewAcquisition();self.acquisition_arm=self.inner.previous_q[:5].copy()
        self.inner.anchor=ClearViewAnchor()

    def step(self,frames,q,qd,tcp,target,now,capture):
        acquiring=not self.acquisition.complete
        if acquiring:
            ready=self.acquisition.update(target,capture.get('student_target_detections',[]),np.asarray(qd),np.asarray(tcp),now,q_rad=q)
            if ready:
                anchor=self.inner.anchor;anchor.position=self.acquisition.position.copy()
                anchor.stamp=now;anchor.box=self.acquisition.record['bbox'];anchor.label=self.acquisition.record['label']
        command,note=super().step(frames,q,qd,tcp,target,now,capture)
        if acquiring:
            goal,servo=decode_command(command,self.contract['lower_rad'],self.contract['upper_rad'])
            goal[:5]=self.acquisition_arm
            goal[-1]=np.clip(1.5,self.inner.previous_q[-1]-.1,self.inner.previous_q[-1]+.1)
            command=encode_command(goal,servo,self.contract['lower_rad'],self.contract['upper_rad'])
            # A parent may have proposed an approach this tick, but the arm is
            # still stationary until acquisition completes and this is acked.
            self.pregrasp_plan=None;self.insertion_start=None;self.pregrasp_settle_s=0.
        note['visual_servo'].update(clear_view_acquisition_complete=self.acquisition.complete,
            clear_view_samples=len(self.acquisition.samples),initial_arm_hold=acquiring,
            acquisition_measured_arm_stationary=self.acquisition.arm_stationary)
        return command,note
