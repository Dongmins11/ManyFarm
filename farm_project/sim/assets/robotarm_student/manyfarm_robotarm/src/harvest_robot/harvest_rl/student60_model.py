"""Separate checkpoint family: measured v3 observations, eight command outputs."""
import numpy as np
import torch
from torch import nn
from .student_v3 import MultimodalStudent
from .student_v2 import DualHistory
from harvest_runtime.student60 import VERSION, decode_command


class Student60(MultimodalStudent):
    def __init__(self):
        super().__init__()
        self.actor=nn.Sequential(nn.Linear(128,128),nn.ELU(),nn.Linear(128,8),nn.Tanh())


class Student60Inference:
    """Caller filters targets with TargetFilter before packing observations.

predict returns position goals and jaw gain/velocity; these are not increments.
No Teacher policy/controller is constructed or called.
"""
    def __init__(self, checkpoint, contract, device='cpu'):
        saved=torch.load(checkpoint,map_location='cpu',weights_only=True)
        if saved.get('student60_version')!=VERSION or saved.get('contract')!=contract:
            raise ValueError('Checkpoint action/sensor/actuator contract mismatch')
        self.contract=contract;self.device=device
        self.model=Student60().to(device).eval();self.model.load_state_dict(saved['student'],strict=True)
        self.reset()

    def reset(self):self.history=None;self.target_id=None;self.previous=None

    def predict(self, observation, target_id):
        if not target_id:raise ValueError('Require explicit assigned target')
        if self.target_id!=target_id:
            self.reset();self.target_id=target_id
        if self.previous is not None and not np.allclose(observation['state'][12:18],self.previous,atol=1e-6):
            raise ValueError('Previous action must be the actual executed target command')
        if self.history is None:self.history=DualHistory(observation)
        else:self.history.update(observation)
        with torch.inference_mode():cmd=self.model(**self.history.tensors(self.device))[0].cpu().numpy()
        decode_command(cmd,self.contract['lower_rad'],self.contract['upper_rad'])
        return cmd

    def acknowledge(self, executed_command):
        decode_command(executed_command,self.contract['lower_rad'],self.contract['upper_rad'])
        self.previous=np.asarray(executed_command[:6]).copy()
