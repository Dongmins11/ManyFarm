"""60Hz r2 원본 계산에서 추출. 재생성: sim/tools/import_teacher60.py."""

import torch

def escape_velocity(jacobian, linear, targets, lower, upper, ramp, *, centering=False):
    if not all(torch.isfinite(x).all() for x in (jacobian,linear,targets,lower,upper,ramp)):
        raise ValueError('Finite posture inputs required')
    jp=jacobian[:,:3];n=len(targets)
    lo=lower[:5].expand_as(targets);hi=upper[:5].expand_as(targets).clone();hi[:,2]=hi[:,2].clamp_max(1.45)
    preferred=torch.zeros_like(targets)
    if centering:
        preferred=((lo+hi)/2-targets)*.05
        preferred=preferred.clamp(-.08,.08)
    blocked=torch.zeros_like(targets,dtype=torch.bool)
    eye=torch.eye(3,device=targets.device,dtype=targets.dtype).expand(n,3,3)
    for _ in range(6):
        j=torch.where(blocked[:,None,:],0.,jp)
        pref=torch.where(blocked,0.,preferred)
        inv=torch.linalg.solve(j@j.transpose(1,2)+.003**2*eye,eye)
        pinv=j.transpose(1,2)@inv
        velocity=(pinv@linear[:,:,None]).squeeze(-1)
        velocity+=pref-(pinv@(j@pref[:,:,None])).squeeze(-1)
        velocity=torch.where(blocked,0.,velocity)
        limit=.3*ramp[:,None]
        new=(((targets-.05*limit<=lo+.005)&(velocity<0))|
             ((targets+.05*limit>=hi-.005)&(velocity>0)))
        if torch.equal(blocked|new,blocked):break
        blocked|=new
    joint=(.3*ramp/velocity.abs().amax(-1).clamp_min(1e-12)).clamp_max(1.)
    predicted=(jacobian@velocity[:,:,None]).squeeze(-1)
    scale=joint.minimum((.035*ramp/predicted[:,:3].norm(dim=-1).clamp_min(1e-12)).clamp_max(1.))
    scale=scale.minimum((.08/predicted[:,3:].norm(dim=-1).clamp_min(1e-12)).clamp_max(1.))
    velocity*=scale[:,None]
    return velocity,blocked
