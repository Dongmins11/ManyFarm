"""New timing contract around preserved weights and public/encoder assistance.

The neural target still uses its frozen50ms validity rule. Helper-only target
ages are explicit and recorded. A missed neural interval resets recurrent memory
instead of manufacturing20Hz timestamps. All input ages remain real clock ages.
"""
import numpy as np
import torch
from harvest_rl.student60_recurrent import RecurrentCameraInference
from harvest_rl.student60_crop import crop_arrays,observed_box
from harvest_rl.student_v2 import measured_proprio
from harvest_rl.student_v3 import pack_observation
from ..student60 import TargetFilter,decode_command
from ..student60_contract import encode_targets
from ..student60_camera_controller import CameraRecurrentController
from ..student60_faster_capture import FasterCaptureCameraHarvestController
from ..student60_clear_view import ClearViewAcquisition
from ..student60_reobserved_harvest import PregraspObservation
from ..student60_side_scan import SideScanInsertionAnchor
from ..student60_approach_anchor import iou


class GapAwareInference(RecurrentCameraInference):
    def reset(self):
        super().reset();self.gap_resets=0

    def predict(self,observation,target_id):
        if not target_id:raise ValueError('Assigned target required')
        if target_id!=self.target_id:self.reset();self.target_id=target_id
        if self.previous is not None and not np.allclose(observation['state'][12:18],self.previous,atol=1e-6):
            raise ValueError('Previous command must be actually applied')
        now=float(observation['elapsed_s'])
        if self.last_time is not None:
            if now<=self.last_time:raise ValueError('Policy clock did not advance')
            if now-self.last_time>.075:self.hidden=None;self.gap_resets+=1
        with torch.inference_mode():
            commands,self.hidden=self.model(**{k:torch.as_tensor(v[None,None],device=self.device) for k,v in observation.items()},
                hidden=self.hidden,return_hidden=True)
        self.last_time=now;command=commands[0,0].cpu().numpy()
        decode_command(command,self.contract['lower_rad'],self.contract['upper_rad'])
        return command


class ElapsedTargetFilter(TargetFilter):
    def observe_command(self,previous_target,target,tcp_arm,dt=.05):
        if not 0<dt<=10:raise ValueError('Invalid actual acknowledgement interval')
        p=(self.box_from_arm@np.r_[np.asarray(tcp_arm,float),1])[:3]
        zone=bool(np.all(p[:2]>=self.lo[:2]-.06) and np.all(p[:2]<=self.hi[:2]+.06)
            and self.hi[2]-.04<=p[2]<=self.hi[2]+.18)
        speed=float('inf') if self.last is None else np.linalg.norm(p-self.last)/dt
        self.still_s=self.still_s+dt if zone and speed<=.03 else 0.;self.last=p
        delta=float(target[-1]-previous_target[-1])
        self.opening=max(0.,self.opening+delta) if zone and self.still_s>=.15 else 0.
        if self.opening>=.012:self.released=True


