"""Dual RGB-D target-conditioned student; ROS/Isaac-independent inference contract."""
import numpy as np
import torch
from torch import nn
from torch.nn import functional as F
from .target_contract import student_state

CAMERAS=('right','rear')
VERSION=2
HEIGHT,WIDTH=90,160


def pack_observation(frames, proprio, tcp_arm, target, now, ttl=.3):
    rgb=[];depth=[];valid=[]
    identities={(f.frame_id,f.clock_id) for f in frames.values()}
    if len(identities)>1: raise ValueError('Camera frame/clock mismatch')
    for name in CAMERAS:
        frame=frames.get(name)
        ok=frame is not None and 0<=now-frame.stamp_s<=ttl
        if ok:
            frame.validate()
            if frame.camera_id!=name: raise ValueError('Camera order mismatch')
            x=torch.from_numpy(frame.rgb.copy()).permute(2,0,1)[None].float()
            rgb.append(F.interpolate(x,(HEIGHT,WIDTH),mode='bilinear',align_corners=False)[0].permute(1,2,0).round().byte().numpy())
            d=np.where(np.isfinite(frame.depth_m)&(frame.depth_m>0)&(frame.depth_m<=3),frame.depth_m,0).astype('float32')
            depth.append(F.interpolate(torch.from_numpy(d)[None,None],(HEIGHT,WIDTH),mode='nearest')[0,0].numpy())
        else:
            rgb.append(np.zeros((HEIGHT,WIDTH,3),np.uint8));depth.append(np.zeros((HEIGHT,WIDTH),np.float32))
        valid.append(ok)
    state=student_state(torch.as_tensor(proprio,dtype=torch.float32).reshape(1,18),
        torch.tensor([target['position_m']],dtype=torch.float32),torch.as_tensor(tcp_arm,dtype=torch.float32).reshape(1,3),
        torch.tensor([target['valid']],dtype=torch.bool),torch.tensor([target['age_s']],dtype=torch.float32))[0].numpy()
    return dict(rgb=np.stack(rgb),depth_m=np.stack(depth),camera_valid=np.array(valid,np.bool_),state=state)


class DualRGBDStudent(nn.Module):
    version=VERSION
    history=3
    def __init__(self):
        super().__init__()
        # Shared encoder, preserved camera order in fusion. RGB + depth + depth validity.
        self.encoder=nn.Sequential(nn.Conv2d(5,24,5,2),nn.ELU(),nn.Conv2d(24,48,3,2),nn.ELU(),
            nn.Conv2d(48,64,3,2),nn.ELU(),nn.AdaptiveAvgPool2d((2,3)),nn.Flatten())
        self.memory=nn.GRU(2*64*6+23+2,128,batch_first=True)
        self.actor=nn.Sequential(nn.Linear(128,128),nn.ELU(),nn.Linear(128,6),nn.Tanh())

    def forward(self,rgb,depth_m,camera_valid,state):
        # N,T,2,H,W,3 / N,T,2,H,W / N,T,2 / N,T,23
        n,t,c,h,w,_=rgb.shape
        if c!=2 or state.shape!=(n,t,23) or depth_m.shape!=(n,t,c,h,w) or camera_valid.shape!=(n,t,c):
            raise ValueError('Student v2 input shape mismatch')
        if not torch.isfinite(state).all(): raise ValueError('Invalid state')
        mask=torch.isfinite(depth_m)&(depth_m>0)&(depth_m<=3)
        depth=torch.where(mask,depth_m,0).float()/3.
        x=torch.cat((rgb.float()/255.,depth[...,None],mask[...,None].float()),dim=-1)
        x=x*camera_valid[...,None,None,None]
        x=self.encoder(x.reshape(n*t*c,h,w,5).permute(0,3,1,2)).reshape(n,t,-1)
        x,_=self.memory(torch.cat((x,state,camera_valid.float()),-1))
        return self.actor(x[:,-1])


class DualHistory:
    def __init__(self, observation): self.reset(observation)
    def reset(self, observation):
        self.data={k:np.repeat(v[None],3,axis=0) for k,v in observation.items()}
    def update(self, observation):
        for k,v in observation.items(): self.data[k]=np.concatenate((self.data[k][1:],v[None]),axis=0)
    def tensors(self, device='cpu'):
        return {k:torch.as_tensor(v[None],device=device) for k,v in self.data.items()}


def measured_proprio(q_rad, qd_rad_s, previous_action, lower_rad, upper_rad):
    """Same normalization as HarvestEnv.proprio, using measured joints only."""
    q,qd,action,lo,hi=[np.asarray(v,dtype=np.float32) for v in (q_rad,qd_rad_s,previous_action,lower_rad,upper_rad)]
    if any(v.shape!=(6,) or not np.isfinite(v).all() for v in (q,qd,action,lo,hi)) or np.any(hi<=lo):
        raise ValueError('Invalid joint state/limits')
    if np.any(np.abs(action)>1): raise ValueError('Previous action must be normalized')
    return np.concatenate((2*(q-lo)/(hi-lo)-1,qd/1.5,action))


class StudentInference:
    """Stateful tensor inference; caller owns motion gating and completion evidence."""
    def __init__(self, checkpoint, device='cpu'):
        saved=torch.load(checkpoint,map_location=device,weights_only=True)
        if saved.get('schema_version')!=VERSION or saved.get('camera_order')!=list(CAMERAS):
            raise ValueError('Require dual RGB-D Student v2 checkpoint')
        self.model=DualRGBDStudent().to(device).eval()
        self.model.load_state_dict(saved['student'],strict=True)
        self.device=device;self.history=None;self.target_id=None
    def reset(self): self.history=None;self.target_id=None
    def predict(self, observation, target_id):
        if not target_id: raise ValueError('Require assigned target ID')
        if self.history is None or self.target_id!=target_id:
            self.history=DualHistory(observation);self.target_id=target_id
        else: self.history.update(observation)
        with torch.inference_mode(): return self.model(**self.history.tensors(self.device))[0].cpu().numpy()
