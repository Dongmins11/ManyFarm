"""Learned camera-centre preprocessing shared by training and live Student input.

This family preserves the recurrent architecture and eight-command boundary,
but explicitly requires the camera-only centre estimator in both data and live
observations. An old raw-input controller must reject these checkpoints.
"""
import numpy as np
import torch
from harvest_rl.student60_recurrent import RecurrentCameraInference,RecurrentCameraStudent
from harvest_rl.student60_crop import EXTENSION as CROP_EXTENSION
from harvest_rl.student60_data import digest
from harvest_vision.student60_camera_center import CenterCorrector,selected_record
from .student60_camera_controller import CameraRecurrentController
from .student60 import TargetFilter,decode_command,VERSION

FAMILY='student60_recurrent_camera_center_corrected_v1'
EXTENSION=CROP_EXTENSION+'_camera_center11_consistent_v1'
MAX_CORRECTION_M=.025


def corrected_point(corrector,position,record):
    _,delta=corrector.predict(None,position,record)
    delta=np.asarray(delta,float);delta*=min(1.,MAX_CORRECTION_M/max(np.linalg.norm(delta),1e-12))
    return np.asarray(position,float)+delta,delta


def correct_recorded_observation(observation,note,corrector):
    result=dict(observation);result['state']=observation['state'].copy()
    if result['state'][21] and note['target']['valid']:
        record=selected_record(note['target']['position_m'],note['detections'])
        if record is not None:
            _,delta=corrected_point(corrector,note['target']['position_m'],record)
            result['state'][18:21]+=delta.astype(np.float32)
    return result


class CorrectedCameraInference(RecurrentCameraInference):
    def __init__(self,checkpoint,contract,device='cpu'):
        saved=torch.load(checkpoint,map_location='cpu',weights_only=True)
        if (saved.get('model_family')!=FAMILY or saved.get('observation_extension')!=EXTENSION
                or saved.get('contract')!=contract or saved.get('student60_version')!=VERSION):
            raise ValueError('Corrected-camera recurrent contract mismatch')
        self.preprocessing=saved['training_config']['camera_center_preprocessing']
        for name,key in [('source','source_sha256'),('feature_source','feature_source_sha256')]:
            if digest(self.preprocessing[name])!=self.preprocessing[key]:raise ValueError('Camera preprocessing implementation changed')
        if digest(self.preprocessing['checkpoint'])!=self.preprocessing['sha256']:
            raise ValueError('Pinned learned camera estimator changed')
        self.model=RecurrentCameraStudent(contract).to(device).eval();self.model.load_state_dict(saved['student'],strict=True)
        self.contract,self.device=contract,device;self.reset()


class CorrectedCameraController(CameraRecurrentController):
    def __init__(self,checkpoint,contract,device='cpu'):
        self.policy=CorrectedCameraInference(checkpoint,contract,device);self.contract=contract
        self.corrector=CenterCorrector(self.policy.preprocessing['checkpoint'])
        self.target_filter=TargetFilter(contract['box_from_arm'],contract['box_min'],contract['box_max'])
        self.target_id=None;self.pending=False

    def step(self,frames,q,qd,tcp,target,now,capture):
        self.measured_jaw=float(q[-1]);corrected=dict(target);diagnostic=None
        if target['valid'] and 0<=target['age_s']<=.050001 and not self.target_filter.released:
            record=selected_record(target['position_m'],capture.get('student_target_detections',[]))
            if record is not None:
                point,delta=corrected_point(self.corrector,target['position_m'],record)
                corrected['position_m']=point.tolist()
                diagnostic=dict(raw_position_m=target['position_m'],offset_m=delta.tolist(),source='camera_only_center11')
        command,note=super().step(frames,q,qd,tcp,corrected,now,capture)
        note['learned_camera_center']=diagnostic
        return command,note

    def acknowledge(self,command):
        released_before=self.target_filter.released
        super().acknowledge(command)
        goal,_=decode_command(command,self.contract['lower_rad'],self.contract['upper_rad'])
        if not released_before and goal[-1]<=self.measured_jaw+1e-4:
            self.target_filter.opening=0.;self.target_filter.released=False


def make_controller(checkpoint,contract,device='cpu'):
    return CorrectedCameraController(checkpoint,contract,device)
