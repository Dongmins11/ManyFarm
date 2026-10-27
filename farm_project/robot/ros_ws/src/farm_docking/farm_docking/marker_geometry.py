"""Rigid pose composition shared by front/side camera observations.

T_base_marker = T_base_camera @ T_camera_marker (OpenCV optical frame).
No global localization update, velocity generation or target assumptions.
"""
import math
import numpy as np
import cv2


def transform_matrix(translation, quaternion):
    t=np.asarray(translation,dtype=float);q=np.asarray(quaternion,dtype=float)
    if t.shape!=(3,) or q.shape!=(4,) or not np.isfinite(t).all() or not np.isfinite(q).all():
        raise ValueError('Invalid TF translation/quaternion')
    norm=np.linalg.norm(q)
    if abs(norm-1)>1e-3:raise ValueError('TF quaternion must be normalized')
    x,y,z,w=q/norm
    r=np.array([[1-2*(y*y+z*z),2*(x*y-z*w),2*(x*z+y*w)],
                [2*(x*y+z*w),1-2*(x*x+z*z),2*(y*z-x*w)],
                [2*(x*z-y*w),2*(y*z+x*w),1-2*(x*x+y*y)]])
    out=np.eye(4);out[:3,:3]=r;out[:3,3]=t
    return out


def compose_marker(base_camera, rvec, tvec):
    camera_marker=np.eye(4)
    camera_marker[:3,:3]=cv2.Rodrigues(rvec)[0]
    camera_marker[:3,3]=np.asarray(tvec).reshape(3)
    if not np.isfinite(camera_marker).all():raise ValueError('Nonfinite marker pose')
    result=np.asarray(base_camera)@camera_marker
    inverse=np.linalg.inv(result)
    return dict(marker_position_in_base_m=result[:3,3].tolist(),
        marker_rotation_in_base=result[:3,:3].tolist(),
        base_position_in_marker_m=inverse[:3,3].tolist(),
        base_forward_in_marker=inverse[:3,0].tolist())


def solve_marker(obj,pixels,k,d,max_error_px=3.0):
    _,rvs,tvs,_=cv2.solvePnPGeneric(obj,pixels,k,d,flags=cv2.SOLVEPNP_IPPE_SQUARE)
    candidates=[]
    for rv,tv in zip(rvs,tvs):
        rv,tv=cv2.solvePnPRefineLM(obj,pixels,k,d,rv.copy(),tv.copy())
        rotation=cv2.Rodrigues(rv)[0];t=tv.reshape(3);p=-rotation.T@t
        if t[2]<=0 or p[2]<=0:continue
        projected=cv2.projectPoints(obj,rv,tv,k,d)[0].reshape(4,2)
        error=float(np.sqrt(np.mean(np.sum((projected-pixels)**2,axis=1))))
        if not math.isfinite(error) or error>max_error_px:continue
        candidates.append((error,rv,tv,p,rotation))
    return min(candidates,key=lambda item:item[0]) if candidates else None
