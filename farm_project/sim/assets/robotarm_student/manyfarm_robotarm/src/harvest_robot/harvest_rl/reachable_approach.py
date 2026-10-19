"""Bounded FK candidate planner for simulation approach diagnostics, not collision planning."""
import numpy as np
from scipy.optimize import least_squares, brentq
from scipy.spatial.transform import Rotation


def opening_angle(diameter, lower, upper):
    gap=lambda q:.0281*(1-np.cos(q))+.0616*np.sin(q)
    hi=min(float(upper),1.9)
    if gap(hi)<diameter+.012:raise ValueError('Insufficient gripper clearance')
    return brentq(lambda q:gap(q)-diameter-.012,max(0.,float(lower)),hi)


class ReachableApproach:
    def __init__(self, pose, lower, upper, diameter, dt=.05, speed=.8, gripper_speed=1.):
        self.pose=pose;self.lo=np.asarray(lower,dtype=float)+.02;self.hi=np.asarray(upper,dtype=float)-.02
        self.dt,self.speed,self.gripper_speed=dt,speed,gripper_speed
        self.jaw=opening_angle(diameter,lower[-1],upper[-1]);self.path=None;self.index=0;self.count=0
        self.target=None;self.elapsed=0.;self.best=float('inf');self.stall=0.;self.observations=[];self.bias=np.zeros(6);self.moved_time=0.
    def plan(self,q,target):
        q=np.asarray(q,dtype=float);target=np.asarray(target,dtype=float)
        def full(x):return np.r_[x,self.jaw]
        direction=target.copy();direction[2]=0;direction/=max(np.linalg.norm(direction),1e-6)
        def residual(x):
            t=self.pose(full(x))
            return np.r_[t[:3,3]-target,.03*(t[:3,2]+direction),.03*t[2,0]]
        rng=np.random.default_rng(17);candidates=[]
        seeds=[np.clip(q[:5],self.lo[:5],self.hi[:5])]+[rng.uniform(self.lo[:5],self.hi[:5]) for _ in range(11)]
        for seed in seeds:
            r=least_squares(residual,seed,bounds=(self.lo[:5],self.hi[:5]),max_nfev=100)
            final=full(r.x);t=self.pose(final)
            if np.linalg.norm(t[:3,3]-target)>.005 or np.dot(-t[:3,2],direction)<.6 or abs(t[2,0])>.35:continue
            rotation=t[:3,:3].copy();reverse=[final];valid=True
            # Check an entire insertion corridor, not only an endpoint.
            for distance in (.015,.03,.045,.06):
                point=target+rotation[:,2]*distance
                def corridor(x):
                    p=self.pose(full(x))
                    return np.r_[p[:3,3]-point,.1*Rotation.from_matrix(rotation@p[:3,:3].T).as_rotvec()]
                v=least_squares(corridor,reverse[-1][:5],bounds=(self.lo[:5],self.hi[:5]),max_nfev=80)
                p=self.pose(full(v.x))
                if np.linalg.norm(p[:3,3]-point)>.005 or np.linalg.norm(Rotation.from_matrix(rotation@p[:3,:3].T).as_rotvec())>.15:
                    valid=False;break
                reverse.append(full(v.x))
            if valid:candidates.append((np.linalg.norm(reverse[-1][:5]-q[:5]),list(reversed(reverse))))
        if not candidates:return False
        self.path=min(candidates,key=lambda x:x[0])[1];self.target=target.copy();return True
    def command(self,q,targets,target):
        q,targets,target=[np.asarray(x,dtype=float) for x in (q,targets,target)]
        self.elapsed+=self.dt
        if self.path is None:
            self.observations.append(target.copy())
            self.observations=self.observations[-10:]
            if len(self.observations)<10 or np.max(np.linalg.norm(np.asarray(self.observations)-target,axis=1))>.005:
                return np.zeros(6),dict(abort='TARGET_UNSTABLE' if self.elapsed>3. else None,ready=False,stage='WAIT_STABLE_TARGET')
            if not self.plan(q,target):return np.zeros(6),dict(abort='NO_REACHABLE_APPROACH',ready=False)
        abort=None
        if np.linalg.norm(target-self.target)>.02:
            self.moved_time+=self.dt
            hold=np.clip((q-targets)/(np.r_[np.full(5,self.speed),self.gripper_speed]*self.dt),-.25,.25)
            return hold,dict(abort='TARGET_MOVED' if self.moved_time>=.25 else None,ready=False,stage='VERIFY_TARGET_MOVE',target_shift_m=float(np.linalg.norm(target-self.target)))
        self.moved_time=0.
        if self.elapsed>20:abort='APPROACH_TIMEOUT'
        goal=self.path[self.index];actual=self.pose(q);desired=self.pose(goal)
        err=float(np.linalg.norm(actual[:3,3]-desired[:3,3]))
        progress=float(np.linalg.norm(goal-q))
        if progress<self.best-.005:self.best=progress;self.stall=0.
        else:self.stall+=self.dt
        if self.stall>3:abort='APPROACH_STALLED'
        arrived=np.max(np.abs(goal-q))<.035 and err<.006
        self.count=self.count+1 if arrived else 0
        ready=False
        if self.count>=3:
            if self.index==len(self.path)-1:ready=True
            else:self.index+=1;self.count=0;self.best=float('inf');self.stall=0.
        # Bounded tracking of a planned joint pose, with bounded target lead.
        # Integrate only small residuals near the waypoint; never compensate the jaw.
        residual=goal-q
        eligible=(np.abs(residual[:5])<.08) & (targets[:5]>self.lo[:5]+.01) & (targets[:5]<self.hi[:5]-.01)
        if not abort and not ready:
            self.bias[:5]=np.clip(self.bias[:5]+np.where(eligible,.5*self.dt*residual[:5],0.),-.05,.05)
        compensated=np.clip(goal+self.bias,self.lo,self.hi)
        step=np.clip(compensated-targets,-.15*self.dt,.15*self.dt)
        desired_q=np.clip(targets+step,q-.12,q+.12)
        desired_q=np.clip(desired_q,self.lo,self.hi)
        command=np.clip((desired_q-targets)/(np.r_[np.full(5,self.speed),self.gripper_speed]*self.dt),-.25,.25)
        if abort:command=np.clip((q-targets)/(np.r_[np.full(5,self.speed),self.gripper_speed]*self.dt),-.25,.25)
        elif ready:command=np.zeros(6)  # Preserve compensated hold target on completion.
        return command,dict(abort=abort,ready=ready,stage='PREPOSE' if self.index==0 else 'INSERT',waypoint=self.index,error_m=err,jaw_rad=self.jaw,measured_q=q.tolist(),previous_targets=targets.tolist(),waypoint_q=goal.tolist(),tracking_bias_rad=self.bias.tolist())
