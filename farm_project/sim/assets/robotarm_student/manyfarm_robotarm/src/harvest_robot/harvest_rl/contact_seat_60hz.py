"""Small Teacher-only centering commands for weak attached contacts."""
from dataclasses import dataclass,asdict
import math
import torch


@dataclass(frozen=True)
class ContactSeatSpec:
    enabled: bool = False
    start_s: float = .25
    end_s: float = 1.5
    weak_force_N: float = .12
    minimum_one_contact_N: float = .08
    speed_m_s: float = .003
    total_path_m: float = .003
    joint_speed_rad_s: float = .04
    joint_path_rad: float = .02
    rotation_length_m: float = .08
    damping_m: float = .002

    def __post_init__(self):
        if type(self.enabled)is not bool or any(not math.isfinite(v) for k,v in asdict(self).items() if k!='enabled'):
            raise ValueError('Finite seating parameters and a boolean switch required')
        if (self.start_s!=.25 or self.end_s!=1.5 or min(self.speed_m_s,self.total_path_m,self.joint_speed_rad_s,
                self.joint_path_rad,self.rotation_length_m,self.damping_m)<=0
                or self.speed_m_s>.003 or self.total_path_m>.003 or self.joint_speed_rad_s>.04
                or self.joint_path_rad>.02 or not 0<self.minimum_one_contact_N<self.weak_force_N):
            raise ValueError('Strict small-motion/force/window bounds required')


class ContactSeat:
    def __init__(self,count,device,spec):
        self.spec=spec
        self.path=torch.zeros(count,device=device)
        self.joint_path=torch.zeros(count,5,device=device)

    def reset(self,ids):
        self.path[ids]=0.;self.joint_path[ids]=0.

    def step(self,commands,elapsed,*,error,jacobian,fixed,moving,confirmed,release,
             attached,slip,center_tolerance,max_slip,action_speed,dt):
        if (commands.shape!=(len(self.path),6) or error.shape!=(len(self.path),3)
                or jacobian.shape!=(len(self.path),6,5) or dt!=.05 or action_speed<=0
                or not all(torch.isfinite(t).all() for t in [commands,elapsed,error,jacobian,fixed,moving,slip])):
            raise ValueError('Finite matching20Hz seating inputs required')
        s=self.spec
        active=(s.enabled & confirmed & attached & ~release & (elapsed>=s.start_s-1e-7)
            & (elapsed<s.end_s-1e-7) & (fixed.minimum(moving)<s.weak_force_N)
            & (fixed.maximum(moving)>=s.minimum_one_contact_N)
            & (error.norm(dim=-1)<center_tolerance) & (slip<max_slip)
            & (self.path<s.total_path_m-1e-9))
        # Existing settle commands are zero; never add correction during pulling.
        if (commands[active,:5].abs()>1e-8).any():raise ValueError('Seating may only replace the zero-arm settle command')
        j=jacobian.clone();j[:,3:]*=s.rotation_length_m
        desired=torch.zeros(len(commands),6,device=commands.device,dtype=commands.dtype)
        desired[:,:3]=error*2.
        desired[:,:3]*=(s.speed_m_s/desired[:,:3].norm(dim=-1).clamp_min(1e-12)).clamp_max(1)[:,None]
        eye=torch.eye(5,device=j.device,dtype=j.dtype)
        v=torch.linalg.solve(j.transpose(1,2)@j+s.damping_m**2*eye,j.transpose(1,2)@desired[:,:,None]).squeeze(-1)
        pred=(jacobian[:,:3]@v[:,:,None]).squeeze(-1)
        scale=(s.joint_speed_rad_s/v.abs().amax(-1).clamp_min(1e-12)).clamp_max(1)
        scale=scale.minimum((s.speed_m_s/pred.norm(dim=-1).clamp_min(1e-12)).clamp_max(1))
        scale=scale.minimum(((s.total_path_m-self.path).clamp_min(0)/(pred.norm(dim=-1)*dt).clamp_min(1e-12)).clamp_max(1))
        remaining=(s.joint_path_rad-self.joint_path).clamp_min(0)
        scale=scale.minimum((remaining/(v.abs()*dt).clamp_min(1e-12)).amin(-1).clamp_max(1))
        v*=scale[:,None]
        pred=(jacobian[:,:3]@v[:,:,None]).squeeze(-1)
        # A singular least-squares result pointing away from the center is rejected.
        active &= (pred*error).sum(-1)>0
        result=commands.clone();result[active,:5]=(v/action_speed)[active]
        increment=pred.norm(dim=-1)*dt*active
        self.path+=increment;self.joint_path+=v.abs()*dt*active[:,None]
        return result,dict(seat_active=active,seat_predicted_step_m=increment,
            seat_command_path_m=self.path.clone(),seat_joint_path_max_rad=self.joint_path.amax(-1).clone())
