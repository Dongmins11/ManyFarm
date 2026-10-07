"""Tag geometry only. No motion controller or TF ownership policy."""
import math
import numpy as np
from .roi import roi_accept

# 실제 보정 ROI. 촬영 모니터의 가로/세로 60% roi60_candidate와 구분한다.
OBSERVATION_ROI = (0.6, 0.8)

def wrap(a):return math.atan2(math.sin(a),math.cos(a))
def matrix(q):
 x,y,a=q;c=math.cos(a);s=math.sin(a)
 return np.array([[c,-s,x],[s,c,y],[0.,0.,1.]])
def pose(t):return np.array([t[0,2],t[1,2],math.atan2(t[1,0],t[0,0])])
def transported(tag,old_odom,new_odom):
 return pose(matrix(tag)@np.linalg.inv(matrix(old_odom))@matrix(new_odom))
def correction(current,tag):
 # Bound each update, not departure error. Larger offsets converge in increments.
 current=np.asarray(current,float);tag=np.asarray(tag,float)
 if current.shape!=(3,) or tag.shape!=(3,) or not np.isfinite([current,tag]).all():raise ValueError('nonfinite_pose')
 delta=tag-current;delta[2]=wrap(delta[2])
 if np.linalg.norm(delta[:2])>.5 or abs(delta[2])>math.radians(30):
  raise ValueError('observation_disagreement_skip_only')
 step=.5*delta
 length=np.linalg.norm(step[:2])
 if length>.08:step[:2]*=.08/length
 step[2]=np.clip(step[2],-math.radians(5),math.radians(5))
 out=current+step;out[2]=wrap(out[2]);return out,delta

def observe(observer,record):
 stamp=int(record['source_stamp_ns']);c=observer.context
 if record['frame_id']!=observer.camera.optical_frame:raise ValueError('optical_frame_mismatch')
 ds=[dict(family=d['family'],tag_id=d['id'],corners=d['corners_rectified'],corner_convention='apriltag_c_p_v1',decision_margin=d['decision_margin'],hamming=d['hamming']) for d in record['detections']]
 ds=[d for d in ds if roi_accept(d,OBSERVATION_ROI)]
 frame=dict(stamp_ns=stamp,camera_info_stamp_ns=stamp,image_size=[1280,720],optical_frame=observer.camera.optical_frame,calibration_version=c.calibration_version,rectified=True,session_id=c.session_id,epoch=0,image_uid='capture:'+str(stamp),capture_time_model_valid=True,capture_time_source='read_completion_experimental_assumption')
 result=observer.observe(frame,ds);packet=result['selected']
 if packet is None:return None,result
 if len(packet['usable_candidates'])!=1:return None,result
 return packet['usable_candidates'][0],result

