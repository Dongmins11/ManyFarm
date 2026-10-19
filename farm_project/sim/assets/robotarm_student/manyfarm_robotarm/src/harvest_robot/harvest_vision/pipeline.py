import json
from pathlib import Path
import numpy as np
from PIL import Image,ImageDraw
from .geometry import Frame,locate


def process(frame,detector,now_s,centre_offset_m=None,arm_roi=None):
    frame.validate();records=[];image=frame.rgb.copy()
    for d in detector.predict(frame.rgb):
        point=locate(frame,d['mask'],now_s,centre_offset_m=centre_offset_m)
        record={k:v for k,v in d.items() if k!='mask'};record.update(point)
        xyz=point['grasp_estimate_arm_m'] or point['surface_arm_m']
        inside=xyz is not None and (arm_roi is None or bool(np.all(np.asarray(xyz)>=arm_roi[0]) and np.all(np.asarray(xyz)<=arm_roi[1])))
        record['candidate_valid']=bool(point['valid'] and inside)
        record['candidate_reason']=point['reason'] if not point['valid'] else ('ok' if inside else 'outside_fruit_workspace')
        if not record['candidate_valid']:record['control_valid']=False
        records.append(record)
        color=np.array([255,60,60] if d['class_id']==0 else [255,230,0])
        image[d['mask']]=(image[d['mask']]*.55+color*.45).astype(np.uint8)
    image=Image.fromarray(image);draw=ImageDraw.Draw(image)
    for r in records:
        draw.rectangle(r['bbox'],outline='white',width=2)
        xyz=r['grasp_estimate_arm_m'] or r['surface_arm_m']
        label=f"{r['label']} {r['confidence']:.2f} {'OK' if r['candidate_valid'] else 'REJECT'} " + (','.join(f'{v:.3f}' for v in xyz) if xyz else r['reason'])
        draw.text((r['bbox'][0],max(0,r['bbox'][1]-12)),label,fill='white')
        if 'pixel' in r:
            u,v=r['pixel'];draw.ellipse((u-3,v-3,u+3,v+3),fill='cyan')
    return records,np.asarray(image)


def save_packet(path,frame):
    path=Path(path);path.mkdir(parents=True,exist_ok=True)
    np.savez_compressed(path/'frame.npz',rgb=frame.rgb,depth_m=frame.depth_m,k=frame.k,arm_from_optical=frame.arm_from_optical)
    meta={k:v for k,v in vars(frame).items() if not isinstance(v,np.ndarray)}
    (path/'frame.json').write_text(json.dumps(meta,indent=2))


def load_packet(path):
    path=Path(path);meta=json.loads((path/'frame.json').read_text())
    with np.load(path/'frame.npz',allow_pickle=False) as a:frame=Frame(**meta,**{k:a[k] for k in a.files})
    frame.validate();return frame
