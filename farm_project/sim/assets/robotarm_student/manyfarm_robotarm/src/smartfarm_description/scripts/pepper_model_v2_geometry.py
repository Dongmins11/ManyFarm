"""Measured body dimensions with a provisional lower taper. No USD/GPU imports."""
import numpy as np


def fit(points, profile):
    p=np.asarray(points,dtype=np.float64)
    if p.ndim!=2 or p.shape[1]!=3 or len(p)<4 or not np.isfinite(p).all():raise ValueError('Invalid mesh points')
    width=profile['body_max_width_m'];height=profile['body_height_m'];lower=profile['lower_body_max_width_m']
    fraction=profile['lower_body_height_fraction'];blend=profile['taper_blend_end_fraction']
    if not 0<lower<=width or height<=0 or not 0<fraction<blend<1:raise ValueError('Invalid measured dimensions/taper')
    cutoff=profile['source_body_cut_fraction_of_whole_height']*np.ptp(p[:,2])
    body_mask=p[:,2]<=cutoff;body=p[body_mask]
    if len(body)<4:raise ValueError('No body geometry')
    lo,hi=body[:,2].min(),body[:,2].max();span=hi-lo
    if span<=0:raise ValueError('Flat body')
    center_xy=(body[:,:2].min(0)+body[:,:2].max(0))/2
    xy=p[:,:2]-center_xy;t=(p[:,2]-lo)/span
    low_mask=body_mask & (t<=fraction)
    if low_mask.sum()<4:raise ValueError('No lower body samples')
    u=np.clip((t-fraction)/(blend-fraction),0,1);weight=u*u*(3-2*u)
    def transformed(a):return xy*(a+(1-a)*weight[:,None])
    def ratio(a):
        q=transformed(a)
        return np.ptp(q[low_mask],axis=0).max()/np.ptp(q[body_mask],axis=0).max()
    target=lower/width
    if ratio(1)<target:raise ValueError('Source bottom narrower than requested: review taper rather than expand silently')
    low,high=0.,1.
    for _ in range(60):
        a=(low+high)/2
        if ratio(a)<target:low=a
        else:high=a
    a=(low+high)/2;q=transformed(a);xy_scale=width/np.ptp(q[body_mask],axis=0).max()
    q*=xy_scale;z_scale=height/span
    center=profile['grasp_center_local_m'];out=np.column_stack((q+np.asarray(center[:2]),(p[:,2]-(lo+hi)/2)*z_scale+center[2]))
    return out,body_mask,low_mask,dict(source_body_cut_z=cutoff,source_body_bounds=[body.min(0).tolist(),body.max(0).tolist()],
        lower_radial_factor=a,xy_scale=xy_scale,z_scale=z_scale,source_xy_center=center_xy.tolist(),source_body_center_z=(lo+hi)/2,
        visual_whole_bounds_m=[out.min(0).tolist(),out.max(0).tolist()],
        body_dimensions_m=np.ptp(out[body_mask],axis=0).tolist(),lower_body_dimensions_m=np.ptp(out[low_mask],axis=0).tolist())


def transform_point(point, profile, fit_info):
    p=np.asarray(point,dtype=np.float64)
    lo,hi=np.asarray(fit_info['source_body_bounds'])[:,2];t=(p[2]-lo)/(hi-lo)
    u=np.clip((t-profile['lower_body_height_fraction'])/(profile['taper_blend_end_fraction']-profile['lower_body_height_fraction']),0,1)
    factor=fit_info['lower_radial_factor']+(1-fit_info['lower_radial_factor'])*u*u*(3-2*u)
    center=np.asarray(profile['grasp_center_local_m'])
    return np.r_[(p[:2]-fit_info['source_xy_center'])*factor*fit_info['xy_scale'],(p[2]-fit_info['source_body_center_z'])*fit_info['z_scale']]+center
