"""Line-delimited JSON detector process; isolate Ultralytics from Isaac dependencies."""
import argparse,base64,contextlib,json,sys
import numpy as np
p=argparse.ArgumentParser();p.add_argument('--model',required=True);p.add_argument('--device',default='cpu');a=p.parse_args()
with contextlib.redirect_stdout(sys.stderr):
    from ultralytics import YOLO
    model=YOLO(a.model)
if model.task!='segment' or model.names!={0:'Red',1:'Yellow'}:raise ValueError(f'Unexpected detector contract: {model.task} {model.names}')
print(json.dumps({'ready':True,'names':model.names}),flush=True)
for line in sys.stdin:
    try:
        request=json.loads(line)
        rgb=np.frombuffer(base64.b64decode(request['rgb']),np.uint8).reshape(request['shape'])
        with contextlib.redirect_stdout(sys.stderr):
            # Ultralytics ndarray input is BGR. Our external contract is RGB.
            result=model.predict(source=rgb[...,::-1].copy(),imgsz=640,conf=request.get('confidence',.35),device=a.device,retina_masks=True,verbose=False)[0]
        detections=[]
        if result.masks is not None:
            for box,mask in zip(result.boxes,result.masks.data):
                m=mask.cpu().numpy()>.5
                if m.shape!=rgb.shape[:2]:raise ValueError('Mask/image size mismatch')
                c=int(box.cls.item())
                detections.append(dict(class_id=c,label=model.names[c],confidence=float(box.conf.item()),
                    bbox=box.xyxy[0].cpu().tolist(),mask=base64.b64encode(np.packbits(m).tobytes()).decode()))
        print(json.dumps({'detections':detections}),flush=True)
    except Exception as e:
        print(json.dumps({'error':str(e)}),flush=True)
