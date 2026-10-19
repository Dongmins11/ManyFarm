"""Target magnification from observed rear RGB-D, never simulator geometry."""
import numpy as np
import torch
from torch.nn import functional as F

CROP_SIZE=96
CROP_FIELDS={'rear_target_rgb','rear_target_depth','rear_target_valid','elapsed_s'}
EXTENSION='observed_rear_target_crop96_elapsed_persistent_memory_v1'


def crop_arrays(rgb,depth,box,valid,elapsed_s,box_image_size=None):
    result=dict(rear_target_rgb=np.zeros((CROP_SIZE,CROP_SIZE,3),np.uint8),
        rear_target_depth=np.zeros((CROP_SIZE,CROP_SIZE),np.float32),
        rear_target_valid=np.array(False,np.bool_),elapsed_s=np.array(float(elapsed_s),np.float32))
    if not valid or box is None:return result
    box=np.asarray(box,float)
    if box.shape!=(4,) or not np.isfinite(box).all() or np.any(box[2:]<=box[:2]):return result
    h,w=rgb.shape[:2]
    if box_image_size is not None:
        bw,bh=box_image_size;box=box*np.array([w/bw,h/bh,w/bw,h/bh])
    center=(box[:2]+box[2:])/2
    half=np.maximum(box[2:]-box[:2],4)*.75
    lo=np.maximum(0,np.floor(center-half).astype(int));hi=np.minimum([w,h],np.ceil(center+half).astype(int))
    if np.any(hi-lo<2):return result
    x0,y0=lo;x1,y1=hi
    color=torch.from_numpy(np.ascontiguousarray(rgb[y0:y1,x0:x1])).permute(2,0,1)[None].float()
    depths=np.asarray(depth[y0:y1,x0:x1],np.float32)
    depths=np.where(np.isfinite(depths)&(depths>0)&(depths<=3),depths,0)
    result['rear_target_rgb']=F.interpolate(color,(CROP_SIZE,CROP_SIZE),mode='bilinear',align_corners=False)[0].permute(1,2,0).round().byte().numpy()
    result['rear_target_depth']=F.interpolate(torch.from_numpy(depths.copy())[None,None],(CROP_SIZE,CROP_SIZE),mode='nearest')[0,0].numpy()
    result['rear_target_valid']=np.array(True,np.bool_)
    return result


def observed_box(target,detections):
    if not target['valid']:return None
    matches=[]
    for record in detections:
        point=record.get('grasp_estimate_arm_m')
        if record.get('candidate_valid') and point is not None:
            distance=np.linalg.norm(np.asarray(point)-target['position_m'])
            if distance<=.03:matches.append((float(distance),-float(record.get('confidence',0)),record.get('bbox')))
    return min(matches,key=lambda row:row[:2])[2] if matches else None


def from_record(row,note,contract):
    # Old archives only retain reduced policy images. Mark their crop source
    # explicitly in cache metadata; do not claim native detail was recovered.
    streams=contract['camera_config']['views']['rear']['streams']['rgb']
    return crop_arrays(row['rgb'][1],row['depth_m'][1],observed_box(note['target'],note['detections']),
        note['target']['valid'],note['stamp_s'],(streams['width'],streams['height']))
