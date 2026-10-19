"""Rectified RGB + aligned optical-Z metres -> arm-frame surface/centre prior."""
from dataclasses import dataclass
import numpy as np

@dataclass
class Frame:
    rgb: np.ndarray
    depth_m: np.ndarray
    k: np.ndarray
    arm_from_optical: np.ndarray
    stamp_s: float
    pose_stamp_s: float
    camera_id: str
    frame_id: str = 'arm_2/base_link'
    clock_id: str = 'simulation'
    calibration_verified: bool = False
    rectified: bool = True

    def validate(self):
        if self.rgb.dtype != np.uint8 or self.rgb.ndim!=3 or self.rgb.shape[2]!=3:
            raise ValueError('RGB must be HWC uint8 RGB')
        if self.depth_m.shape!=self.rgb.shape[:2] or self.depth_m.dtype.kind!='f':
            raise ValueError('Depth must be RGB-aligned optical-Z floating point metres')
        if not self.rectified:raise ValueError('Rectify RGB/depth before pinhole processing')
        k=np.asarray(self.k);t=np.asarray(self.arm_from_optical)
        if k.shape!=(3,3) or not np.isfinite(k).all() or k[0,0]<=0 or k[1,1]<=0 or not np.allclose(k[2],[0,0,1]) or abs(k[0,1])+abs(k[1,0])>1e-8:raise ValueError('Invalid rectified intrinsics')
        if t.shape!=(4,4) or not np.isfinite(t).all() or not np.allclose(t[3],[0,0,0,1]) or not np.allclose(t[:3,:3].T@t[:3,:3],np.eye(3),atol=1e-4) or not np.isclose(np.linalg.det(t[:3,:3]),1,atol=1e-4):raise ValueError('Invalid rigid transform')
        if not self.camera_id or not self.frame_id or not self.clock_id or not np.isfinite([self.stamp_s,self.pose_stamp_s]).all():raise ValueError('Require frame identities and finite timestamps')


def locate(frame,mask,now_s,*,min_depth=.28,max_depth=3.,ttl=.3,pose_tolerance=.05,
           min_pixels=30,min_fraction=.4,centre_offset_m=None,centre_verified=False):
    frame.validate()
    if not np.isfinite(now_s):raise ValueError('Invalid current timestamp')
    if centre_offset_m is not None and (not np.isfinite(centre_offset_m) or not 0<=centre_offset_m<=.1):raise ValueError('Invalid centre prior')
    out=dict(valid=False,control_valid=False,reason='',camera_id=frame.camera_id,frame_id=frame.frame_id,
        stamp_s=frame.stamp_s,clock_id=frame.clock_id,age_s=float(now_s-frame.stamp_s),
        calibration_verified=frame.calibration_verified,centre_verified=centre_verified,
        surface_arm_m=None,grasp_estimate_arm_m=None,centre_method='surface_plus_ray_offset_prior' if centre_offset_m is not None else 'unavailable')
    if not 0<=now_s-frame.stamp_s<=ttl:out['reason']='stale_or_future_frame';return out
    if abs(frame.pose_stamp_s-frame.stamp_s)>pose_tolerance:out['reason']='unsynchronised_pose';return out
    mask=np.asarray(mask,dtype=bool)
    if mask.shape!=frame.depth_m.shape:raise ValueError('Mask must match original RGB resolution')
    # Erode two pixels, excluding object boundaries and mixed background depth.
    core=mask.copy()
    for _ in range(2):
        p=np.pad(core,1);core=p[1:-1,1:-1]&p[:-2,1:-1]&p[2:,1:-1]&p[1:-1,:-2]&p[1:-1,2:]
    count=int(core.sum());z=frame.depth_m
    good=core & np.isfinite(z) & (z>=min_depth) & (z<=max_depth)
    fraction=float(good.sum()/max(1,count));out.update(valid_depth_fraction=fraction,depth_pixels=int(good.sum()))
    if good.sum()<min_pixels or fraction<min_fraction:out['reason']='insufficient_depth';return out
    median=float(np.median(z[good]));mad=float(np.median(np.abs(z[good]-median)))
    good &= np.abs(z-median)<=max(.005,3*1.4826*mad)
    if good.sum()<min_pixels:out['reason']='insufficient_inliers';return out
    y,x=np.nonzero(good);zz=z[good];k=frame.k
    xyz=np.stack(((x-k[0,2])*zz/k[0,0],(y-k[1,2])*zz/k[1,1],zz),axis=1)
    surface=np.median(xyz,axis=0);t=frame.arm_from_optical
    out.update(valid=True,reason='ok',surface_arm_m=(t[:3,:3]@surface+t[:3,3]).tolist(),
        pixel=[float(np.median(x)),float(np.median(y))],surface_optical_m=surface.tolist(),depth_mad_m=mad)
    if centre_offset_m is not None:
        centre=surface+centre_offset_m*surface/np.linalg.norm(surface)
        out['grasp_estimate_arm_m']=(t[:3,:3]@centre+t[:3,3]).tolist()
        out['control_valid']=bool(frame.calibration_verified and centre_verified)
    return out
