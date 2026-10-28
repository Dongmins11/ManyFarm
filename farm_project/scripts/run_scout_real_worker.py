#!/usr/bin/env python3
"""기존 로봇의 D435/YOLO 구현을 FARM_RPC로 연결합니다. ROS·모터를 실행하지 않습니다."""
import argparse
from collections.abc import Iterator
import contextlib
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import time
import uuid


@contextlib.contextmanager
def timed_stage(timings: dict, stage: str) -> Iterator[None]:
    """단조 시계의 초 단위를 기록하고 진단은 RPC와 분리된 stderr에 출력합니다."""
    begin = time.monotonic()
    print('VISION_TIMING '+json.dumps({'stage': stage, 'event': 'begin'}), file=sys.stderr, flush=True)
    status = 'ok'
    try:
        yield
    except BaseException:
        status = 'error'
        raise
    finally:
        timings[stage] = time.monotonic()-begin
        print('VISION_TIMING '+json.dumps({'stage': stage, 'event': 'end',
              'status': status, 'elapsed_s': timings[stage]}), file=sys.stderr, flush=True)


def resolve_model_path(cfg: dict, project_root: Path) -> Path:
    """선택한 로컬 모델을 import 전에 확인한다. 경로 누락 시 다운로드로 대체하지 않는다."""
    base = cfg.get('model_base', 'legacy')
    if base not in ('legacy', 'project'):
        raise ValueError('Unknown model_base: '+str(base))
    root = project_root if base == 'project' else Path(cfg['legacy_directory']).expanduser()
    path = (root / Path(cfg['model']).expanduser()).resolve()
    if not path.is_file():
        raise FileNotFoundError(f'Local model missing: {path}')
    return path


