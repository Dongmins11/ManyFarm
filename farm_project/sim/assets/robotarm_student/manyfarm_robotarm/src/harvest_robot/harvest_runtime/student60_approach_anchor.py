"""Occlusion-aware approach servo with a clearly separated camera depth prior.

The neural policy always receives the original measured camera target, including
invalid/zero observations. Only the kinematic servo may use a cached attached-
fruit point, supported by a fresh, unambiguous bbox of the same observed fruit.
"""
import numpy as np
from .student60_retention_guard import RetainedGripController


def iou(a,b):
    a,b=np.asarray(a,float),np.asarray(b,float)
    intersection=np.maximum(0,np.minimum(a[2:],b[2:])-np.maximum(a[:2],b[:2])).prod()
    return float(intersection/max(np.maximum(0,a[2:]-a[:2]).prod()+np.maximum(0,b[2:]-b[:2]).prod()-intersection,1e-9))


class ApproachAnchor:
    def __init__(self):
        self.samples=[];self.position=None;self.stamp=None;self.box=None;self.label=None

    def update(self,target,tcp,qjaw,records,now,finished):
        note=dict(active=False,neural_target_unchanged=True)
        if finished:return None,note
        if self.position is None and target['valid'] and now>=.5:
            point=np.asarray(target['position_m'],float)
            candidates=[r for r in records if r.get('candidate_valid') and r.get('grasp_estimate_arm_m') is not None
                        and np.linalg.norm(np.asarray(r['grasp_estimate_arm_m'])-point)<.035]
            if len(candidates)==1:
                observed=candidates[0];distance=float(np.linalg.norm(point-tcp))
                if distance>.105:
                    self.samples.append((now,point.copy()));self.samples=self.samples[-5:]
                elif len(self.samples)>=3 and qjaw>1.35 and now-self.samples[-1][0]<.3:
                    self.position=np.median([p for _,p in self.samples],axis=0)
                    self.stamp=self.samples[-1][0];self.box=observed['bbox'];self.label=observed['label']
        if self.position is None:return None,note
        note.update(anchor_age_s=now-self.stamp,anchor_position_m=self.position.tolist())
        support=[r for r in records if r.get('label')==self.label and r.get('confidence',0)>=.6
                 and r.get('bbox') is not None and iou(r['bbox'],self.box)>=.3
                 and 0<=now-r.get('stamp_s',-float('inf'))<=.05+1e-8]
        if len(support)!=1 or now-self.stamp>8.:
            note['reason']='ambiguous_or_stale_bbox_support';return None,note
        self.box=support[0]['bbox'];note.update(active=True,bbox_stamp_s=support[0]['stamp_s'],
            source='cached_clear_depth_and_fresh_assigned_bbox_for_servo_only')
        return self.position.copy(),note


class AnchoredPolicyFacade:
    def __init__(self,inner):self.inner=inner;self.owner=None;self.anchor=ApproachAnchor();self.real_target=None
    def __getattr__(self,name):return getattr(self.inner,name)
    def start(self,*args):self.anchor=ApproachAnchor();self.inner.start(*args)
    def step(self,frames,q,qd,tcp,target,now,capture):
        command,note=self.inner.step(frames,q,qd,tcp,target,now,capture)
        self.real_target=dict(note['target'])
        point,report=self.anchor.update(self.real_target,np.asarray(tcp),q[-1],
            capture.get('student_target_detections',[]),now,self.owner.guard_finished)
        note['approach_anchor']=report
        if point is not None:
            # Private servo target only. It is restored before the caller records
            # the actual neural observation, validity and original camera age.
            note['target']=dict(self.real_target,position_m=point.tolist(),valid=True)
        return command,note


class AnchoredRetainedController(RetainedGripController):
    def __init__(self,controller,*args,**kwargs):
        facade=AnchoredPolicyFacade(controller)
        super().__init__(facade,*args,**kwargs);facade.owner=self
    def step(self,*args):
        command,note=super().step(*args)
        note['target']=self.inner.real_target
        note['visual_servo']['approach_anchor']=note.pop('approach_anchor')
        return command,note