class TimingCore(CameraRecurrentController):
    def __init__(self,checkpoint,contract,device='cpu',helper_age=.15):
        self.policy=GapAwareInference(checkpoint,contract,device);self.contract=contract
        self.target_filter=ElapsedTargetFilter(contract['box_from_arm'],contract['box_min'],contract['box_max'])
        self.helper_age=helper_age;self.target_id=None;self.pending=False;self.last_ack_s=None
        self.warmup()

    def warmup(self):
        """Prime actual model kernels before enabling the timing clock; no state/history changes."""
        device=self.policy.device
        shapes={'rgb':((1,1,2,90,160,3),torch.uint8),'depth_m':((1,1,2,90,160),torch.float32),
            'camera_valid':((1,1,2),torch.bool),'state':((1,1,23),torch.float32),
            'wrist_ir_right':((1,1,90,160),torch.uint8),'wrist_ir_valid':((1,1),torch.bool),
            'rear_target_rgb':((1,1,96,96,3),torch.uint8),'rear_target_depth':((1,1,96,96),torch.float32),
            'rear_target_valid':((1,1),torch.bool),'elapsed_s':((1,1),torch.float32)}
        observation={name:torch.zeros(shape,dtype=dtype,device=device) for name,(shape,dtype) in shapes.items()}
        with torch.inference_mode():
            for _ in range(2):self.policy.model(**observation)
        if str(device).startswith('cuda'):torch.cuda.synchronize(device)

    def start(self,*args):super().start(*args);self.last_ack_s=None

    def step(self,frames,q,qd,tcp,target,now,capture):
        if self.pending:raise ValueError('Acknowledge actual execution before new inference')
        if target['target_id']!=self.target_id:raise ValueError('Assignment changed')
        if self.last_stamp is not None and now<=self.last_stamp:raise ValueError('Controller clock regressed')
        neural=self.target_filter.filter(target)
        observation=pack_observation(frames,measured_proprio(q,qd,self.previous,self.contract['lower_rad'],self.contract['upper_rad']),
            np.asarray(tcp,float).copy(),neural,now,capture)
        observation.update(crop_arrays(frames['rear'].rgb,frames['rear'].depth_m,
            observed_box(neural,capture.get('student_target_detections',[])),neural['valid'],now))
        command=self.policy.predict(observation,self.target_id)
        self.pending=True;self.tcp=np.asarray(tcp,float).copy();self.last_stamp=now;self.measured_jaw=float(q[-1])
        age=float(target['age_s']);helper=dict(target)
        helper['valid']=bool(target['valid'] and not self.target_filter.released and np.isfinite(age) and 0<=age<=self.helper_age)
        if not helper['valid']:helper['position_m']=[0.,0.,0.]
        return command,dict(target=helper,neural_target=neural,release_latched=self.target_filter.released,
            target_crop_valid=bool(observation['rear_target_valid']),timing_contract='real_elapsed_gap_reset_helper_age_v1',
            recurrent_gap_resets=self.policy.gap_resets)

    def acknowledge_at(self,command,now):
        if not self.pending:raise ValueError('No pending prediction')
        q,_=decode_command(command,self.contract['lower_rad'],self.contract['upper_rad'])
        dt=.05 if self.last_ack_s is None else now-self.last_ack_s
        self.target_filter.observe_command(self.previous_q,q,self.tcp,dt=dt)
        if self.measured_jaw is not None and q[-1]<=self.measured_jaw+1e-4:
            self.target_filter.opening=0.;self.target_filter.released=False
        self.previous_q=q;self.previous=np.asarray(command[:6]).copy();self.policy.acknowledge(command)
        self.pending=False;self.last_ack_s=now

    def acknowledge(self,command):
        if not hasattr(self,'dispatch_stamp'):raise ValueError('Actual dispatch stamp required')
        self.acknowledge_at(command,self.dispatch_stamp)


class TimedAcquisition(ClearViewAcquisition):
    def __init__(self,max_age):super().__init__();self.max_age=max_age

    def update(self,target,records,qd,tcp,now,q_rad=None):
        if self.complete:return True
        if q_rad is None:return False
        self.joint_history.append((now,np.asarray(q_rad,float)[:5].copy()));self.joint_history=self.joint_history[-5:]
        self.arm_stationary=False
        if len(self.joint_history)==5:
            times,joints=zip(*self.joint_history);duration=times[-1]-times[0];joints=np.stack(joints)
            self.arm_stationary=bool(duration>=.19 and np.max(np.ptp(joints,axis=0))<.004
                and np.max(np.abs(joints[-1]-joints[0]))/duration<.02)
        if now<.15 or not target['valid'] or not 0<=target['age_s']<=self.max_age or not self.arm_stationary:return False
        point=np.asarray(target['position_m'],float)
        if np.linalg.norm(point-tcp)<.10:return False
        candidates=[r for r in records if r.get('candidate_valid') and r.get('confidence',0)>=.6
            and r.get('grasp_estimate_arm_m') is not None and np.linalg.norm(np.asarray(r['grasp_estimate_arm_m'])-point)<.035
            and 0<=now-r.get('stamp_s',-100)<=self.max_age]
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
        self.position=median;self.record=observed;self.complete=True;return True


