"""Wrist RGB + distinct right IR view; rear RGB-D. No privileged inputs."""
import numpy as np
import torch
from torch import nn
from torch.nn import functional as F
from .student_v2 import pack_observation as pack_rgbd, DualHistory

VERSION = 3
FIELDS = {'rgb','depth_m','camera_valid','state','wrist_ir_right','wrist_ir_valid'}


def pack_observation(frames, proprio, tcp_arm, target, now, capture, ttl=.3):
    result=pack_rgbd(frames,proprio,tcp_arm,target,now,ttl)
    # Wrist depth is not a policy input (nor an implicit validity channel).
    result['depth_m'][0]=0
    data=capture.get('right')
    valid=data is not None and 0 <= now-data['stamp_s'] <= ttl and 'ir_right' in data['ir']
    if valid:
        image=data['ir']['ir_right']
        if image.dtype != np.uint8 or image.ndim != 2:raise ValueError('Expected right IR Y8')
        result['wrist_ir_right']=F.interpolate(torch.from_numpy(image.copy())[None,None].float(),
            (90,160),mode='bilinear',align_corners=False)[0,0].round().byte().numpy()
    else:result['wrist_ir_right']=np.zeros((90,160),np.uint8)
    result['wrist_ir_valid']=np.array(valid,np.bool_)
    return result


def encoder(channels):
    return nn.Sequential(nn.Conv2d(channels,24,5,2),nn.ELU(),nn.Conv2d(24,48,3,2),nn.ELU(),
        nn.Conv2d(48,64,3,2),nn.ELU(),nn.AdaptiveAvgPool2d((2,3)),nn.Flatten())


class MultimodalStudent(nn.Module):
    version=VERSION;history=3
    def __init__(self):
        super().__init__()
        self.wrist_rgb=encoder(3);self.wrist_ir=encoder(1);self.rear_rgbd=encoder(5)
        self.memory=nn.GRU(3*64*6+23+3,128,batch_first=True)
        self.actor=nn.Sequential(nn.Linear(128,128),nn.ELU(),nn.Linear(128,6),nn.Tanh())

    def forward(self,rgb,depth_m,camera_valid,state,wrist_ir_right,wrist_ir_valid):
        n,t,c,h,w,_=rgb.shape
        if (c,h,w)!=(2,90,160) or state.shape!=(n,t,23) or depth_m.shape!=(n,t,c,h,w) or camera_valid.shape!=(n,t,c) or wrist_ir_right.shape!=(n,t,h,w) or wrist_ir_valid.shape!=(n,t):
            raise ValueError('Student v3 shape mismatch')
        if torch.any(depth_m[:,:,0] != 0):raise ValueError('Wrist depth must be excluded')
        if not torch.isfinite(state).all():raise ValueError('Invalid proprio/target state')
        masks=torch.cat((camera_valid,wrist_ir_valid[...,None]),-1).float()
        wr=rgb[:,:,0].float()/255*camera_valid[:,:,0,None,None,None]
        ir=wrist_ir_right.float()/255*wrist_ir_valid[...,None,None]
        depth=depth_m[:,:,1];valid=torch.isfinite(depth)&(depth>0)&(depth<=3)
        rear=torch.cat((rgb[:,:,1].float()/255,torch.where(valid,depth/3,0)[...,None],valid[...,None].float()),-1)
        rear=rear*camera_valid[:,:,1,None,None,None]
        features=[self.wrist_rgb(wr.reshape(n*t,h,w,3).permute(0,3,1,2)),
                  self.wrist_ir(ir.reshape(n*t,1,h,w)),
                  self.rear_rgbd(rear.reshape(n*t,h,w,5).permute(0,3,1,2))]
        x=torch.cat(features,-1).reshape(n,t,-1)
        x,_=self.memory(torch.cat((x,state,masks),-1))
        return self.actor(x[:,-1])


class StudentInference:
    def __init__(self,checkpoint,device='cpu'):
        saved=torch.load(checkpoint,map_location=device,weights_only=True)
        if saved.get('schema_version')!=3 or saved.get('camera_order')!=['right','rear']:
            raise ValueError('Require multimodal Student v3 checkpoint')
        self.model=MultimodalStudent().to(device).eval();self.model.load_state_dict(saved['student'],strict=True)
        self.device=device;self.reset()
    def reset(self):self.history=None;self.target_id=None
    def predict(self,observation,target_id):
        if not target_id:raise ValueError('Require assigned target ID')
        if self.history is None or self.target_id!=target_id:
            self.history=DualHistory(observation);self.target_id=target_id
        else:self.history.update(observation)
        with torch.inference_mode():return self.model(**self.history.tensors(self.device))[0].cpu().numpy()
