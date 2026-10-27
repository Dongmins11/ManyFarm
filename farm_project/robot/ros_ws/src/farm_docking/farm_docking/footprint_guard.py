"""Finite scan endpoints versus padded swept footprint. No ROS dependencies."""
import math
import numpy as np

class FootprintGuard:
    def __init__(self, polygon, config):
        self.poly=np.asarray(polygon,dtype=float); self.c=dict(config)
        if self.poly.ndim!=2 or self.poly.shape[1]!=2 or len(self.poly)<3 or not np.isfinite(self.poly).all():raise ValueError('invalid footprint')
        edges=np.roll(self.poly,-1,axis=0)-self.poly
        cross=np.cross(edges,np.roll(edges,-1,axis=0))
        if not (np.all(cross>0) or np.all(cross<0)):raise ValueError('footprint must be strictly convex')
        for key in ('margin_m','reaction_s','linear_decel_mps2','angular_decel_rps2','sample_motion_m','max_linear_mps','max_angular_rps'):
            if not math.isfinite(config[key]) or config[key]<=0:raise ValueError('invalid guard '+key)
        self.radius=float(np.linalg.norm(self.poly,axis=1).max())
        self.edges=np.roll(self.poly,-1,axis=0)-self.poly
        self.edge_lengths2=np.sum(self.edges*self.edges,axis=1)
        lo=self.poly.min(axis=0);hi=self.poly.max(axis=0)
        self.rectangle=(lo,hi) if len(self.poly)==4 and len({tuple(v) for v in self.poly})==4 and all(v[0] in (lo[0],hi[0]) and v[1] in (lo[1],hi[1]) for v in self.poly) else None

    def hit(self,points,pose):
        x,y,yaw=pose;c,s=math.cos(yaw),math.sin(yaw)
        q=(points-[x,y])@np.array([[c,-s],[s,c]])
        edges=self.edges
        rel=q[:,None,:]-self.poly[None,:,:]
        cross=edges[None,:,0]*rel[:,:,1]-edges[None,:,1]*rel[:,:,0]
        inside=np.all(cross>=0,axis=1)|np.all(cross<=0,axis=1)
        u=np.clip(np.sum(rel*edges,axis=2)/self.edge_lengths2,0,1)
        dist=np.linalg.norm(rel-u[:,:,None]*edges,axis=2).min(axis=1)
        # Cover the gap between discrete trajectory samples conservatively.
        ids=np.flatnonzero(inside|(dist<=self.c['margin_m']+self.c['sample_motion_m']))
        return int(ids[0]) if len(ids) else None

    def check(self,points,v,w,extra_delay_s=0.):
        points=np.asarray(points,dtype=float).reshape(-1,2)
        if not np.isfinite(points).all() or not all(math.isfinite(k) for k in (v,w)):raise ValueError('nonfinite collision input')
        if abs(v)>self.c['max_linear_mps'] or abs(w)>self.c['max_angular_rps']:raise RuntimeError('collision guard velocity envelope exceeded')
        if not len(points):return None
        if v==0. and w==0.:
            hit=self.hit(points,(0.,0.,0.))
            return None if hit is None else dict(time_s=0.,point=points[hit].tolist())
        if not math.isfinite(extra_delay_s) or extra_delay_s<0:raise ValueError('invalid scan delay')
        reaction=self.c['reaction_s']+extra_delay_s
        duration=reaction+max(abs(v)/self.c['linear_decel_mps2'],abs(w)/self.c['angular_decel_rps2'])
        # Conservative broad phase: no trajectory point can travel farther than
        # integral of translational speed over reaction plus braking.
        reach=self.radius+self.c['margin_m']+self.c['sample_motion_m']+abs(v)*reaction+v*v/(2*self.c['linear_decel_mps2'])+abs(v)*.025
        points=points[np.sum(points*points,axis=1)<=reach*reach]
        if not len(points):return None
        dt=min(.025,self.c['sample_motion_m']/max(abs(v)+self.radius*abs(w),.001))
        x=y=yaw=t=0.
        poses=[];times=[]
        while True:
            poses.append((x,y,yaw));times.append(t)
            if t>=duration:break
            h=min(dt,duration-t)
            # Upper-bound remaining speed during each integration interval.
            elapsed=max(0.,t-reaction)
            vt=math.copysign(max(0.,abs(v)-self.c['linear_decel_mps2']*elapsed),v)
            wt=math.copysign(max(0.,abs(w)-self.c['angular_decel_rps2']*elapsed),w)
            if abs(wt)>1e-9:
                x+=vt/wt*(math.sin(yaw+wt*h)-math.sin(yaw));y+=vt/wt*(-math.cos(yaw+wt*h)+math.cos(yaw))
            else:x+=vt*math.cos(yaw)*h;y+=vt*math.sin(yaw)*h
            yaw+=wt*h;t+=h
        # Same trajectory samples and first-hit ordering, evaluated in batches.
        # Avoid many tiny NumPy calls for every predicted pose.
        for start in range(0,len(poses),64):
            pose=np.asarray(poses[start:start+64])
            delta=points[None,:,:]-pose[:,None,:2]
            c=np.cos(pose[:,2])[:,None];sn=np.sin(pose[:,2])[:,None]
            q=np.stack((delta[:,:,0]*c+delta[:,:,1]*sn,
                        -delta[:,:,0]*sn+delta[:,:,1]*c),axis=-1)
            if self.rectangle is not None:
                lo,hi=self.rectangle
                outside=np.maximum(np.maximum(lo-q,q-hi),0.)
                dist=np.sqrt(np.sum(outside*outside,axis=2))
                hits=dist<=self.c['margin_m']+self.c['sample_motion_m']
            else:
                rel=q[:,:,None,:]-self.poly[None,None,:,:]
                cross=self.edges[None,None,:,0]*rel[:,:,:,1]-self.edges[None,None,:,1]*rel[:,:,:,0]
                inside=np.all(cross>=0,axis=2)|np.all(cross<=0,axis=2)
                u=np.clip(np.sum(rel*self.edges,axis=3)/self.edge_lengths2,0,1)
                offset=rel-u[:,:,:,None]*self.edges
                dist=np.sqrt(np.sum(offset*offset,axis=3)).min(axis=2)
                hits=inside|(dist<=self.c['margin_m']+self.c['sample_motion_m'])
            indices=np.argwhere(hits)
            if len(indices):
                ti,pi=indices[0]
                return dict(time_s=times[start+int(ti)],point=points[int(pi)].tolist())
        return None
