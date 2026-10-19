"""RGB segmentation -> native depth samples, without filling aligned holes.

At 1280 RGB / 848 depth, forward alignment is sparse even for perfect depth.
Depth coverage is assessed in native sensor pixels, not a denser RGB grid.
"""
import numpy as np
from PIL import Image,ImageDraw
from harvest_vision.geometry import Frame,locate


def native_mask(rgb_mask, raw_depth, kd, kc, color_from_depth):
    h,w=raw_depth.shape;y,x=np.mgrid[:h,:w]
    def project(z):
        xyz=np.stack(((x-kd[0,2])*z/kd[0,0],(y-kd[1,2])*z/kd[1,1],z),-1)
        xyz=xyz@color_from_depth[:3,:3].T+color_from_depth[:3,3]
        safe=np.where(xyz[:,:,2]>0,xyz[:,:,2],1.)
        u=np.rint(xyz[:,:,0]/safe*kc[0,0]+kc[0,2]).astype(int)
        v=np.rint(xyz[:,:,1]/safe*kc[1,1]+kc[1,2]).astype(int)
        inside=(xyz[:,:,2]>0)&(u>=0)&(v>=0)&(u<rgb_mask.shape[1])&(v<rgb_mask.shape[0])
        result=np.zeros((h,w),bool);result[inside]=rgb_mask[v[inside],u[inside]]
        return result
    finite=np.isfinite(raw_depth)&(raw_depth>0)
    observed=project(np.where(finite,raw_depth,0.))&finite
    if not observed.any():return observed
    # Missing native pixels still count in the coverage denominator. This
    # fallback projects only the segmentation mask; no depth value is invented.
    reference=float(np.median(raw_depth[observed]))
    return project(np.where(finite,raw_depth,reference))


def process_native(frame,data,detector,now,centre_offset_m,arm_roi=None):
    frame.validate();records=[];overlay=frame.rgb.copy()
    native=Frame(np.zeros(data['depth_m'].shape+(3,),np.uint8),data['depth_m'],data['intrinsics']['depth'],
        frame.arm_from_optical@data['color_from_depth'],frame.stamp_s,frame.pose_stamp_s,frame.camera_id,
        frame_id=frame.frame_id,clock_id=frame.clock_id,calibration_verified=frame.calibration_verified)
    for d in detector.predict(frame.rgb):
        mask=native_mask(d['mask'],data['raw_depth_m'],data['intrinsics']['depth'],frame.k,data['color_from_depth'])
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