def main() -> None:
    parser=argparse.ArgumentParser()
    parser.add_argument('--config', required=True)
    args=parser.parse_args()
    cfg=json.loads(Path(args.config).read_text())
    model_path = resolve_model_path(cfg, Path(__file__).resolve().parents[1])
    source=Path(cfg['legacy_directory']).expanduser()
    sys.path.insert(0,str(source))
    # 로컬 가중치만 사용하므로 import 중 외부 DNS 확인을 생략합니다.
    os.environ['YOLO_OFFLINE'] = 'true'
    startup_timing = {}
    with timed_stage(startup_timing, 'startup_total_s'), contextlib.redirect_stdout(sys.stderr):
        with timed_stage(startup_timing, 'imports_s'):
            import detect_capture as detector
            from scout_realsense_camera import ConfiguredCamera
        detector.torch.set_num_threads(2)
        with timed_stage(startup_timing, 'model_load_s'):
            model=detector.YOLO(str(model_path),task='segment')
            inference = cfg.get('inference', {})
            # Legacy predict explicitly sets conf=0.25 and imgsz=640; keep CPU/RGB-D handling.
            if inference:
                model.overrides.update({key: inference[source] for key, source in
                (('iou', 'iou'), ('max_det', 'max_detections'), ('half', 'half'))
                if source in inference})
        camera=ConfiguredCamera(cfg["camera"])
        with timed_stage(startup_timing, 'camera_start_s'):
            startup_timing['camera'] = camera.start()
    # 선택적 읽기 전용 뷰어: 실패해도 예찰 워커는 계속 동작합니다.
    viewer = None
    try:
        from scout_mjpeg import Viewer
        viewer = Viewer(camera)
    except Exception as error:
        print(f'MJPEG viewer unavailable: {error}', file=sys.stderr, flush=True)
    session=uuid.uuid4().hex
    cached=None
    def emit(value: dict) -> None:
        print('FARM_RPC '+json.dumps(value,allow_nan=False),flush=True)
    emit({'ready':True,'timings':startup_timing})
    try:
        with tempfile.TemporaryDirectory(prefix='farm_real_capture_') as tmp:
            for line in sys.stdin:
                req=json.loads(line)
                if req['op']=='stop':break
                request_begin = time.monotonic()
                request_timing = {}
                try:
                    if req.get('session') and req['session']!=session:
                        raise ValueError('Camera session changed')
                    if req['op'] in ('info','capture'):
                        folder=Path(tmp)/str(req['id'])
                        with contextlib.redirect_stdout(sys.stderr):
                            with timed_stage(request_timing, 'camera_capture_s'):
                                info,timing=camera.capture(folder,1)
                            report = None
                            if req['op']=='capture':
                                with timed_stage(request_timing, 'detector_total_s'):
                                    report=detector.detect_capture(folder,model_path,cached_model=model)
                                request_timing['detector'] = {key: report[key] for key in
                                    ('load_s', 'predict_s', 'postprocess_and_image_save_s', 'model_reused') if key in report}
                        request_timing['camera'] = timing
                        (folder/'startup_timing.json').write_text(json.dumps(startup_timing, indent=2))
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
                            # 후보의 측정 실패는 카메라/RPC 실패와 구분합니다.
                            # 빈 검출 목록으로 기존 FSM을 이어가되 유효 좌표를 만들어내지 않습니다.
                            measurement_status = ('VALID' if accepted else
                                                  'NO_VALID_MEASUREMENTS' if rejected else 'NO_DETECTIONS')
                            measurement = {
                                'status': measurement_status,
                                'candidate_count': len(report['objects']),
                                'valid_count': len(accepted),
                                'rejected': rejected,
                            }
                            # annotate에서 관측 폴더로 복사되어, 과실 없음과 측정 불가를 구분합니다.
                            (folder / 'measurement_status.json').write_text(
                                json.dumps(measurement, ensure_ascii=False, allow_nan=False), encoding='utf-8')
                            if measurement_status == 'NO_VALID_MEASUREMENTS':
                                print('관측 경고: 유효한 깊이·신뢰도 표본 없음; '
                                      '측정 불가를 기록하고 다음 지점으로 진행합니다.',
                                      file=sys.stderr, flush=True)
                            result.update(detections=accepted,rejected=rejected,timings=timing,
                                          measurement_status=measurement_status)
                            cached=(folder,req['id'])
                    elif req['op']=='annotate':
                        if cached is None:raise ValueError('No capture')
                        import cv2
                        folder,_=cached
                        dest=Path(req['directory']);dest.mkdir(parents=True,exist_ok=True)
                        copy_begin = time.monotonic()
                        for file in folder.iterdir():
                            if file.is_file():shutil.copy2(file,dest/file.name)
                        if (folder/'detection').exists():shutil.copytree(folder/'detection',dest/'detection',dirs_exist_ok=True)
                        request_timing['artifact_copy_s'] = time.monotonic()-copy_begin
                        image=cv2.imread(str(folder/'rgb.png'))
                        for label in req['labels']:
                            box=label['box'];cv2.putText(image,label['id'],(int(box[0]),int(box[1])),cv2.FONT_HERSHEY_SIMPLEX,.5,(0,255,0),1)
                        if not cv2.imwrite(str(dest/'registered.jpg'),image):raise RuntimeError('Image write failed')
                        (dest/'windows.json').write_text(json.dumps(req,ensure_ascii=False,indent=2))
                        result={'saved':str(dest)}
                    else:raise ValueError('Unknown operation')
                    # 합계는 RPC 직렬화/전송 전까지이며 하위 단계 시간과 더하지 않습니다.
                    request_timing['request_processing_s'] = time.monotonic()-request_begin
                    result['performance'] = request_timing
                    timing_path = (dest/'annotation_timing.json' if req['op']=='annotate'
                                   else folder/'capture_timing.json')
                    timing_path.write_text(json.dumps(request_timing, indent=2))
                    print('VISION_TIMING '+json.dumps({'op': req['op'], 'id': req['id'],
                          'timings': request_timing}), file=sys.stderr, flush=True)
                    emit({'id':req['id'],'ok':True,'result':result})
                except Exception as error:
                    emit({'id':req['id'],'ok':False,'error':str(error)})
    finally:
        if viewer is not None:
            viewer.close()
        camera.close()


if __name__=='__main__':main()
