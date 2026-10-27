"""Station departure: acquire a fixed odom target, then reverse with mild steering.
No final yaw alignment. Never re-use this fixed target policy for a moving robot.
"""
import math
import numpy as np
from .pose_control import PoseController, rigid
from .target_tracker import FixedTargetTracker, planar, yaw

class DepartureController(PoseController):
    def __init__(self,target,config,departure):
        super().__init__(target,config)
        if self.sign!=-1:raise ValueError('departure requires reverse direction')
        self.d=dict(departure)
        for k in ('lookahead_m','steering_kp','max_heading_error_rad'):
            if not math.isfinite(self.d[k]) or self.d[k]<=0:raise ValueError(k)
    def step(self,observation,now_ns):
        stamp=observation['stamp_ns'];age=(now_ns-stamp)/1e9
        if not 0<=age<=self.c['max_observation_age_s']:return self.stop('departure odometry stale')
        if self.last_stamp is not None and stamp<=self.last_stamp:return self.stop('non-increasing odometry')
        m=next((m for m in observation['markers'] if m['marker_id']==self.marker_id),None)
        if m is None:return self.stop('departure target unavailable')
        current=np.eye(4);current[:3,:3]=m['marker_rotation_in_base'];current[:3,3]=m['marker_position_in_base_m']
        error=rigid(current)@self.target;x,y=error[:2,3];rho=math.hypot(x,y)
        if rho>self.c['max_planar_distance_m']:raise RuntimeError('departure outside distance envelope')
        self.last_stamp=stamp
        angle=math.atan2(-y,max(-x,self.d['lookahead_m']))
        if rho<=self.c['position_tolerance_m']:
            self.settled+=1;v=w=0.;phase='DEPARTURE_SETTLING'
        else:
            self.settled=0
            if x>0:raise RuntimeError('departure passed B outside arrival radius')
            if abs(math.atan2(-y,-x))>self.d['max_heading_error_rad']:
                raise RuntimeError('departure outside gentle reverse corridor')
            w=max(-self.c['max_angular_rps'],min(self.c['max_angular_rps'],self.d['steering_kp']*angle))
            speed=min(self.c['max_linear_mps'],max(self.c['min_linear_mps'],self.c['linear_pid']['kp']*rho))
            v=-speed*max(.5,math.cos(angle));phase='REVERSE_TO_B'
        done=self.settled>=self.c['settle_samples']
        return dict(phase='AT_TARGET' if done else phase,linear_x=float(v),angular_z=float(w),at_target=done,
                    error_x_m=float(x),error_y_m=float(y),error_yaw_rad=yaw(error),observation_age_s=age,shadow_only=True)

class DepartureTracker(FixedTargetTracker):
    def __init__(self,target,marker_id,config,departure):
        super().__init__(target,marker_id,config)
        self.d=dict(departure);self.samples=[];self.locked=False;self.locked_ns=None
        if type(self.d['acquire_samples']) is not int or self.d['acquire_samples']<3:raise ValueError('acquire_samples')
        for k in ('acquire_spread_m','acquire_timeout_s','max_odom_duration_s','max_odom_travel_m','max_odom_yaw_rad'):
            if not math.isfinite(self.d[k]) or self.d[k]<=0:raise ValueError(k)
    def update(self,report,odom_base,now_ns,max_distance,max_tilt):
        if self.locked:return False  # A noisy visual update must not move the departure goal.
        if not super().update(report,odom_base,now_ns,max_distance,max_tilt):return False
        self.samples.append((self.goal.copy(),self.stamp));self.samples=self.samples[-self.d['acquire_samples']:]
        if len(self.samples)<self.d['acquire_samples']:return True
        positions=np.array([g[:2,3] for g,_ in self.samples]);center=np.median(positions,axis=0)
        fresh=(self.samples[-1][1]-self.samples[0][1])/1e9<=self.d['acquire_timeout_s']
        if not fresh or np.max(np.linalg.norm(positions-center,axis=1))>self.d['acquire_spread_m']:return True
        self.goal=planar(*center,yaw(self.goal));self.locked=True;self.locked_ns=now_ns;self.origin=odom_base.copy()
        return True
    def observation(self,odom_base,odom_stamp,now_ns):
        if not self.locked:return None,'acquiring stable departure target'
        age=(now_ns-self.locked_ns)/1e9
        distance=np.linalg.norm(odom_base[:2,3]-self.origin[:2,3])
        angle=abs(math.atan2(math.sin(yaw(odom_base)-yaw(self.origin)),math.cos(yaw(odom_base)-yaw(self.origin))))
        if not 0<=age<=self.d['max_odom_duration_s'] or distance>self.d['max_odom_travel_m'] or angle>self.d['max_odom_yaw_rad']:
            raise RuntimeError('departure odometry continuation limit exceeded')
        marker=np.linalg.inv(rigid(odom_base))@self.goal@np.linalg.inv(self.target)
        return dict(stamp_ns=odom_stamp,source_observation_stamp_ns=self.stamp,estimate=True,
                    markers=[dict(marker_id=self.marker_id,marker_rotation_in_base=marker[:3,:3].tolist(),marker_position_in_base_m=marker[:3,3].tolist())]),''
