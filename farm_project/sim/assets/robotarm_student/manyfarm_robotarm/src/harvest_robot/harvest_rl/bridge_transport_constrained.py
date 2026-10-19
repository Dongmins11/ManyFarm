"""Active-set velocity solve for the existing5DOF transport candidate.

The elbow target boundary1.45rad is a conservative diagnostic command bound
from observed shoulder-link collisions around1.55-1.59rad, not a URDF change.
"""
import torch


def solve_velocity(jacobian,wanted,targets,lower,upper,ramp):
    j=jacobian.clone();j[:,3:]*=.02
    eye=torch.eye(5,device=j.device,dtype=j.dtype)
    lo=lower[:5].expand_as(targets).clone()
    hi=upper[:5].expand_as(targets).clone();hi[:,2]=hi[:,2].clamp_max(1.45)
    blocked=torch.zeros_like(targets,dtype=torch.bool)
    for _ in range(6):
        js=torch.where(blocked[:,None,:],0.,j)
        velocity=torch.linalg.solve(js.transpose(1,2)@js+.003**2*eye,
            js.transpose(1,2)@wanted[:,:,None]).squeeze(-1)
        velocity=torch.where(blocked,0.,velocity)
        limit=.3*ramp[:,None]
        new=(((targets-.05*limit<=lo+.005)&(velocity<0))
             |((targets+.05*limit>=hi-.005)&(velocity>0)))
        if torch.equal(blocked|new,blocked):break
        blocked |= new
    scale=(.3*ramp/velocity.abs().amax(-1).clamp_min(1e-12)).clamp_max(1.)
    predicted=(jacobian[:,:3]@velocity[:,:,None]).squeeze(-1)
    scale=scale.minimum((.035*ramp/predicted.norm(dim=-1).clamp_min(1e-12)).clamp_max(1.))
    return velocity*scale[:,None],blocked