class TimedRefinement(PregraspObservation):
    def __init__(self,max_age):super().__init__();self.max_age=max_age

    def update(self,q,target,records,now,reference,label,assigned_record=None):
        self.joints.append(np.asarray(q,float)[:5].copy());self.joints=self.joints[-5:]
        if (len(self.joints)<5 or np.max(np.ptp(self.joints,axis=0))>=.004 or q[-1]<1.4
                or not target['valid'] or not 0<=target['age_s']<=self.max_age):self.samples=[];return False
        point=np.asarray(target['position_m'],float)
        if np.linalg.norm(point-reference)>.04:return False
        records=[assigned_record] if assigned_record is not None else records
        confidence=.5 if assigned_record is not None else .65
        candidates=[r for r in records if r.get('label')==label and r.get('candidate_valid')
            and r.get('confidence',0)>=confidence and r.get('grasp_estimate_arm_m') is not None
            and np.linalg.norm(np.asarray(r['grasp_estimate_arm_m'])-point)<.035 and 0<=now-r.get('stamp_s',-100)<=self.max_age]
        if len(candidates)!=1:return False
        record=candidates[0];stamp=record['stamp_s']
        if self.last_stamp is not None and stamp<=self.last_stamp:return False
        self.last_stamp=stamp;self.samples.append(point.copy());self.samples=self.samples[-12:]
        if len(self.samples)<8:return False
        points=np.stack(self.samples);median=np.median(points,axis=0);inliers=np.linalg.norm(points-median,axis=1)<.008
        if inliers.sum()<8 or inliers.mean()<.8:return False
        points=points[inliers];median=np.median(points,axis=0)
        if np.median(np.linalg.norm(points-median,axis=1))>.003:return False
        self.position=median;self.record=record;return True


class TimedAnchor(SideScanInsertionAnchor):
    max_age=.15
    def update(self,target,tcp,qjaw,records,now,finished):
        point,note=super().update(target,tcp,qjaw,records,now,finished)
        if point is not None or self.position is None or finished:return point,note
        r=self.assigned_record
        if (r is not None and r.get('label')==self.label and r.get('confidence',0)>=.5
                and r.get('bbox') is not None and 0<=now-r.get('stamp_s',-100)<=self.max_age
                and iou(r['bbox'],self.box)>=.12 and now-self.stamp<=8.):
            self.box=r['bbox'];note.update(active=True,bbox_stamp_s=r['stamp_s'],
                source='timed_assigned_bbox_support_private_prior',point_age_s=now-self.stamp)
            return self.position.copy(),note
        return None,note


def phase_from_note(note):
    v=note.get('visual_servo',{})
    if v.get('observed_stopped_tray_opening'):return 'release'
    if v.get('observed_transfer_phase') or v.get('observed_tray_servo'):return 'transfer'
    if v.get('bounded_camera_pull'):return 'pull'
    if v.get('captured_proxy'):return 'hold'
    if v.get('entry_ready'):return 'close'
    if not v.get('active_view_pose_reached',False):return 'view'
    if v.get('pregrasp_reobservation_active') or not v.get('clear_view_acquisition_complete',False):return 'observe'
    if v.get('insertion_fraction',0)>0:return 'insert'
    return 'approach'


class TimingAssistedController(FasterCaptureCameraHarvestController):
    def __init__(self,core,kin,contract,profile,**kwargs):
        self.timing_core=core;self.timing_profile=profile
        super().__init__(core,kin,contract,**kwargs)

    def _install_observers(self):
        age=self.timing_core.helper_age
        if not isinstance(self.acquisition,TimedAcquisition):
            value=TimedAcquisition(age);value.__dict__.update(vars(self.acquisition));value.max_age=age;self.acquisition=value
        self.acquisition.max_age=age
        if not isinstance(self.refinement,TimedRefinement):
            value=TimedRefinement(age);value.__dict__.update(vars(self.refinement));value.max_age=age;self.refinement=value
        self.refinement.max_age=age
        if not isinstance(self.inner.anchor,TimedAnchor):
            value=TimedAnchor();value.__dict__.update(vars(self.inner.anchor));self.inner.anchor=value
        self.inner.anchor.max_age=age

    def start(self,*args):super().start(*args);self._install_observers();self.last_timing_note={}

    def step(self,*args):
        phase=phase_from_note(self.last_timing_note)
        self.timing_core.helper_age=self.timing_profile.phase_age.get(phase,.15)
        self._install_observers();command,note=super().step(*args);self._install_observers()
        self.last_timing_note=note;return command,note

    def acknowledge_at(self,command,now):
        self.timing_core.dispatch_stamp=now
        super().acknowledge(command)
