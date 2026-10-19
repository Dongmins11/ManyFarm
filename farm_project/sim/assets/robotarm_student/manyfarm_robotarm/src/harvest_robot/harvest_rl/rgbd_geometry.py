"""CPU geometry for nominal D435 preview and future calibrated sensor adapters."""
import numpy as np


def intrinsics(width, height, horizontal_fov_deg):
    if width <= 0 or height <= 0 or not 0 < horizontal_fov_deg < 180:
        raise ValueError('Invalid image/FOV')
    f = width/(2*np.tan(np.deg2rad(horizontal_fov_deg)/2))
    return np.array([[f,0,width/2],[0,f,height/2],[0,0,1]],dtype=np.float64)


def valid_depth(depth, minimum, maximum):
    """Return metres and an explicit mask. Invalid values are zero, not a far plane."""
    valid = np.isfinite(depth) & (depth >= minimum) & (depth <= maximum)
    return np.where(valid,depth,0).astype(np.float32), valid


def align_depth_to_color(depth, kd, kc, color_from_depth, color_shape):
    """Forward project native optical-Z depth with a z-buffer, preserving holes.

    No interpolation/dilation or invented measurements. Transform is in metres.
    Returns optical-Z depth in COLOR coordinates, not Euclidean range.
    """
    h,w = color_shape
    y,x=np.nonzero(np.isfinite(depth) & (depth>0))
    z=depth[y,x]
    xyz=np.stack(((x-kd[0,2])*z/kd[0,0],(y-kd[1,2])*z/kd[1,1],z),axis=1)
    xyz=xyz@color_from_depth[:3,:3].T+color_from_depth[:3,3]
    keep=xyz[:,2]>0
    xyz=xyz[keep]
    u=np.rint(xyz[:,0]/xyz[:,2]*kc[0,0]+kc[0,2]).astype(np.int64)
    v=np.rint(xyz[:,1]/xyz[:,2]*kc[1,1]+kc[1,2]).astype(np.int64)
    keep=(u>=0)&(u<w)&(v>=0)&(v<h)
    out=np.full(h*w,np.inf,dtype=np.float32)
    np.minimum.at(out,v[keep]*w+u[keep],xyz[keep,2])
    return np.where(np.isfinite(out),out,0).reshape(h,w)


def project(world_points, world_from_optical, k, shape):
    points=np.asarray(world_points,dtype=float).reshape(-1,3)
    camera=(points-world_from_optical[:3,3])@world_from_optical[:3,:3]
    z=camera[:,2]
    safe=np.where(np.abs(z)>1e-9,z,1e-9)
    uv=np.stack((camera[:,0]/safe*k[0,0]+k[0,2],camera[:,1]/safe*k[1,1]+k[1,2]),axis=1)
    h,w=shape
    visible=(z>0)&(uv[:,0]>=0)&(uv[:,0]<w)&(uv[:,1]>=0)&(uv[:,1]<h)
    return uv,z,visible


def depth_rgb(depth, near, far):
    """Fixed colour scale: near red, middle green, far blue; invalid black."""
    t=np.clip((depth-near)/(far-near),0,1)
    out=np.stack((np.clip(2-4*t,0,1),np.clip(2-np.abs(4*t-2),0,1),np.clip(4*t-2,0,1)),axis=-1)
    out[(depth<=0)|~np.isfinite(depth)]=0
    return (out*255).astype(np.uint8)
