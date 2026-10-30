"""저장된 실제 선별 RGB에 원본 검출기를 적용한다. ROS/팔/운영 설정은 변경하지 않는다."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path

import cv2

ROOT = Path(__file__).resolve().parents[2]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--trial', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    trial, output = args.trial.resolve(), args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    settings_path = trial / 'runtime/sorter.json'
    settings = json.loads(settings_path.read_text())
    source = ROOT / settings['source_workspace']
    detector_path = source / 'src/sorting_station/hcr/zone_preview.py'
    roi_path = source / settings['source_roi']
    image_path = trial / 'sorting/camera_rgb.png'
    report_path = trial / 'sorting/physical_report.json'
    spec = importlib.util.spec_from_file_location('hcr_detection_test', detector_path)
    vision = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(vision)
    config = json.loads(roi_path.read_text())
    image = cv2.imread(str(image_path))
    if image is None or list(image.shape[1::-1]) != config['size']:
        raise ValueError('원본 카메라 영상 크기 불일치')
    rois = config['rois']
    vision.validate_rois(rois, *config['size'])
    # 같은 실제 영상에서 위치만 바꿔 영향 분리. 8%/채도90/명도60은 운영값 그대로다.
    cases = []
    for offset in range(41):
        observations = {}
        shifted = {n: [x, y + offset, w, h] for n, (x, y, w, h) in rois.items()}
        vision.validate_rois(shifted, *config['size'])
        for name, (x, y, w, h) in shifted.items():
            state, red, yellow = vision.classify(image[y:y+h, x:x+w], .08, 90, 60)
            observations[name] = dict(state=state, red_ratio=red, yellow_ratio=yellow)
        cases.append(dict(offset_y_px=offset, rois=shifted, observations=observations))
        if offset in (0, 5, 10, 20, 40):
            overlay = image.copy()
            for name, (x, y, w, h) in shifted.items():
                cv2.rectangle(overlay, (x, y), (x+w-1, y+h-1), (255, 0, 255), 1)
                cv2.putText(overlay, name, (x, y-5), cv2.FONT_HERSHEY_SIMPLEX,
                            .4, (255, 0, 255), 1)
            cv2.imwrite(str(output / f'roi_y_plus_{offset:02d}.png'), overlay)
    physical = json.loads(report_path.read_text())
    result = dict(scope='offline original RGB detection only; no new physics or arm commands',
                  image=str(image_path), thresholds=dict(minimum=.08, saturation=90, brightness=60),
                  physical_remaining=sum(not f['sorted'] for f in physical['fruits']),
                  physical_fruits=physical['fruits'], cases=cases,
                  source_sha256={str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
                                 for p in (settings_path, detector_path, roi_path, image_path, report_path)})
    (output / 'result.json').write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n')
    for case in cases:
        if case['offset_y_px'] in (0, 5, 10, 20, 40):
            print(case['offset_y_px'], {n: v['state'] for n, v in case['observations'].items()})


if __name__ == '__main__':
    main()
