"""Binary transport variant of the frozen isolated Ultralytics worker."""
import argparse
import contextlib
import sys
import time
import numpy as np
from binary_protocol import BinaryChannel


def main():
    p=argparse.ArgumentParser();p.add_argument('--model',required=True);p.add_argument('--device',default='cpu');a=p.parse_args()
    with contextlib.redirect_stdout(sys.stderr):
        from ultralytics import YOLO
        model=YOLO(a.model)
    if model.task!='segment' or model.names!={0:'Red',1:'Yellow'}:raise ValueError('Unexpected detector contract')
    channel=BinaryChannel(sys.stdin.fileno(),sys.stdout.fileno())
    channel.send(dict(ready=True,names=model.names))
    while True:
        try:request,payload=channel.receive()
        except EOFError:return
        except TimeoutError:continue
        try:
            shape=request['shape']
            if (len(shape)!=3 or any(type(x) is not int or x<=0 for x in shape) or shape[2]!=3
                    or int(np.prod(shape))!=len(payload)):raise ValueError('Invalid RGB payload')
            rgb=np.frombuffer(payload,np.uint8).reshape(shape)
            start=time.perf_counter()
            with contextlib.redirect_stdout(sys.stderr):
                result=model.predict(source=rgb[...,::-1].copy(),imgsz=640,conf=request.get('confidence',.35),
                    device=a.device,retina_masks=True,verbose=False)[0]
            prediction=time.perf_counter()-start;start=time.perf_counter();detections=[];masks=[]
            if result.masks is not None:
                for box,mask in zip(result.boxes,result.masks.data):
                    m=mask.cpu().numpy()>.5
                    if m.shape!=rgb.shape[:2]:raise ValueError('Mask/image size mismatch')
                    c=int(box.cls.item());masks.append(np.packbits(m).tobytes())
                    detections.append(dict(class_id=c,label=model.names[c],confidence=float(box.conf.item()),
                        bbox=box.xyxy[0].cpu().tolist()))
            channel.send(dict(sequence=request['sequence'],detections=detections,
                timing=dict(prediction_s=prediction,mask_pack_s=time.perf_counter()-start)),b''.join(masks))
        except Exception as exc:channel.send(dict(sequence=request.get('sequence'),error=str(exc)))


if __name__=='__main__':main()
