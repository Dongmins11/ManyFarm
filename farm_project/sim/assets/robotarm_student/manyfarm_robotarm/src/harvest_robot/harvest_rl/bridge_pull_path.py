"""Bounded Cartesian pull comparison; no attachment/contact/outcome writes."""
from dataclasses import asdict, dataclass
import math
import torch


@dataclass(frozen=True)
class PullPathSpec:
    speed_m_s: float = .03
    travel_m: float = .055
    gain_s: float = 4.
    orientation_length_m: float = .04
    damping_m: float = .003
    joint_speed_rad_s: float = .3
    hold_after_detach: bool = False
    axial: bool = True

    def __post_init__(self):
        if any(not math.isfinite(v) or v <= 0 for k,v in asdict(self).items()
               if k not in ('hold_after_detach','axial')):
            raise ValueError('Positive finite pull-path parameters required')
        if self.speed_m_s > .06 or self.travel_m > .06 or self.joint_speed_rad_s > .5:
            raise ValueError('Diagnostic path exceeds its bounded comparison limits')


class PullPath:
    """Keep handoff pose, advance an axial waypoint only under real qualification.

    The waypoint is a controller target, never a simulated fruit position. Joint
    increments are added to existing loaded targets; no measured-angle rebasing.
    Qualified loss pauses advancement and commands zero arm increments. Original
    physics and the original finite episode clock continue to run.
    """
    def __init__(self,n,device,spec):
        self.spec=spec
        self.origin=torch.zeros(n,3,device=device)
        self.rotation=torch.eye(3,device=device).expand(n,3,3).clone()
        self.travel=torch.zeros(n,device=device)
        self.started=torch.zeros(n,device=device,dtype=torch.bool)

    def reset(self,ids):
        self.started[ids]=False;self.travel[ids]=0.

    def step(self,commands,position,rotation,jacobian,*,active,attached,qualified,
             valid_detach,release,axis,ramp,action_speed,dt):
        if abs(dt-.05)>1e-9 or action_speed<=0:
            raise ValueError('Preserve positive action speed and20Hz control')
        a=torch.as_tensor(axis,device=commands.device,dtype=commands.dtype)
        if a.shape!=(3,) or not torch.isfinite(a).all() or a.norm()<1e-9:
            raise ValueError('Nonzero finite world-frame pull axis required')
        a=a/a.norm()
        first=active & ~self.started & ~release
        self.origin[first]=position[first];self.rotation[first]=rotation[first]
        self.travel[first]=0.;self.started |= first
        scope=active & self.started & attached & ~release & self.spec.axial
        moving=scope & qualified
        self.travel=torch.where(moving,(self.travel+self.spec.speed_m_s*dt*ramp).clamp_max(self.spec.travel_m),self.travel)
        target=self.origin+self.travel[:,None]*a
        linear=self.spec.gain_s*(target-position)
        # Skew error is a small-angle world rotation error about the handoff pose.
        skew=self.rotation@rotation.transpose(1,2)
        angular=.5*torch.stack((skew[:,2,1]-skew[:,1,2],skew[:,0,2]-skew[:,2,0],skew[:,1,0]-skew[:,0,1]),-1)
        angular*=self.spec.gain_s
        weight=self.spec.orientation_length_m
        j=jacobian.clone();j[:,3:]*=weight
        wanted=torch.cat((linear,angular*weight),-1)
        eye=torch.eye(5,device=commands.device,dtype=commands.dtype)
        velocity=torch.linalg.solve(j.transpose(1,2)@j+self.spec.damping_m**2*eye,
                                    j.transpose(1,2)@wanted[:,:,None]).squeeze(-1)
        # Uniform scaling preserves the solved direction; bound joint and TCP speed.
        limit=torch.minimum(ramp*self.spec.joint_speed_rad_s,ramp*action_speed)
        scale=(limit/velocity.abs().amax(-1).clamp_min(1e-12)).clamp_max(1.)
        predicted=(jacobian[:,:3]@velocity[:,:,None]).squeeze(-1)
        scale=scale.minimum((ramp*self.spec.speed_m_s/predicted.norm(dim=-1).clamp_min(1e-12)).clamp_max(1.))
        velocity*=scale[:,None]
        result=commands.clone();result[scope,:5]=0.
        result[moving,:5]=(velocity/action_speed)[moving]
        holding=active & valid_detach & ~attached & ~release & self.spec.hold_after_detach
        result[holding,:5]=0.
        actual=(jacobian[:,:3]@(result[:,:5]*action_speed)[:,:,None]).squeeze(-1)
        diagnostics=dict(path_active=scope,path_paused=scope & ~qualified,
            path_hold=holding,path_travel_m=self.travel.clone(),
            path_tracking_error_m=(target-position).norm(dim=-1),
            path_predicted_axial_m_s=(actual*a).sum(-1),
            path_predicted_lateral_m_s=(actual-(actual*a).sum(-1)[:,None]*a).norm(dim=-1))
        if not torch.isfinite(result).all():raise FloatingPointError('Nonfinite Cartesian path command')
        return result,diagnostics
