"""Marker-relative differential drive controller. No ROS or motor output."""
import math
import numpy as np


def rigid(value):
    t=np.asarray(value,dtype=float)
    if t.shape!=(4,4) or not np.isfinite(t).all():raise ValueError('Invalid target transform')
    if not np.allclose(t[3],[0,0,0,1],atol=1e-6):raise ValueError('Invalid homogeneous row')
    r=t[:3,:3]
    if not np.allclose(r.T@r,np.eye(3),atol=1e-5) or not np.isclose(np.linalg.det(r),1):
        raise ValueError('Invalid rotation')
    return t


class PID:
    def __init__(self,p,i,d,limit):
        self.p,self.i,self.d,self.limit=p,i,d,limit
        self.reset()
    def reset(self):self.integral=0.;self.previous=None
    def step(self,error,dt):
        derivative=0. if self.previous is None else (error-self.previous)/dt
        candidate=self.integral+error*dt
        raw=self.p*error+self.i*candidate+self.d*derivative
        output=max(-self.limit,min(self.limit,raw))
        if abs(raw)<=self.limit or raw*error<0:self.integral=candidate
        self.previous=error
        return output


class PoseController:
    def __init__(self,target,config):
        self.target=rigid(target['T_marker_base']);self.marker_id=target['marker_id']
        self.size=float(target['marker_size_m']);self.c=dict(config)
        for name in ('position_tolerance_m','yaw_tolerance_rad','max_linear_mps','max_angular_rps',
                     'rotate_first_rad','max_observation_age_s','max_planar_distance_m','max_tilt_rad'):
            if not math.isfinite(self.c[name]) or self.c[name]<=0:raise ValueError(name)
        if self.c['direction'] not in ('forward','reverse'):raise ValueError('direction')
        for key,upper in [('min_linear_mps','max_linear_mps'),('min_angular_rps','max_angular_rps')]:
            self.c.setdefault(key,0.)
            if not math.isfinite(self.c[key]) or not 0<=self.c[key]<=self.c[upper]:raise ValueError(key)
        self.c.setdefault('approach_yaw_deadband_rad',0.)
        if not math.isfinite(self.c['approach_yaw_deadband_rad']) or self.c['approach_yaw_deadband_rad']<0:raise ValueError('approach_yaw_deadband_rad')
        self.sign=1 if self.c['direction']=='forward' else -1
        self.controllers=[]
        for name,limit in (('linear',self.c['max_linear_mps']),('angular',self.c['max_angular_rps'])):
            gains=self.c[name+'_pid']
            if any(not math.isfinite(gains[k]) or gains[k]<0 for k in ('kp','ki','kd')):raise ValueError(name)
            self.controllers.append(PID(gains['kp'],gains['ki'],gains['kd'],limit))
        self.reset()
    def reset(self):
        for p in self.controllers:p.reset()
        self.last_stamp=None;self.settled=0
    def stop(self,reason):
        self.reset()
        return dict(phase='WAIT_OBSERVATION',reason=reason,linear_x=0.,angular_z=0.,at_target=False)
    def step(self,observation,now_ns,*,max_age=None):
        stamp=observation['stamp_ns'];age=(now_ns-stamp)/1e9
        age_limit=self.c['max_observation_age_s'] if max_age is None else max_age
        if not 0<=age<=age_limit:
            return self.stop(f'observation time invalid: age={age:.6f}s limit={age_limit:.3f}s stamp={stamp} now={now_ns}')
        if self.last_stamp is not None and stamp<=self.last_stamp:return self.stop('non-increasing timestamp')
        m=next((m for m in observation['markers'] if m['marker_id']==self.marker_id),None)
        if m is None:return self.stop('target marker not visible')
        current=np.eye(4);current[:3,:3]=m['marker_rotation_in_base'];current[:3,3]=m['marker_position_in_base_m']
        error=rigid(current)@self.target
        x,y,z=error[:3,3];rho=math.hypot(x,y)
        yaw=math.atan2(error[1,0],error[0,0])
        tilt=math.acos(max(-1.,min(1.,error[2,2])))
        if rho>self.c['max_planar_distance_m'] or tilt>self.c['max_tilt_rad']:
            return self.stop('outside validated planar envelope')
        dt=.1 if self.last_stamp is None else (stamp-self.last_stamp)/1e9
        if dt>self.c['max_observation_age_s']:
            for pid in self.controllers:pid.reset()
        dt=max(.001,min(dt,self.c['max_observation_age_s']));self.last_stamp=stamp
        at_position=rho<=self.c['position_tolerance_m']
        if not at_position and self.sign*x < -self.c['position_tolerance_m']:
            return self.stop('target behind selected approach direction; reposition required')
        if at_position:
            self.controllers[0].reset();v=0.
            if abs(yaw)<=self.c['yaw_tolerance_rad']:
                self.settled+=1;self.controllers[1].reset();w=0.;phase='SETTLING'
            else:
                self.settled=0;w=self.controllers[1].step(yaw,dt);phase='ALIGN_FINAL'
        else:
            self.settled=0
            # Robot is differential drive: lateral error needs a curved approach.
            alpha=math.atan2(self.sign*y,self.sign*x)
            w=self.controllers[1].step(alpha,dt)
            if abs(alpha)<=self.c['approach_yaw_deadband_rad']:
                w=0.;self.controllers[1].reset()
            if abs(alpha)>self.c['rotate_first_rad']:
                self.controllers[0].reset();v=0.;phase='ALIGN_APPROACH'
            else:
                blend=max(0.,1.-(abs(alpha)/self.c['rotate_first_rad'])**2)
                speed=max(self.c['min_linear_mps'],self.controllers[0].step(rho,dt))
                v=self.sign*speed*blend;phase='APPROACH'
        # The floor is applied before heading attenuation; rotation transition stays continuous.
        if w:w=math.copysign(max(abs(w),self.c['min_angular_rps']),w)
        done=self.settled>=self.c['settle_samples']
        if done:phase='AT_TARGET'
        return dict(phase=phase,linear_x=float(v),angular_z=float(w),at_target=done,
                    error_x_m=float(x),error_y_m=float(y),error_yaw_rad=yaw,
                    observation_age_s=age,shadow_only=True,
                    approach_bearing_rad=math.atan2(self.sign*y,self.sign*x))
