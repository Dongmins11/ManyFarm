"""Conservative sampled link-centre screening, plus runtime contact interlocks.

This is NOT exact mesh collision detection. Do not deploy as a hardware planner.
"""
import numpy as np


def screened_home_path(current,home,kin,fruit_positions,settings):
    start=np.asarray(current).copy();end=np.asarray(home).copy()
    start[-1]=end[-1]
    lo=np.asarray(settings.box_min);hi=np.asarray(settings.box_max)
    def clear(q):
        joints=[kin.fk(q,'arm_2/'+name)[:3,3] for name in
                ('upper_arm_link','lower_arm_link','wrist_link','gripper_link')]
        joints.append(kin.grasp_fk(q,settings.diameter)[:3,3])
        samples=np.concatenate([np.linspace(a,b,9) for a,b in zip(joints[:-1],joints[1:])])
        margin=.015
        # Box side walls, not its empty interior. Floor and deck excluded from
        # corners are screened explicitly below.
        for axis in (0,1):
            other=1-axis
            for face in (lo[axis],hi[axis]):
                hit=(abs(samples[:,axis]-face)<margin)&(samples[:,other]>lo[other]-margin)&(samples[:,other]<hi[other]+margin)&(samples[:,2]>lo[2]-margin)&(samples[:,2]<hi[2]+margin)
                if hit.any():return False
        if ((samples[:,2]<.74)&(samples[:,0]<.315)).any():return False
        if (samples[:,2]<lo[2]+margin).any():return False
        if len(fruit_positions):
            distance=np.linalg.norm(samples[:,None]-np.asarray(fruit_positions)[None,:],axis=-1)
            if (distance<max(settings.diameter/2,settings.length/2)+margin).any():return False
        return True
    count=max(2,int(np.ceil(np.max(abs(end-start))/.02))+1)
    path=np.linspace(start,end,count)
    if not all(clear(q) for q in path):
        raise RuntimeError('Direct HOME path blocked by conservative clearance screen; no old-target detour fallback')
    return path
