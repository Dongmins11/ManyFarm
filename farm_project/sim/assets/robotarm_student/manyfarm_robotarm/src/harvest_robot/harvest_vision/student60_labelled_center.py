"""Camera-only centre residual; no robot-state shortcuts in perception.

The input is the observed RGB-D point, segmentation bbox and depth quality.
Simulator position is used only as an offline supervised target in the trainer.
"""
import numpy as np
import torch
from torch import nn
from .student60_center_correction import selected_record

VERSION='observed_center_visual_geometry_label13_v1'


def features(state,position,record):
    box=np.asarray(record.get('bbox',[0,0,0,0]),np.float32)/np.array([1280,720,1280,720],np.float32)
    quality=[record.get('confidence',0),record.get('valid_depth_fraction',0),
             min(float(record.get('depth_mad_m',0) or 0),.1),np.log1p(record.get('depth_pixels',0))/10]
    label=record.get('label')
    if label not in ('Red','Yellow'):raise ValueError('Unobserved fruit class')
    x=np.r_[np.asarray(position,np.float32),box,quality,[label=='Red',label=='Yellow']].astype(np.float32)
    if x.shape!=(13,) or not np.isfinite(x).all():raise ValueError('Invalid camera centre features')
    return x


class CenterResidual(nn.Module):
    def __init__(self):
        super().__init__();self.register_buffer('mean',torch.zeros(13));self.register_buffer('std',torch.ones(13))
        self.net=nn.Sequential(nn.Linear(13,96),nn.ELU(),nn.Linear(96,96),nn.ELU(),nn.Linear(96,3),nn.Tanh())
    def forward(self,x):return self.net(((x-self.mean)/self.std).clamp(-8,8))*.03


class CenterCorrector:
    def __init__(self,path):
        saved=torch.load(path,map_location='cpu',weights_only=True)
        if saved.get('version')!=VERSION:raise ValueError('Camera-only centre version mismatch')
        self.model=CenterResidual().eval();self.model.load_state_dict(saved['model'],strict=True)
    def predict(self,state,position,record):
        with torch.inference_mode():delta=self.model(torch.from_numpy(features(None,position,record))[None])[0].numpy()
        return np.asarray(position)+delta,delta
