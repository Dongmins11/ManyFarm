"""Share native-depth projection within one fresh frame, preserving mask pixels.

No frame/depth/detection cache survives this call. Missing depth contributes to
coverage exactly as in native_vision; it is never filled with a synthetic value.
"""
import numpy as np
from PIL import Image, ImageDraw
from harvest_vision.geometry import Frame, locate


class FrameDepthProjector:
    def __init__(self,raw_depth,kd,kc,color_from_depth,rgb_shape):
        self.raw=np.asarray(raw_depth);self.kd=np.asarray(kd);self.kc=np.asarray(kc)
        self.transform=np.asarray(color_from_depth);self.rgb_shape=rgb_shape
        self.y,self.x=np.mgrid[:self.raw.shape[0],:self.raw.shape[1]]
        self.finite=np.isfinite(self.raw)&(self.raw>0)
        self.u,self.v,self.inside=self.project(np.where(self.finite,self.raw,0.),self.x,self.y)

    def project(self,z,x,y):
        kd,kc=self.kd,self.kc;t=self.transform
        # Preserve the frozen implementation's floating-point operation order.
        xyz=np.stack(((x-kd[0,2])*z/kd[0,0],(y-kd[1,2])*z/kd[1,1],z),-1)
        xyz=xyz@t[:3,:3].T+t[:3,3]
        safe=np.where(xyz[...,2]>0,xyz[...,2],1.)
        u=np.rint(xyz[...,0]/safe*kc[0,0]+kc[0,2]).astype(int)
        v=np.rint(xyz[...,1]/safe*kc[1,1]+kc[1,2]).astype(int)
        inside=(xyz[...,2]>0)&(u>=0)&(v>=0)&(u<self.rgb_shape[1])&(v<self.rgb_shape[0])
        return u,v,inside

    def mask(self,rgb_mask):
        result=np.zeros(self.raw.shape,bool)
        result[self.inside]=rgb_mask[self.v[self.inside],self.u[self.inside]]
        result&=self.finite
        if not result.any() or self.finite.all():return result
        reference=float(np.median(self.raw[result]))
        missing=~self.finite
        z=np.full(int(missing.sum()),reference,dtype=self.raw.dtype)
        u,v,inside=self.project(z,self.x[missing],self.y[missing])
        fallback=np.zeros(len(z),bool);fallback[inside]=rgb_mask[v[inside],u[inside]]
        result[missing]=fallback
        return result


def process_native(frame,data,detector,now,centre_offset_m,arm_roi=None):
    frame.validate();records=[];overlay=frame.rgb.copy()
    native=Frame(np.zeros(data['depth_m'].shape+(3,),np.uint8),data['depth_m'],data['intrinsics']['depth'],
        frame.arm_from_optical@data['color_from_depth'],frame.stamp_s,frame.pose_stamp_s,frame.camera_id,
        frame_id=frame.frame_id,clock_id=frame.clock_id,calibration_verified=frame.calibration_verified)
    projector=FrameDepthProjector(data['raw_depth_m'],data['intrinsics']['depth'],frame.k,
                                  data['color_from_depth'],frame.rgb.shape[:2])
    for d in detector.predict(frame.rgb):
        mask=projector.mask(d['mask'])
        point=locate(native,mask,now,centre_offset_m=centre_offset_m)
        record={k:v for k,v in d.items() if k!='mask'};record.update(point)
        record['depth_coverage_grid']='native_depth';record['pixel_frame']='depth_optical'
        xyz=point['grasp_estimate_arm_m'] or point['surface_arm_m']
        inside=xyz is not None and (arm_roi is None or bool(np.all(np.asarray(xyz)>=arm_roi[0]) and np.all(np.asarray(xyz)<=arm_roi[1])))
        record['candidate_valid']=bool(point['valid'] and inside)
        record['candidate_reason']=point['reason'] if not point['valid'] else ('ok' if inside else 'outside_fruit_workspace')
        if not record['candidate_valid']:record['control_valid']=False
        records.append(record)
        colour=np.array([255,60,60] if d['class_id']==0 else [255,230,0])
        overlay[d['mask']]=(overlay[d['mask']]*.55+colour*.45).astype(np.uint8)
    image=Image.fromarray(overlay);draw=ImageDraw.Draw(image)
    for r in records:
        draw.rectangle(r['bbox'],outline='white',width=2)
        draw.text((r['bbox'][0],max(0,r['bbox'][1]-12)),r['label']+' '+r['candidate_reason'],fill='white')
    return records,np.asarray(image)
