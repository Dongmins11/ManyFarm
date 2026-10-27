"""Fixed-dock estimate in odom. Capture stamps are never restamped as images."""
import math
import numpy as np
from .pose_control import rigid

def wrap(a):return math.atan2(math.sin(a),math.cos(a))
def yaw(t):return math.atan2(t[1,0],t[0,0])
def planar(x,y,a):
 t=np.eye(4);c,s=math.cos(a),math.sin(a);t[:2,:2]=[[c,-s],[s,c]];t[:2,3]=[x,y];return t

class FixedTargetTracker:
 def __init__(self,target,marker_id,config):
  self.target=rigid(target).copy();self.marker_id=marker_id;self.c=dict(config)
  for k in ('max_prediction_s','max_prediction_distance_m','max_prediction_yaw_rad','filter_alpha','max_innovation_m','max_innovation_yaw_rad','max_input_age_s'):
   if not math.isfinite(self.c[k]) or self.c[k]<=0:raise ValueError(k)
  if self.c['filter_alpha']>1:raise ValueError('filter_alpha')
  self.goal=None;self.stamp=None;self.last_attempt=None;self.origin=None;self.reason='no accepted marker';self.accepted_count=0
 def update(self,report,odom_base,now_ns,max_distance,max_tilt):
  stamp=report['stamp_ns']
  if self.last_attempt is not None and stamp<=self.last_attempt:return False
  self.last_attempt=stamp
  age=(now_ns-stamp)/1e9
  if not 0<=age<=self.c['max_input_age_s']:self.reason=f'observation age {age:.3f}s';return False
  m=next((m for m in report['markers'] if m['marker_id']==self.marker_id),None)
  if m is None:self.reason='target marker not visible';return False
  marker=np.eye(4);marker[:3,:3]=m['marker_rotation_in_base'];marker[:3,3]=m['marker_position_in_base_m']
  relative=rigid(marker)@self.target
  distance=float(np.linalg.norm(relative[:2,3]));tilt=math.acos(float(np.clip(relative[2,2],-1,1)))
  if distance>max_distance or tilt>max_tilt:
   self.reason=f'planar envelope: distance={distance:.3f}/{max_distance:.3f}m tilt={tilt:.3f}/{max_tilt:.3f}rad';return False
  goal=rigid(odom_base)@relative
  goal=planar(goal[0,3],goal[1,3],yaw(goal))
  if self.goal is not None:
   delta=float(np.linalg.norm(goal[:2,3]-self.goal[:2,3]));angle=wrap(yaw(goal)-yaw(self.goal))
   if delta>self.c['max_innovation_m'] or abs(angle)>self.c['max_innovation_yaw_rad']:
    self.reason=f'observation jump: {delta:.3f}m {angle:.3f}rad';return False
   a=self.c['filter_alpha'];xy=self.goal[:2,3]+a*(goal[:2,3]-self.goal[:2,3]);goal=planar(*xy,yaw(self.goal)+a*angle)
  self.goal=goal;self.stamp=stamp;self.origin=odom_base.copy();self.reason='';self.accepted_count+=1;return True
 def observation(self,odom_base,odom_stamp,now_ns):
  if self.goal is None:return None,self.reason
  age=(now_ns-self.stamp)/1e9
  distance=float(np.linalg.norm(odom_base[:2,3]-self.origin[:2,3]));angle=abs(wrap(yaw(odom_base)-yaw(self.origin)))
  if not 0<=age<=self.c['max_prediction_s'] or distance>self.c['max_prediction_distance_m'] or angle>self.c['max_prediction_yaw_rad']:
   return None,f'prediction limit: age={age:.3f}s travel={distance:.3f}m yaw={angle:.3f}rad; {self.reason}'
  # Synthetic marker is a control estimate at the odometry stamp, NOT a new camera observation.
  marker=np.linalg.inv(rigid(odom_base))@self.goal@np.linalg.inv(self.target)
  return dict(stamp_ns=odom_stamp,source_observation_stamp_ns=self.stamp,estimate=True,
    markers=[dict(marker_id=self.marker_id,marker_rotation_in_base=marker[:3,:3].tolist(),marker_position_in_base_m=marker[:3,3].tolist())]),''
