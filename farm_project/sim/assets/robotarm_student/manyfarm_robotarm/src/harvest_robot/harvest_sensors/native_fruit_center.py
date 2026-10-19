"""Optional robust fruit-body centre from observed native depth surface points.

Uses segmentation, factory calibration and a nominal size prior only. No scene
geometry, fruit pose, segmentation IDs, simulator contacts or hidden state.
"""
import numpy as np
from scipy.optimize import least_squares
from .native_vision import process_native as baseline,native_mask


def fit_body_center(points,radius=.035):
    points=np.asarray(points,float)
    points=points[np.isfinite(points).all(1)]
    if len(points)<40:return None,dict(valid=False,reason='too_few_surface_points')
    median=np.median(points,axis=0)
    points=points[np.abs(points[:,2]-median[2])<radius*1.6]
    if len(points)<40:return None,dict(valid=False,reason='inconsistent_surface_depth')
    if len(points)>512:points=points[np.linspace(0,len(points)-1,512).astype(int)]
    center=median+radius*.8*median/np.linalg.norm(median)
    n=len(points)
    def residual(x):
        surface=np.linalg.norm(points-x[:3],axis=1)-x[3]
        return np.r_[surface,(x[3]-radius)*np.sqrt(n)*.35]
    lo=np.r_[median-radius*1.8,radius*.8];hi=np.r_[median+radius*1.8,radius*1.2]
    lo[2]=np.quantile(points[:,2],.05)
    fitted=least_squares(residual,np.r_[center,radius],bounds=(lo,hi),loss='soft_l1',
                         f_scale=.002,max_nfev=50)
    distances=np.abs(np.linalg.norm(points-fitted.x[:3],axis=1)-fitted.x[3])
    error=float(np.median(distances));coverage=float(np.mean(distances<.006))
    valid=bool(fitted.success and error<.004 and coverage>=.75 and np.isfinite(fitted.x).all())
    return (fitted.x[:3] if valid else None),dict(valid=valid,reason='robust_surface_sphere' if valid else 'surface_fit_unreliable',
        points=n,median_surface_residual_m=error,inlier_fraction=coverage,fitted_radius_m=float(fitted.x[3]))


def process_native(frame,data,detector,now,centre_offset_m,arm_roi=None):
    class RetainedDetector:
        def predict(self,image):
            self.detections=detector.predict(image)
            return self.detections
    proxy=RetainedDetector()
    records,overlay=baseline(frame,data,proxy,now,centre_offset_m,arm_roi)
    depth=data['depth_m'];kd=np.asarray(data['intrinsics']['depth'])
    arm_from_depth=frame.arm_from_optical@data['color_from_depth']
    for record,detected in zip(records,proxy.detections):
        if not record.get('candidate_valid'):continue
        mask=native_mask(detected['mask'],data['raw_depth_m'],kd,frame.k,data['color_from_depth'])
        valid=mask&np.isfinite(depth)&(depth>0)&(depth<=3)
        y,x=np.where(valid);z=depth[y,x]
        points=np.stack(((x-kd[0,2])*z/kd[0,0],(y-kd[1,2])*z/kd[1,1],z),-1)
        center,diagnostic=fit_body_center(points)
        record['body_center_fit']=diagnostic
        if center is None:continue
        estimate=(arm_from_depth@np.r_[center,1])[:3]
        if arm_roi is not None and (np.any(estimate<arm_roi[0]) or np.any(estimate>arm_roi[1])):continue
        record['ray_prior_estimate_arm_m']=record['grasp_estimate_arm_m']
        record['grasp_estimate_arm_m']=estimate.tolist();record['centre_method']='robust_native_depth_body_sphere'
    return records,overlay
