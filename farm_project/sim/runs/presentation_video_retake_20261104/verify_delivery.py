"""재촬영 배포물을 읽기 전용으로 검증한다. manifest와 촬영 이력을 수정하지 않는다.

ffmpeg/ffprobe와 NumPy가 필요하다. GUI·ROS·물리 시뮬레이션은 실행하지 않는다.
"""
from pathlib import Path
import hashlib
import json
import subprocess

import numpy as np


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def verify_clip(root, clip):
    path = root / clip['file']
    require(digest(path) == clip['sha256'], f'{path.name}: SHA256 불일치')
    require((clip['frames'], clip['fps'], clip['width'], clip['height']) ==
            (150, 30, 1920, 1080), f'{path.name}: manifest 규격 불일치')
    streams = json.loads(subprocess.check_output([
        'ffprobe', '-v', 'error', '-count_frames', '-show_entries',
        'stream=codec_type,codec_name,width,height,pix_fmt,r_frame_rate,avg_frame_rate,nb_read_frames,duration',
        '-of', 'json', str(path)], text=True))['streams']
    require(not any(s['codec_type'] == 'audio' for s in streams),
            f'{path.name}: 오디오 스트림 발견')
    videos = [s for s in streams if s['codec_type'] == 'video']
    require(len(videos) == 1, f'{path.name}: 비디오 스트림 수 불일치')
    video = videos[0]
    require((video['codec_name'], video['pix_fmt'], video['width'], video['height'],
             video['r_frame_rate'], video['avg_frame_rate'], int(video['nb_read_frames'])) ==
            ('h264', 'yuv420p', 1920, 1080, '30/1', '30/1', 150),
            f'{path.name}: 실제 영상 규격 불일치: {video}')
    require(abs(float(video['duration']) - 5) < 0.0001,
            f'{path.name}: 5초 길이 불일치')
    decoded = subprocess.run(['ffmpeg', '-v', 'error', '-i', str(path),
                              '-f', 'null', '-'], capture_output=True, text=True)
    require(decoded.returncode == 0 and not decoded.stderr,
            f'{path.name}: 전체 디코딩 실패: {decoded.stderr}')
    ledger = [json.loads(line) for line in
              (root / (path.stem + '-frames.jsonl')).read_text().splitlines()]
    require([r['frame'] for r in ledger] == list(range(150)),
            f'{path.name}: 렌더 프레임 누락/중복')
    require(all(b['render_reference_time'] > a['render_reference_time']
                for a, b in zip(ledger, ledger[1:])),
            f'{path.name}: 새 렌더 참조 시각 확인 실패')
    require(all(abs(r['time_s'] - i / 30) < 1e-9 for i, r in enumerate(ledger)),
            f'{path.name}: 프레임 시간 불일치')
    for frame in (0, 75, 149):
        preview = root / 'preview' / f'{path.stem}-{frame:04}.png'
        require(preview.is_file() and preview.stat().st_size > 0,
                f'{path.name}: 프리뷰 이미지 없음: {preview.name}')
        info = json.loads(Path(str(preview) + '.json').read_text())
        require(info['frame'] == frame and abs(info['time_s'] - frame / 30) < 1e-9,
                f'{path.name}: 프리뷰 메타데이터 프레임 불일치')
    print(f'{path.name}: 150프레임 / 5초 / 1080p30 / 무음 / 해시·디코딩·렌더 기록 PASS',
          flush=True)


def verify_originals(root):
    original = root.parent / 'presentation_video_20261104'
    recorded = root / 'original_hashes.json'
    checked = skipped = 0
    if recorded.exists():
        for name, expected in json.loads(recorded.read_text()).items():
            path = original / name
            if not path.is_file():
                skipped += 1
                continue
            require(digest(path) == expected, f'보존 원본 변경 발견: {name}')
            checked += 1
        print(f'원본 보존: {checked}개 해시 일치, 배포에 없는 파일 {skipped}개 건너뜀')
    else:
        print('원본 보존: original_hashes.json 없음; 원본 해시 검사 건너뜀')
    return original


def verify_continuity(root, original):
    a = json.loads((original / 'preview/03_grasp-0149.png.json').read_text())
    b = json.loads((root / 'preview/04_deposit-0000.png.json').read_text())
    required = ('/World/Vegetation/Bed_02/Fruits/Pepper_0003_red',
                '/World/harvest_robot/arm_2_gripper_link')
    for name in required:
        before = np.asarray(a['inspected'][name], dtype=float)
        after = np.asarray(b['inspected'][name], dtype=float)
        require(before.shape == after.shape == (4, 4), f'연속성 행렬 형식 오류: {name}')
        difference = float(np.max(np.abs(before - after)))
        require(difference == 0, f'03 마지막→04 시작 변환 불일치: {name}, {difference}')
    require(a['state']['joints'] == b['state']['joints'], '03→04 관절 상태 불일치')
    require(a['state']['attach_fruits'] == b['state']['attach_fruits'], '03→04 과실 부착 불일치')
    print('원본 03 마지막→새 04 시작: 과실·집게 월드 행렬 차이 0, 관절·부착 동일 PASS')


def main():
    root = Path(__file__).resolve().parent
    manifest = json.loads((root / 'manifest.json').read_text())
    clips = manifest['clips']
    require(len(clips) == 3 and {c['file'] for c in clips} ==
            {'02_scout.mp4', '04_deposit.mp4', '07_sorting.mp4'}, '재촬영 3종 목록 불일치')
    for clip in clips:
        verify_clip(root, clip)
    require(bool(manifest['capture_tools']), '촬영 도구 해시 목록 없음')
    for name, expected in manifest['capture_tools'].items():
        require(digest(root / name) == expected, f'촬영 도구 SHA256 불일치: {name}')
    print(f"촬영 도구 {len(manifest['capture_tools'])}개 SHA256 PASS")
    original = verify_originals(root)
    verify_continuity(root, original)
    print('검증 완료. manifest와 원본 파일은 수정하지 않았습니다.')


if __name__ == '__main__':
    main()
