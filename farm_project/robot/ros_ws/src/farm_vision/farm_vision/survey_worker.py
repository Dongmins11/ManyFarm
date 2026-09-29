"""Persistent YOLO-environment worker. JSON requests via stdin; no ROS/GT imports."""
import argparse
import json
from pathlib import Path
import select
import sys
import time
import cv2
import numpy as np
from farm_common.rgbd_shm import RgbdReader
from .preprocess import prepare
from .detector import YoloSegmenter


def surface_sample(mask,depth,K,minimum=12):
    inside=cv2.erode(mask.astype(np.uint8),np.ones((3,3),np.uint8)).astype(bool)
    valid=inside & np.isfinite(depth) & (depth>.1) & (depth<5.)
    yy,xx=np.nonzero(valid)
    if len(xx)<minimum:return None
    my,mx=np.nonzero(mask)
    target=np.array([(mx.min()+mx.max())/2,(my.min()+my.max())/2])
    k=np.argmin((xx-target[0])**2+(yy-target[1])**2);u,v=int(xx[k]),int(yy[k])
    patch=depth[max(0,v-1):v+2,max(0,u-1):u+2]
    ok=valid[max(0,v-1):v+2,max(0,u-1):u+2]
    z=float(np.median(patch[ok]));K=np.asarray(K)
    return {'pixel_uv':[u,v],'depth_m':z,'valid_depth_pixels':len(xx),
            'position_camera_m':[(u-K[0,2])*z/K[0,0],(v-K[1,2])*z/K[1,1],z]}


