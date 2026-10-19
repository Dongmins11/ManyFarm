"""Native camera wrapper for the separate persistent-memory checkpoint family."""
import numpy as np
import torch
from .student60_controller import Student60Controller
from .student60 import TargetFilter
from harvest_rl.student60_recurrent import RecurrentCameraInference,FAMILY
from harvest_rl.student60_crop import crop_arrays,observed_box
from harvest_rl.student_v2 import measured_proprio
from harvest_rl.student_v3 import pack_observation


class CameraRecurrentController(Student60Controller):
    def __init__(self,checkpoint,contract,device='cpu'):
        self.policy=RecurrentCameraInference(checkpoint,contract,device)
        self.contract=contract;self.target_filter=TargetFilter(contract['box_from_arm'],contract['box_min'],contract['box_max'])
        self.target_id=None;self.pending=False

    def step(self,frames,q_rad,qd_rad_s,tcp_arm,target,now,capture):
        if self.pending:raise ValueError('Acknowledge before next step')
        if target['target_id']!=self.target_id:raise ValueError('Target changed without reset')
        if self.last_stamp is not None and abs(now-self.last_stamp-.05)>1e-6:raise ValueError('Require20Hz')
        filtered=self.target_filter.filter(target)
        proprio=measured_proprio(q_rad,qd_rad_s,self.previous,self.contract['lower_rad'],self.contract['upper_rad'])
        observation=pack_observation(frames,proprio,tcp_arm,filtered,now,capture)
        box=observed_box(filtered,capture.get('student_target_detections',[]))
        observation.update(crop_arrays(frames['rear'].rgb,frames['rear'].depth_m,box,filtered['valid'],now))
        command=self.policy.predict(observation,self.target_id)
        self.pending=True;self.tcp=np.asarray(tcp_arm,float).copy();self.last_stamp=now
        self.measured_jaw=float(q_rad[-1])
        return command,dict(target=filtered,release_latched=self.target_filter.released,
                            target_crop_valid=bool(observation['rear_target_valid']))


def make_controller(checkpoint,contract,device='cpu'):
    saved=torch.load(checkpoint,map_location='cpu',weights_only=True)
    if saved.get('model_family')==FAMILY:return CameraRecurrentController(checkpoint,contract,device)
    if saved.get('model_family') not in (None,'student60_absolute_v1'):raise ValueError('Unknown model family')
    return Student60Controller(checkpoint,contract,device)
