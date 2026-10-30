"""Opt-in CPU geometry acceleration; original sensor/vision modules stay frozen.

No fast-math, interpolation, depth filling, image resize or detector change.
Warm the kernels before timing or operating a control loop. Numerical equivalence
is checked by tests/recorded frames; it is not assumed for arbitrary calibration.
"""
import numpy as np
from numba import njit
from harvest_vision.geometry import Frame,locate
from .student60_native_fast import FrameDepthProjector


@njit(cache=True,nogil=True,fastmath=False)
def _project_one(x,y,z,kd,kc,t):
    xx=(x-kd[0,2])*z/kd[0,0];yy=(y-kd[1,2])*z/kd[1,1]
    a=xx*t[0,0]+yy*t[0,1]+z*t[0,2]+t[0,3]
    b=xx*t[1,0]+yy*t[1,1]+z*t[1,2]+t[1,3]
    c=xx*t[2,0]+yy*t[2,1]+z*t[2,2]+t[2,3]
    safe=c if c>0 else 1.
    u=int(np.rint(a/safe*kc[0,0]+kc[0,2]));v=int(np.rint(b/safe*kc[1,1]+kc[1,2]))
    return u,v,c


@njit(cache=True,nogil=True,fastmath=False)
def _align(raw,kd,kc,t,h,w):
    out=np.full((h,w),np.inf,np.float32)
    for y in range(raw.shape[0]):
        for x in range(raw.shape[1]):
            z=raw[y,x]
            if np.isfinite(z) and z>0:
                u,v,zz=_project_one(x,y,z,kd,kc,t)
                if zz>0 and 0<=u<w and 0<=v<h and zz<out[v,u]:out[v,u]=zz
    for y in range(h):
        for x in range(w):
            if not np.isfinite(out[y,x]):out[y,x]=0.
    return out


@njit(cache=True,nogil=True,fastmath=False)
def _projection(raw,kd,kc,t,h,w):
    us=np.empty(raw.shape,np.int64);vs=np.empty(raw.shape,np.int64);inside=np.empty(raw.shape,np.bool_)
    for y in range(raw.shape[0]):
        for x in range(raw.shape[1]):
            z=raw[y,x] if np.isfinite(raw[y,x]) and raw[y,x]>0 else np.float32(0)
            u,v,zz=_project_one(x,y,z,kd,kc,t);us[y,x]=u;vs[y,x]=v
            inside[y,x]=zz>0 and 0<=u<w and 0<=v<h
    return us,vs,inside


@njit(cache=True,nogil=True,fastmath=False)
def _mask(u,v,inside,finite,rgb_mask):
    result=np.zeros(inside.shape,np.bool_)
    for y in range(inside.shape[0]):
        for x in range(inside.shape[1]):
            if inside[y,x] and finite[y,x]:result[y,x]=rgb_mask[v[y,x],u[y,x]]
    return result


def align_depth_to_color(depth,kd,kc,color_from_depth,color_shape):
    return _align(depth,np.asarray(kd,np.float64),np.asarray(kc,np.float64),
        np.asarray(color_from_depth,np.float64),*color_shape)


class CompiledFrameDepthProjector(FrameDepthProjector):
    def __init__(self,raw_depth,kd,kc,color_from_depth,rgb_shape):
        self.raw=np.asarray(raw_depth);self.kd=np.asarray(kd);self.kc=np.asarray(kc)
        self.transform=np.asarray(color_from_depth);self.rgb_shape=rgb_shape
        self.finite=np.isfinite(self.raw)&(self.raw>0)
        self.u,self.v,self.inside=_projection(self.raw,np.asarray(kd,np.float64),np.asarray(kc,np.float64),
            np.asarray(color_from_depth,np.float64),*rgb_shape)

    def mask(self,rgb_mask):
        result=_mask(self.u,self.v,self.inside,self.finite,rgb_mask)
        if not result.any() or self.finite.all():return result
        # Same missing-pixel coverage accounting as the frozen implementation;
        # these mask bits never invent a missing depth value.
        reference=float(np.median(self.raw[result]));missing=~self.finite
        z=np.full(int(missing.sum()),reference,dtype=self.raw.dtype)
        y,x=np.nonzero(missing)
        u,v,inside=self.project(z,x,y)
        fallback=np.zeros(len(z),bool);fallback[inside]=rgb_mask[v[inside],u[inside]]
        result[missing]=fallback
        return result


def warmup():
    depth=np.ones((2,2),np.float32);k=np.eye(3);t=np.eye(4)
    align_depth_to_color(depth,k,k,t,(2,2));CompiledFrameDepthProjector(depth,k,k,t,(2,2)).mask(np.ones((2,2),bool))
    # LatestVision owns read-only snapshots. Numba specializes buffer mutability;
    # compile that path too, outside any control deadline.
    for value in [depth,k,t]:value.setflags(write=False)
    align_depth_to_color(depth,k,k,t,(2,2));CompiledFrameDepthProjector(depth,k,k,t,(2,2)).mask(np.ones((2,2),bool))


ALIGNMENT_CHECK=dict(calls=0,bit_identical=0)


def install_alignment(verify=False):
    """Process-only adapter; call after Isaac AppLauncher, before creating rig."""
    warmup()
    from . import isaac_rig
    ALIGNMENT_CHECK.update(calls=0,bit_identical=0)
    if verify:
        from harvest_rl.rgbd_geometry import align_depth_to_color as reference
        def checked(*args):
            result=align_depth_to_color(*args);expected=reference(*args)
            ALIGNMENT_CHECK['calls']+=1
            np.testing.assert_array_equal(result,expected)
            ALIGNMENT_CHECK['bit_identical']+=1
            return result
        isaac_rig.align_depth_to_color=checked
    else:isaac_rig.align_depth_to_color=align_depth_to_color


def process_native(frame,data,detector,now,centre_offset_m,arm_roi=None):
    """Same detection records, omitting the unused painted overlay."""
    frame.validate();records=[]
    detections=detector.predict(frame.rgb)
    if not detections:
        return records,None
    native=Frame(np.zeros(data['depth_m'].shape+(3,),np.uint8),data['depth_m'],data['intrinsics']['depth'],
        frame.arm_from_optical@data['color_from_depth'],frame.stamp_s,frame.pose_stamp_s,frame.camera_id,
        frame_id=frame.frame_id,clock_id=frame.clock_id,calibration_verified=frame.calibration_verified)
    projector=CompiledFrameDepthProjector(data['raw_depth_m'],data['intrinsics']['depth'],frame.k,
        data['color_from_depth'],frame.rgb.shape[:2])
    for detection in detections:
        mask=projector.mask(detection['mask'])
        point=locate(native,mask,now,centre_offset_m=centre_offset_m)
        record={k:v for k,v in detection.items() if k!='mask'};record.update(point)
        record['depth_coverage_grid']='native_depth';record['pixel_frame']='depth_optical'
        xyz=point['grasp_estimate_arm_m'] or point['surface_arm_m']
        inside=xyz is not None and (arm_roi is None or bool(np.all(np.asarray(xyz)>=arm_roi[0]) and np.all(np.asarray(xyz)<=arm_roi[1])))
        record['candidate_valid']=bool(point['valid'] and inside)
        record['candidate_reason']=point['reason'] if not point['valid'] else ('ok' if inside else 'outside_fruit_workspace')
        if not record['candidate_valid']:record['control_valid']=False
        records.append(record)
    return records,None
