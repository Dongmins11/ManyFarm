"""Latest-frame shared-memory preview. No ROS, motion commands or simulated truth labels."""
import argparse
from collections import Counter
from datetime import datetime
import json
import math
from pathlib import Path
import time

import cv2
import numpy as np
from farm_common.rgbd_shm import RgbdReader
from farm_vision.preprocess import prepare, GeometryError


def render(rgb, network, masks, detections, geometry, status, preview_only=False):
    raw = np.ascontiguousarray(rgb[:,:,::-1])
    cv2.polylines(raw,[np.rint(geometry['polygon_original_px']).astype(np.int32)],True,(255,255,0),2)
    overlay = network.copy()
    for mask,item in zip(masks,detections):
        color = np.array((0,0,255) if item['class_name'].lower() == 'red' else (0,230,255),np.uint8)
        overlay[mask] = (overlay[mask]*.6+color*.4).astype(np.uint8)
        x0,y0,x1,y1 = item['mask_box_network_xyxy']
        cv2.rectangle(overlay,(x0,y0),(x1,y1),tuple(map(int,color)),1)
        label = f"{item['class_name']} {item['confidence']:.2f}"
        cv2.putText(overlay,label,(x0,max(15,y0-5)),cv2.FONT_HERSHEY_SIMPLEX,.45,tuple(map(int,color)),1)
    n = network.shape[0]
    left = np.full((n,n,3),30,np.uint8)
    ratio = min(n/raw.shape[1],n/raw.shape[0]);w,h = round(raw.shape[1]*ratio),round(raw.shape[0]*ratio)
    left[(n-h)//2:(n-h)//2+h,(n-w)//2:(n-w)//2+w] = cv2.resize(raw,(w,h))
    board = np.hstack([left,overlay])
    cv2.rectangle(board,(0,0),(2*n,55),(20,20,20),-1)
    cv2.putText(board,'RGB + B observation ROI',(10,22),cv2.FONT_HERSHEY_SIMPLEX,.55,(255,255,255),1)
    title = 'B crop + padding (YOLO OFF)' if preview_only else 'B crop + padding + YOLO'
    cv2.putText(board,title,(n+10,22),cv2.FONT_HERSHEY_SIMPLEX,.55,(255,255,255),1)
    cv2.putText(board,status,(10,46),cv2.FONT_HERSHEY_SIMPLEX,.5,(255,255,255),1)
    return board,overlay


def save_snapshot(directory, frame, network, annotated, record, masks, transform):
    directory.mkdir(parents=True,exist_ok=True)
    name = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
    prefix = directory/name
    for suffix,img in [('rgb',frame['rgb'][:,:,::-1]),('input',network),('result',annotated)]:
        if not cv2.imwrite(str(prefix)+f'_{suffix}.png',img): raise OSError('Image save failed')
    np.save(str(prefix)+'_depth.npy',frame['depth'])
    h,w = frame['rgb'].shape[:2]
    # Snapshot only: preserve actual segment masks and the exact original-pixel mapping.
    restored = np.stack([transform.mask_to_original(m,w,h) for m in masks]) if masks else np.empty((0,h,w),bool)
    np.savez_compressed(str(prefix)+'_masks.npz',masks=restored)
    Path(str(prefix)+'.json').write_text(json.dumps(record,ensure_ascii=False,indent=2,allow_nan=False))
    print(f'[vision] saved {prefix}',flush=True)


def main(argv=None, project_root=None):
    parser = argparse.ArgumentParser(description='Shared RGB-D → B crop → YOLO segmentation')
    parser.add_argument('--config',required=True)
    parser.add_argument('--model',default=None)
    parser.add_argument('--device',default='0')
    parser.add_argument('--preview-only',action='store_true',help='ROI/padding only; do not load YOLO')
    parser.add_argument('--headless',action='store_true')
    parser.add_argument('--max-frames',type=int,default=0)
    parser.add_argument('--save-dir',default=None)
    args = parser.parse_args(argv)
    config_path = Path(args.config).expanduser().resolve()
    config = json.loads(config_path.read_text())
    root = Path(project_root).resolve() if project_root else config_path.parent
    def resolve(path):
        p = Path(path).expanduser();return p if p.is_absolute() else root/p
    c = config['preprocess']; inference = dict(config['inference'],input_size=c['input_size'])
    fps = float(config['max_fps']);max_age = float(config['max_frame_age_s'])
    if not math.isfinite(fps) or not 0 < fps <= 120 or not math.isfinite(max_age) or max_age <= 0:
        raise ValueError('Invalid max_fps/max_frame_age_s')
    if not 0 <= inference['confidence'] <= 1 or not 0 <= inference['iou'] <= 1:
        raise ValueError('confidence and iou must be between zero and one')
    detector = None
    if not args.preview_only:
        from farm_vision.detector import YoloSegmenter
        detector = YoloSegmenter(resolve(args.model or config['model']),inference,args.device)
        print(f'[vision] model classes={detector.names}; device={args.device}',flush=True)
    reader = RgbdReader(config['shm_name'])
    save_dir = resolve(args.save_dir or config['save_dir'])
    print('[vision] Waiting for RGB-D. Q/ESC: quit, S: save current frame. No motion commands.',flush=True)
    print(f'[vision] B height band={c["height_band_m"]}m (prototype values); plane distance={c["camera_to_bed_plane_m"]}m',flush=True)
    window = 'Scout B vision'
    if not args.headless:
        cv2.namedWindow(window,cv2.WINDOW_NORMAL);cv2.resizeWindow(window,1280,640)
    last_notice = 0.;last_processed = 0.;last_frame = None;last_valid = 0.
    count=0;last_key=None;fps_start=time.perf_counter();fps_count=0;measured_fps=0.
    try:
        while True:
            now = time.monotonic()
            frame = reader.read(max_age=max_age) if now-last_processed >= 1/fps else None
            if frame is not None:
                last_processed = now
                meta = frame['metadata']
                key=(meta['session'],int(meta['stamp_ns']))
                if last_key is not None and key[0] == last_key[0] and key[1] <= last_key[1]:
                    continue  # Do not infer the same simulated capture twice or after a backward clock jump.
                last_key=key
                started=time.perf_counter()
                try:
                    network,valid,transform,geometry = prepare(frame['rgb'],meta,c)
                except GeometryError as error:
                    last_frame=None
                    last_valid=meta['written_monotonic']  # Camera is fresh; preserve ROI error on screen.
                    if now-last_notice > 1:
                        print(f'[vision] ROI ERROR: {error}',flush=True);last_notice=now
                    if not args.headless:
                        board=np.zeros((640,1280,3),np.uint8)
                        cv2.putText(board,str(error),(15,100),cv2.FONT_HERSHEY_SIMPLEX,.65,(0,0,255),1)
                        cv2.imshow(window,board)
                    if not args.headless and (cv2.waitKey(1)&0xff) in (27,ord('q')): break
                    continue
                prepared=time.perf_counter()
                detections,masks = detector.infer(network,valid,transform,frame['rgb'].shape) if detector else ([],[])
                predicted=time.perf_counter()
                # Avoid treating delayed inference output as a fresh camera observation.
                age = time.monotonic()-meta['written_monotonic']
                if age > max_age:
                    last_frame=None
                    if now-last_notice>1:
                        print('[vision] Inference output expired; reduce load or adjust max_frame_age_s',flush=True);last_notice=now
                    if not args.headless:
                        board=np.zeros((640,1280,3),np.uint8)
                        cv2.putText(board,'STALE - inference output expired',(20,100),cv2.FONT_HERSHEY_SIMPLEX,.8,(0,180,255),2)
                        cv2.imshow(window,board)
                        if (cv2.waitKey(1)&0xff) in (27,ord('q')): break
                    continue
                fps_count+=1;elapsed=predicted-fps_start
                if elapsed>=1:
                    measured_fps=fps_count/elapsed;fps_start=predicted;fps_count=0
                timings={'preprocess_ms':(prepared-started)*1000,'predict_and_masks_ms':(predicted-prepared)*1000,
                         'shm_to_result_ms':age*1000,'processed_fps':measured_fps}
                record={'schema_version':1,'capture':meta,'preprocess':transform.to_dict(),'geometry':geometry,
                        'detections':detections,'timings':timings,'preview_only':args.preview_only,
                        'noise':False,'blur':False,'scope':'single_frame_2d_detections_no_tracking_or_map_positions'}
                classes=dict(Counter(d['class_name'] for d in detections))
                status=f'FPS {measured_fps:.1f} | infer {timings["predict_and_masks_ms"]:.1f}ms | shm age {age*1000:.0f}ms | {classes}'
                if args.preview_only:status='PREVIEW ONLY - '+status
                board,annotated=render(frame['rgb'],network,masks,detections,geometry,status,preview_only=args.preview_only) if not args.headless else (None,network)
                last_frame=(frame,network,annotated,record,masks,transform);last_valid=meta['written_monotonic']
                if not args.headless:cv2.imshow(window,board)
                if now-last_notice>=1:
                    print(f'[vision] frame={meta["sequence"]} sim={meta["stamp_ns"]/1e9:.3f}s {status}',flush=True);last_notice=now
                count+=1
                if args.max_frames and count>=args.max_frames:break
            elif now-last_valid>max_age:
                last_frame=None
                if now-last_notice>=2:
                    print('[vision] WAITING/STALE: no fresh camera frame',flush=True);last_notice=now
                if not args.headless:
                    board=np.zeros((640,1280,3),np.uint8)
                    cv2.putText(board,'WAITING / STALE - no fresh camera frame',(20,100),cv2.FONT_HERSHEY_SIMPLEX,.8,(0,180,255),2)
                    cv2.imshow(window,board)
            if not args.headless:
                keycode=cv2.waitKey(1)&0xff
                if keycode in (27,ord('q')) or cv2.getWindowProperty(window,cv2.WND_PROP_VISIBLE)<1:break
                if keycode==ord('s') and last_frame is not None and time.monotonic()-last_frame[0]['metadata']['written_monotonic']<=max_age:
                    save_snapshot(save_dir,*last_frame)
            time.sleep(.002)
    except KeyboardInterrupt:
        pass
    finally:
        if not args.headless:cv2.destroyAllWindows()
