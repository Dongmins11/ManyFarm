"""Read-only perception evaluation on saved RGB-D; no robot actions or training."""
import argparse,json
from pathlib import Path
import numpy as np
from PIL import Image
from harvest_vision.client import Detector
from harvest_vision.geometry import Frame
from harvest_vision.pipeline import process,load_packet,save_packet
p=argparse.ArgumentParser();p.add_argument('--capture',type=Path,required=True)
p.add_argument('--output',type=Path,required=True);p.add_argument('--model',type=Path,required=True)
p.add_argument('--vision-python',type=Path,default=Path('.venvs/harvest_vision/bin/python'))
p.add_argument('--arm-roi',type=float,nargs=6,help='xmin ymin zmin xmax ymax zmax in arm frame')
p.add_argument('--device',default='cpu');p.add_argument('--centre-offset-m',type=float)
a=p.parse_args();a.output.mkdir(parents=True,exist_ok=False)
detector=Detector(a.vision_python,a.model,a.device)
try:
    if (a.capture/'report.json').exists():
        report=json.loads((a.capture/'report.json').read_text());frames=[]
        for name in ('right','rear'):
            root=a.capture/name;cal=json.loads((root/'calibration.json').read_text())
            frames.append(Frame(np.array(Image.open(root/'rgb.png').convert('RGB')),
                np.load(root/'aligned_depth_m.npy',allow_pickle=False),np.array(cal['intrinsics']['rgb']),
                np.linalg.inv(np.array(report['arm_base_world']))@np.array(cal['world_from_optical']['rgb']),
                0.,0.,name,clock_id='offline',calibration_verified=False))
    else:frames=[load_packet(a.capture)]
    for frame in frames:
        records,overlay=process(frame,detector,frame.stamp_s,a.centre_offset_m,None if a.arm_roi is None else (a.arm_roi[:3],a.arm_roi[3:]))
        root=a.output/frame.camera_id;save_packet(root,frame)
        Image.fromarray(overlay).save(root/'overlay.png');(root/'detections.json').write_text(json.dumps(records,indent=2))
        print(frame.camera_id,json.dumps(records),flush=True)
finally:detector.close()
