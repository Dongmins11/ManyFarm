"""60Hz r2 원본 계산에서 추출. 재생성: sim/tools/import_teacher60.py."""

import torch

class TransportPath:
    def __init__(self,n,device):
        self.started=torch.zeros(n,device=device,dtype=torch.bool)
        self.clear=torch.zeros_like(self.started)
        self.origin=torch.zeros(n,3,device=device)
        self.rotation=torch.eye(3,device=device).expand(n,3,3).clone()

    def reset(self,ids):
        self.started[ids]=False;self.clear[ids]=False

    def step(self,position,rotation,jacobian,goal,*,active,qualified,elapsed,dt=.05):
        if abs(dt-.05)>1e-9:raise ValueError('Requires20Hz policy')
        first=active & ~self.started
        self.origin[first]=position[first];self.rotation[first]=rotation[first]
        self.started |= first
        exit_goal=self.origin.clone();exit_goal[:,0]-=.03
        self.clear |= active & ((position-exit_goal).norm(dim=-1)<.005)
        target=torch.where(self.clear[:,None],goal,exit_goal)
        linear=4.*(target-position)
        skew=self.rotation@rotation.transpose(1,2)
        angular=2.*torch.stack((skew[:,2,1]-skew[:,1,2],skew[:,0,2]-skew[:,2,0],skew[:,1,0]-skew[:,0,1]),-1)
        # SO101 has5 arm joints. Position is primary; softly retain the actual
        # captured wrist orientation instead of commanding an impossible6DOF pose.
        j=jacobian.clone();j[:,3:]*=.02
        wanted=torch.cat((linear,angular*.02),-1)
        eye=torch.eye(5,device=position.device,dtype=position.dtype)
        velocity=torch.linalg.solve(j.transpose(1,2)@j+.003**2*eye,
            j.transpose(1,2)@wanted[:,:,None]).squeeze(-1)
        ramp=.25+.75*(elapsed/3.).clamp(0.,1.)
        scale=(.3*ramp/velocity.abs().amax(-1).clamp_min(1e-12)).clamp_max(1.)
        predicted=(jacobian[:,:3]@velocity[:,:,None]).squeeze(-1)
        scale=scale.minimum((.035*ramp/predicted.norm(dim=-1).clamp_min(1e-12)).clamp_max(1.))
        velocity*=scale[:,None]
        velocity=torch.where((active & qualified)[:,None],velocity,0.)
        if not torch.isfinite(velocity).all():raise FloatingPointError('Nonfinite transport path')
        return velocity,dict(transport_path_clear=self.clear.clone(),
            transport_path_paused=active & ~qualified,
            transport_path_error_m=(target-position).norm(dim=-1),
            transport_goal_error_m=(goal-position).norm(dim=-1),
            transport_path_predicted_speed_m_s=(jacobian[:,:3]@velocity[:,:,None]).squeeze(-1).norm(dim=-1))
