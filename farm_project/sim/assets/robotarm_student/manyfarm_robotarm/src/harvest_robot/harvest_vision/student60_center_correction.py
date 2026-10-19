"""Bounded learned correction to an observed RGB-D centre estimate.

Features contain measured proprioception, estimated point and detector quality.
Training pose labels are never arguments to runtime inference.
"""
import numpy as np
import torch
from torch import nn

VERSION='observed_center_residual34_v1'


def features(state,position,record):
    box=np.asarray(record.get('bbox',[0,0,0,0]),np.float32)/np.array([1280,720,1280,720],np.float32)
    quality=[record.get('confidence',0),record.get('valid_depth_fraction',0),
             min(float(record.get('depth_mad_m',0) or 0),.1),np.log1p(record.get('depth_pixels',0))/10]
    x=np.r_[np.asarray(state,np.float32),np.asarray(position,np.float32),box,quality].astype(np.float32)
    if x.shape!=(34,) or not np.isfinite(x).all():raise ValueError('Invalid observed centre features')
    return x


def selected_record(position,records):
    candidates=[r for r in records if r.get('candidate_valid') and r.get('grasp_estimate_arm_m') is not None]
    if not candidates:return None
    found=min(candidates,key=lambda r:np.linalg.norm(np.asarray(r['grasp_estimate_arm_m'])-position))
    return found if np.linalg.norm(np.asarray(found['grasp_estimate_arm_m'])-position)<.035 else None


class CenterResidual(nn.Module):
    def __init__(self):
        super().__init__();self.register_buffer('mean',torch.zeros(34));self.register_buffer('std',torch.ones(34))
        self.net=nn.Sequential(nn.Linear(34,96),nn.ELU(),nn.Linear(96,96),nn.ELU(),nn.Linear(96,3),nn.Tanh())
    def forward(self,x):return self.net(((x-self.mean)/self.std).clamp(-8,8))*.03


class CenterCorrector:
    def __init__(self,path):
        saved=torch.load(path,map_location='cpu',weights_only=True)
        if saved.get('version')!=VERSION:raise ValueError('Centre estimator version mismatch')
        self.model=CenterResidual().eval();self.model.load_state_dict(saved['model'],strict=True)
    def predict(self,state,position,record):
        with torch.inference_mode():delta=self.model(torch.from_numpy(features(state,position,record))[None])[0].numpy()
        return np.asarray(position)+delta,delta
