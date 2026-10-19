"""FK/vision-only staged approach. No fruit truth or simulator API dependencies."""
import numpy as np
from scipy.spatial.transform import Rotation


class AlignedApproach:
    def __init__(self, pose, lower, upper, dt=.05, speed=.8):
        self.pose, self.lower, self.upper = pose, np.asarray(lower), np.asarray(upper)
        self.dt, self.speed = dt, speed
        self.rotation = None
        self.stage = 'ALIGN'
        self.count = 0

    def command(self, q, targets, target):
        q, targets, target = map(np.asarray, (q, targets, target))
        t = self.pose(q)
        if self.rotation is None:
            self.rotation = t[:3,:3].copy()
        # Link local -Z points out through fingertips (grasp_fk rotates +Z by pi).
        pre = target + self.rotation[:,2]*.07
        goal = pre if self.stage == 'ALIGN' else target
        error = goal-t[:3,3]
        rotation_error = Rotation.from_matrix(self.rotation@t[:3,:3].T).as_rotvec()
        if self.stage == 'ALIGN':
            self.count = self.count+1 if np.linalg.norm(error)<.008 and np.linalg.norm(rotation_error)<.12 else 0
            if self.count >= 3:
                self.stage='INSERT'
        # Stop insertion when lateral alignment is lost; never sweep sideways near fruit.
        local = self.rotation.T@(target-t[:3,3])
        blocked = self.stage == 'INSERT' and np.linalg.norm(local[:2])>.012
        if blocked:
            return np.r_[np.clip((q[:5]-targets[:5])/(self.speed*self.dt),-.2,.2),1.],dict(stage='ALIGNMENT_LOST',abort='ALIGNMENT_LOST')
        j=np.zeros((6,5));eps=1e-4
        for i in range(5):
            perturbed=q.copy();perturbed[i]+=eps;p=self.pose(perturbed)
            j[:3,i]=(p[:3,3]-t[:3,3])/eps
            j[3:,i]=Rotation.from_matrix(p[:3,:3]@t[:3,:3].T).as_rotvec()/eps
        v=error*2
        v*=min(1.,.025/max(np.linalg.norm(v),1e-9))
        weight=.15
        a=j.copy();a[3:]*=weight
        b=np.r_[v,weight*rotation_error*2]
        dq=a.T@np.linalg.solve(a@a.T+.02**2*np.eye(6),b)
        dq=np.clip(dq,-.2,.2)
        desired=np.clip(q[:5]+dq*self.dt,self.lower[:5]+.01,self.upper[:5]-.01)
        action=np.r_[np.clip((desired-targets[:5])/(self.speed*self.dt),-.25,.25),1.]
        return action,dict(stage=self.stage,abort=None,error_m=error.tolist(),lateral_error_m=float(np.linalg.norm(local[:2])))
