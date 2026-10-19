"""Capture-region perception head. No simulator truth is consumed by inference."""
import numpy as np
import torch
from torch import nn
from .student_v2 import DualRGBDStudent,DualHistory
from .entry_grasp import entry_state


def entry_truth(local_center,half_width,jaw,diameter):
    # Center containment survives jaw closing; full-open clearance is a separate label.
    aligned,gap=entry_state(local_center,jaw)
    x=local_center[:,0]+diameter/2
    return aligned & (x>=0) & (x<=gap) & (half_width>0)


class EntryAuxModel(DualRGBDStudent):
    def __init__(self):
        super().__init__()
        self.actor=nn.Sequential(nn.Linear(128,128),nn.ELU(),nn.Linear(128,2))


class EntryDecision:
    def __init__(self,threshold=.95,frames=3):
        if not .5<threshold<1 or frames<1:raise ValueError('Invalid threshold/dwell')
        self.threshold=threshold;self.frames=frames;self.reset()
    def reset(self):self.count=0;self.target_id=None
    def update(self,probability,target_id,observable,geometry_ok=True):
        if target_id!=self.target_id:self.count=0;self.target_id=target_id
        if not observable or not target_id or not 0<=probability<=1:
            self.count=0;return 'UNKNOWN'
        if not geometry_ok:self.count=0;return 'OUTSIDE'
        self.count=self.count+1 if probability>=self.threshold else 0
        return 'INSIDE' if self.count>=self.frames else 'OUTSIDE'


class EntryAuxInference:
    """Shadow-only suggestion; INSIDE is NOT proof of contact, hold or detachment."""
    def __init__(self,path,contract,device='cpu'):
        saved=torch.load(path,map_location=device,weights_only=True)
        if saved.get('kind')!='entry_aux_v1' or saved['contract']!=contract:raise ValueError('Entry model observation contract mismatch')
        self.model=EntryAuxModel().to(device).eval();self.model.load_state_dict(saved['model'])
        self.max_age=contract['control_dt']
        self.device=device;self.decision=EntryDecision();self.history=None;self.target_id=None
    def reset(self):self.decision.reset();self.history=None;self.target_id=None
    def predict(self,sample,target_id):
        if self.history is None or target_id!=self.target_id:self.history=DualHistory(sample);self.target_id=target_id
        else:self.history.update(sample)
        with torch.inference_mode():p=float(self.model(**self.history.tensors(self.device)).softmax(-1)[0,1])
        observable=bool(sample['state'][21] and sample['state'][22]<=self.max_age and sample['camera_valid'].any())
        delta=np.asarray(sample['state'][18:21])
        distance=float(np.linalg.norm(delta))
        geometry_ok=bool(np.isfinite(distance) and distance<=.05)
        return dict(probability=p,state=self.decision.update(p,target_id,observable,geometry_ok),
            geometry_ok=geometry_ok,estimated_distance_m=distance,geometry_max_distance_m=.05,
            reason='unobservable' if not observable else ('far_from_capture' if not geometry_ok else 'model_and_dwell'),shadow_only=True)
