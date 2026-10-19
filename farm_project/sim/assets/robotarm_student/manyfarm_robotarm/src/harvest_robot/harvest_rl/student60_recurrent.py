"""Persistent camera policy with observed target crop and bounded goal residuals.

The only inputs are camera pixels, measured proprioception, vision target,
previous applied command and the controller's elapsed clock. No phase/contact
or simulator target is an input. Output remains six absolute goals + two servos.
"""
import numpy as np
import torch
from torch import nn
from .student_v3 import encoder
from .student60_crop import EXTENSION,CROP_SIZE
from harvest_runtime.student60 import VERSION,decode_command

FAMILY='student60_camera_recurrent_delta_v1'


class RecurrentCameraStudent(nn.Module):
    def __init__(self,contract):
        super().__init__()
        self.wrist_rgb=encoder(3);self.wrist_ir=encoder(1);self.rear_rgbd=encoder(5)
        self.memory=nn.GRU(4*384+24+4,192,batch_first=True)
        self.actor=nn.Sequential(nn.Linear(192+24,192),nn.ELU(),nn.Linear(192,8))
        # Actual recorded arm commands are <=.04 rad/tick, jaw<=.089 (deposit).
        span=(np.asarray(contract['upper_rad'])-np.asarray(contract['lower_rad']))/2
        self.register_buffer('delta_scale',torch.tensor(np.array([.04]*5+[.10])/span,dtype=torch.float32))
        self.freeze_encoders()

    def freeze_encoders(self):
        for module in (self.wrist_rgb,self.wrist_ir,self.rear_rgbd):
            for p in module.parameters():p.requires_grad_(False)

    def initialize_encoders(self,state):
        for name in ('wrist_rgb','wrist_ir','rear_rgbd'):
            getattr(self,name).load_state_dict({k[len(name)+1:]:v for k,v in state.items() if k.startswith(name+'.')},strict=True)

    def encode(self,rgb,depth_m,camera_valid,state,wrist_ir_right,wrist_ir_valid,
               rear_target_rgb,rear_target_depth,rear_target_valid,elapsed_s):
        n,t,c,h,w,_=rgb.shape
        if (c,h,w)!=(2,90,160) or state.shape!=(n,t,23) or rear_target_rgb.shape!=(n,t,CROP_SIZE,CROP_SIZE,3):
            raise ValueError('Camera recurrent observation shape mismatch')
        if not torch.isfinite(state).all() or torch.any(depth_m[:,:,0]!=0) or not torch.isfinite(elapsed_s).all():
            raise ValueError('Invalid measured state or included wrist depth')
        valid=torch.isfinite(depth_m[:,:,1])&(depth_m[:,:,1]>0)&(depth_m[:,:,1]<=3)
        rear=torch.cat((rgb[:,:,1].float()/255,torch.where(valid,depth_m[:,:,1]/3,0)[...,None],valid[...,None].float()),-1)
        crop_ok=torch.isfinite(rear_target_depth)&(rear_target_depth>0)&(rear_target_depth<=3)
        crop=torch.cat((rear_target_rgb.float()/255,torch.where(crop_ok,rear_target_depth/3,0)[...,None],crop_ok[...,None].float()),-1)
        wr=rgb[:,:,0].float()/255*camera_valid[:,:,0,None,None,None]
        ir=wrist_ir_right.float()/255*wrist_ir_valid[...,None,None]
        rear=rear*camera_valid[:,:,1,None,None,None];crop=crop*rear_target_valid[...,None,None,None]
        with torch.no_grad():
            values=[self.wrist_rgb(wr.reshape(n*t,h,w,3).permute(0,3,1,2)),
                self.wrist_ir(ir.reshape(n*t,1,h,w)),
                self.rear_rgbd(rear.reshape(n*t,h,w,5).permute(0,3,1,2)),
                self.rear_rgbd(crop.reshape(n*t,CROP_SIZE,CROP_SIZE,5).permute(0,3,1,2))]
        masks=torch.stack((camera_valid[:,:,0],camera_valid[:,:,1],wrist_ir_valid,rear_target_valid),-1).float()
        # Keep measured state last, making the command identity path explicit.
        return torch.cat((torch.cat(values,-1).reshape(n,t,-1),masks,state,
                          (elapsed_s/60).clamp(0,2)[...,None]),-1)

    def forward_features(self,features,hidden=None):
        x,hidden=self.memory(features,hidden)
        raw=self.actor(torch.cat((x,features[:,:,-24:]),-1))
        state=features[:,:,-24:-1]
        goals=(state[:,:,12:18]+torch.tanh(raw[:,:,:6])*self.delta_scale).clamp(-1,1)
        return torch.cat((goals,torch.tanh(raw[:,:,6:])),dim=-1),hidden

    def forward(self,hidden=None,return_hidden=False,**observation):
        commands,hidden=self.forward_features(self.encode(**observation),hidden)
        return (commands,hidden) if return_hidden else commands


class RecurrentCameraInference:
    def __init__(self,checkpoint,contract,device='cpu'):
        saved=torch.load(checkpoint,map_location='cpu',weights_only=True)
        if saved.get('model_family')!=FAMILY or saved.get('observation_extension')!=EXTENSION or saved.get('contract')!=contract or saved.get('student60_version')!=VERSION:
            raise ValueError('Recurrent camera checkpoint contract mismatch')
        self.model=RecurrentCameraStudent(contract).to(device).eval()
        self.model.load_state_dict(saved['student'],strict=True)
        self.contract,self.device=contract,device;self.reset()

    def reset(self):self.hidden=None;self.previous=None;self.target_id=None;self.last_time=None

    def predict(self,observation,target_id):
        if not target_id:raise ValueError('Assigned target required')
        if target_id!=self.target_id:self.reset();self.target_id=target_id
        if self.previous is not None and not np.allclose(observation['state'][12:18],self.previous,atol=1e-6):
            raise ValueError('Previous command must be the actual applied command')
        now=float(observation['elapsed_s'])
        if self.last_time is not None and abs(now-self.last_time-.05)>2e-5:raise ValueError('Nonsequential recurrent clock')
        with torch.inference_mode():
            commands,self.hidden=self.model(**{k:torch.as_tensor(v[None,None],device=self.device) for k,v in observation.items()},
                                            hidden=self.hidden,return_hidden=True)
        self.last_time=now
        command=commands[0,0].cpu().numpy();decode_command(command,self.contract['lower_rad'],self.contract['upper_rad'])
        return command

    def acknowledge(self,command):
        decode_command(command,self.contract['lower_rad'],self.contract['upper_rad'])
        self.previous=np.asarray(command[:6]).copy()