def main(root):
    p=argparse.ArgumentParser();p.add_argument('--config',required=True);p.add_argument('--device',default='0')
    p.add_argument('--headless',action='store_true');a=p.parse_args()
    c=json.loads(Path(a.config).read_text());reader=RgbdReader(c['shm_name'])
    model=Path(c['model']);model=model if model.is_absolute() else root/model
    detector=YoloSegmenter(model,dict(c['inference'],input_size=c['preprocess']['input_size']),a.device)
    # Warm up before accepting a mission frame. Do not pay cold-start latency after capture.
    dummy=np.full((c['preprocess']['input_size'],)*2+(3,),114,np.uint8)
    detector.model.predict(source=dummy,imgsz=c['preprocess']['input_size'],rect=False,
        device=a.device,quantize=16 if c['inference'].get('half',False) and a.device!='cpu' else 32,
        verbose=False,save=False)
    cached=None;board=None
    def frame(after,session=None):
        end=time.monotonic()+10
        while time.monotonic()<end:
            f=reader.read(max_age=c['max_frame_age_s'])
            if f:
                if session and f['metadata']['session']!=session:raise RuntimeError('Camera restarted during mission')
                if f['metadata']['stamp_ns']>after:return f
            time.sleep(.01)
        raise RuntimeError('No fresh RGB-D frame after stop')
    print('FARM_RPC '+json.dumps({'ready':True}),flush=True)
    try:
        while True:
            if board is not None and not a.headless:
                cv2.imshow('B survey: stable IDs and harvest windows',board)
                cv2.waitKey(1)
            if not select.select([sys.stdin],[],[],.03)[0]:continue
            line=sys.stdin.readline()
            if not line:break
            req=json.loads(line)
            try:
                op=req['op']
                if op=='stop':break
                if op in ('info','capture'):
                    f=frame(req.get('after_stamp_ns',0),req.get('session'));meta=f['metadata']
                    result={'metadata':meta,'width':f['rgb'].shape[1],'height':f['rgb'].shape[0]}
                    if op=='capture':
                        t=time.perf_counter();net,valid,tr,geom=prepare(f['rgb'],meta,c['preprocess'])
                        detections,masks=detector.infer(net,valid,tr,f['rgb'].shape)
                        accepted=[];rejected=[];T=np.asarray(meta['T_odom_camera_optical'])
                        for i,(d,mask) in enumerate(zip(detections,masks)):
                            full=tr.mask_to_original(mask,result['width'],result['height'])
                            sample=surface_sample(full,f['depth'],meta['K'])
                            if sample is None:
                                rejected.append(dict(d,reason='insufficient_valid_depth'));continue
                            q=np.r_[sample['position_camera_m'],1.]
                            accepted.append(dict(d,**sample,position_odom_m=(T@q)[:3].tolist(),source_index=i))
                        if detections and not accepted:
                            raise RuntimeError('All detected fruit lack valid depth; observation not accepted')
                        age=time.monotonic()-meta['written_monotonic']
                        if age>c['max_frame_age_s']:raise RuntimeError('Inference frame expired; retry observation')
                        result.update(detections=accepted,rejected=rejected,geometry=geom,
                            timings={'capture_to_result_ms':age*1000,'preprocess_infer_depth_ms':(time.perf_counter()-t)*1000})
                        cached=(f,net,result)
                elif op=='annotate':
                    if cached is None:raise RuntimeError('No captured frame')
                    f,net,observation=cached;meta=f['metadata']
                    if int(req['stamp_ns'])!=int(meta['stamp_ns']):raise RuntimeError('Annotation capture mismatch')
                    board=f['rgb'][:,:,::-1].copy();K=np.array(meta['K'])
                    C=np.linalg.inv(np.array(req['T_map_odom'])@np.array(meta['T_odom_camera_optical']))
                    for item in req['labels']:
                        x0,y0,x1,y1=map(lambda x:int(round(x)),item['box'])
                        cv2.rectangle(board,(x0,y0),(x1,y1),(0,220,255),2)
                        cv2.putText(board,item['id'],(x0,max(14,y0-4)),cv2.FONT_HERSHEY_SIMPLEX,.4,(0,220,255),1)
                    edges=[(0,1),(0,2),(1,3),(2,3),(4,5),(4,6),(5,7),(6,7),(0,4),(1,5),(2,6),(3,7)]
                    for win in req['windows']:
                        if win.get('range_tolerance_m',0)>0 and 'acceptance_corners_map_m' in win:
                            outer=np.c_[win['acceptance_corners_map_m'],np.ones(8)]@C.T
                            if (outer[:,2]>.05).all():
                                ouv=outer[:,:3]@K.T;ouv=ouv[:,:2]/ouv[:,2:3]
                                if np.isfinite(ouv).all() and np.abs(ouv).max()<=1e6:
                                    for i,j in edges:
                                        cv2.line(board,tuple(np.rint(ouv[i]).astype(int)),tuple(np.rint(ouv[j]).astype(int)),(255,210,0),1)
                        pts=np.c_[win['corners_map_m'],np.ones(8)]@C.T
                        if (pts[:,2]<=.05).any():continue
                        uv=pts[:,:3]@K.T;uv=uv[:,:2]/uv[:,2:3]
                        if not np.isfinite(uv).all() or np.abs(uv).max()>1e6:continue
                        for i,j in edges:
                            cv2.line(board,tuple(np.rint(uv[i]).astype(int)),tuple(np.rint(uv[j]).astype(int)),(220,0,220),1)
                        if 0<=uv[0,0]<board.shape[1] and 0<=uv[0,1]<board.shape[0]:
                            cv2.putText(board,win['window_id'],tuple(np.rint(uv[0]).astype(int)),cv2.FONT_HERSHEY_SIMPLEX,.4,(220,0,220),1)
                    tolerances={w.get('range_tolerance_m',0) for w in req['windows']}
                    if any(t>0 for t in tolerances):
                        cv2.putText(board,f'Purple: nominal | Cyan: allowance {max(tolerances)*1000:.0f}mm',
                            (8,board.shape[0]-10),cv2.FONT_HERSHEY_SIMPLEX,.45,(255,210,0),1)
                    if req.get('segment_id'):
                        cv2.putText(board,'Segment: '+req['segment_id'],(8,18),
                            cv2.FONT_HERSHEY_SIMPLEX,.5,(255,255,255),1)
                    directory=Path(req['directory']);directory.mkdir(parents=True,exist_ok=True)
                    for name,img in [('rgb',f['rgb'][:,:,::-1]),('input',net),('annotated',board)]:
                        if not cv2.imwrite(str(directory/(name+'.png')),img):raise RuntimeError('Image write failed')
                    np.save(directory/'depth.npy',f['depth'])
                    (directory/'observation.json').write_text(json.dumps(dict(observation,labels=req['labels'],
                        section_id=req.get('section_id'),segment_id=req.get('segment_id'),
                        T_map_odom=req['T_map_odom'],windows=req['windows']),ensure_ascii=False,indent=2,allow_nan=False))
                    result={'saved':str(directory)}
                else:raise ValueError('Unknown operation')
                print('FARM_RPC '+json.dumps({'id':req['id'],'ok':True,'result':result},allow_nan=False),flush=True)
            except Exception as e:
                print('FARM_RPC '+json.dumps({'id':req['id'],'ok':False,'error':str(e)}),flush=True)
    finally:
        if not a.headless:cv2.destroyAllWindows()
