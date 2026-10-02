#!/usr/bin/env python3
"""기존 로봇의 D435/YOLO 구현을 FARM_RPC로 연결합니다. ROS·모터를 실행하지 않습니다."""
import argparse
import contextlib
import json
from pathlib import Path
import shutil
import sys
import tempfile
import uuid


def main() -> None:
    parser=argparse.ArgumentParser()
    parser.add_argument('--config', required=True)
    args=parser.parse_args()
    cfg=json.loads(Path(args.config).read_text())
    source=Path(cfg['legacy_directory']).expanduser()
    sys.path.insert(0,str(source))
    with contextlib.redirect_stdout(sys.stderr):
        import detect_capture as detector
        from scout_realsense_camera import ConfiguredCamera
        detector.torch.set_num_threads(2)
        model_path=source/cfg['model']
        model=detector.YOLO(str(model_path),task='segment')
        camera=ConfiguredCamera(cfg["camera"])
        camera.start()
    session=uuid.uuid4().hex
    cached=None
    def emit(value: dict) -> None:
        print('FARM_RPC '+json.dumps(value,allow_nan=False),flush=True)
    emit({'ready':True})
    try:
        with tempfile.TemporaryDirectory(prefix='farm_real_capture_') as tmp:
            for line in sys.stdin:
                req=json.loads(line)
                if req['op']=='stop':break
                try:
                    if req.get('session') and req['session']!=session:
                        raise ValueError('Camera session changed')
                    if req['op'] in ('info','capture'):
                        folder=Path(tmp)/str(req['id'])
                        with contextlib.redirect_stdout(sys.stderr):
                            info,timing=camera.capture(folder,1)
                            report=detector.detect_capture(folder,model_path,cached_model=model) if req['op']=='capture' else None
                        intr=info['intrinsics']
                        result={'metadata':{'session':session,'pose_frame':cfg['camera_frame'],
                            'K':[[intr['fx'],0,intr['ppx']],[0,intr['fy'],intr['ppy']],[0,0,1]],
                            'T_odom_camera_optical':[[1,0,0,0],[0,1,0,0],[0,0,1,0],[0,0,0,1]],
                            'timing_policy':'stationary_interval_reference_not_exposure'},
                            'width':info['rgb_size'][0],'height':info['rgb_size'][1],
                            'camera_settings':{key:info[key] for key in ('white_balance','auto_white_balance','auto_exposure','warmup_frames','requested_fps')}}
                        if report is not None:
                            accepted=[];rejected=[]
                            for obj in report['objects']:
                                if obj.get('xyz_m') is None or obj['confidence']<cfg['confidence']:
                                    rejected.append(obj);continue
                                accepted.append({'position_odom_m':obj['xyz_m'],'class_name':obj['class'],
                                    'confidence':obj['confidence'],'mask_box_original_xyxy':obj['bbox_xyxy']})
                            if report['objects'] and not accepted:
                                raise RuntimeError('검출된 과실 중 유효한 깊이·신뢰도 표본이 없습니다.')
                            result.update(detections=accepted,rejected=rejected,timings=timing)
                            cached=(folder,req['id'])
                    elif req['op']=='annotate':
                        if cached is None:raise ValueError('No capture')
                        import cv2
                        folder,_=cached
                        dest=Path(req['directory']);dest.mkdir(parents=True,exist_ok=True)
                        for file in folder.iterdir():
                            if file.is_file():shutil.copy2(file,dest/file.name)
                        if (folder/'detection').exists():shutil.copytree(folder/'detection',dest/'detection',dirs_exist_ok=True)
                        image=cv2.imread(str(folder/'rgb.png'))
                        for label in req['labels']:
                            box=label['box'];cv2.putText(image,label['id'],(int(box[0]),int(box[1])),cv2.FONT_HERSHEY_SIMPLEX,.5,(0,255,0),1)
                        if not cv2.imwrite(str(dest/'registered.jpg'),image):raise RuntimeError('Image write failed')
                        (dest/'windows.json').write_text(json.dumps(req,ensure_ascii=False,indent=2))
                        result={'saved':str(dest)}
                    else:raise ValueError('Unknown operation')
                    emit({'id':req['id'],'ok':True,'result':result})
                except Exception as error:
                    emit({'id':req['id'],'ok':False,'error':str(error)})
    finally:camera.close()


if __name__=='__main__':main()
