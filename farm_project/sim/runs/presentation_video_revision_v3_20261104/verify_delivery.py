"""Read-only V3 package validation. No manifest, GUI or source file is modified.

ffmpeg/ffprobe and NumPy are required. Visual quality remains a separate human/QA
inspection; the checks here validate the saved evidence and media specifications.
"""
from pathlib import Path
import hashlib
import json
import subprocess

import numpy as np

RAW_FRAMES = {'01_overview.mp4': 150, '02_scout.mp4': 150, '04_deposit.mp4': 150,
              '05_handoff.mp4': 150, '06_transport.mp4': 120, '07_sorting.mp4': 210}
EDIT_FILES = {'ManyFarm_22s_clean.mp4', 'ManyFarm_22s_captioned.mp4'}
HOUSE = '/World/farm_framechanged'


def require(condition, message):
    if not condition:
        raise ValueError(message)


def read(path):
    return json.loads(path.read_text())


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_video(root, record, frames):
    path = root / record['file']
    require(digest(path) == record['sha256'], f'{path.name}: SHA256 mismatch')
    require((record['frames'], record['fps'], record['width'], record['height']) ==
            (frames, 30, 1920, 1080), f'{path.name}: manifest specification mismatch')
    streams = json.loads(subprocess.check_output([
        'ffprobe', '-v', 'error', '-count_frames', '-show_entries',
        'stream=codec_type,codec_name,width,height,pix_fmt,r_frame_rate,avg_frame_rate,nb_read_frames,duration',
        '-of', 'json', str(path)], text=True))['streams']
    require(not any(s['codec_type'] == 'audio' for s in streams), f'{path.name}: audio present')
    videos = [s for s in streams if s['codec_type'] == 'video']
    require(len(videos) == 1, f'{path.name}: expected one video stream')
    video = videos[0]
    require((video['codec_name'], video['pix_fmt'], video['width'], video['height'],
             video['r_frame_rate'], video['avg_frame_rate'], int(video['nb_read_frames'])) ==
            ('h264', 'yuv420p', 1920, 1080, '30/1', '30/1', frames),
            f'{path.name}: actual media specification mismatch: {video}')
    require(abs(float(video['duration']) - frames / 30) < .0001,
            f'{path.name}: duration mismatch')
    decoded = subprocess.run(['ffmpeg', '-v', 'error', '-i', str(path), '-f', 'null', '-'],
                             capture_output=True, text=True)
    require(decoded.returncode == 0 and not decoded.stderr,
            f'{path.name}: full decode failed: {decoded.stderr}')
    print(f'{path.name}: SHA / {frames} frames / {frames/30:g}s / 1080p30 / silent / full decode PASS', flush=True)


def house_hide_paths(value):
    found = []
    if isinstance(value, dict):
        for key, item in value.items():
            if key == 'hide':
                found.extend(path for path in item
                             if path in ('/', '/World', HOUSE) or path.startswith(HOUSE + '/'))
            found.extend(house_hide_paths(item))
    elif isinstance(value, list):
        for item in value:
            found.extend(house_hide_paths(item))
    return found


def verify_capture(root, filename, count):
    stem = Path(filename).stem
    ledger = [json.loads(line) for line in (root / f'{stem}-frames.jsonl').read_text().splitlines()]
    require([row['frame'] for row in ledger] == list(range(count)), f'{stem}: missing/duplicate render frame')
    require(all(b['render_reference_time'] > a['render_reference_time']
                for a, b in zip(ledger, ledger[1:])), f'{stem}: stale render reference time')
    require(all(abs(row['time_s'] - index / 30) < 1e-9 for index, row in enumerate(ledger)),
            f'{stem}: ledger frame time mismatch')
    metadata = read(root / f'{stem}.json')
    require(metadata['frames'] == metadata['expected_frames'] == count and not metadata['preview_only'],
            f'{stem}: full raw capture did not finish')
    require(not house_hide_paths(metadata), f'{stem}: capture metadata hides greenhouse')
    config = read(root / 'settings' / f'{stem}.json')
    require(config['fps'] == 30 and round(config['duration_s'] * 30) == count,
            f'{stem}: settings duration mismatch')
    require(not house_hide_paths(config), f'{stem}: settings hide greenhouse')
    for frame in (0, count // 2, count - 1):
        image = root / 'preview' / f'{stem}-{frame:04}.png'
        require(image.is_file() and image.stat().st_size > 0, f'{stem}: preview missing: {frame}')
        info = read(Path(str(image) + '.json'))
        require(info['frame'] == frame and abs(info['time_s'] - frame / 30) < 1e-9,
                f'{stem}: preview metadata does not match frame')
        require(not house_hide_paths(info['state']), f'{stem}: preview state hides greenhouse')
    print(f'{stem}: complete render ledger, three previews and no greenhouse hide PASS', flush=True)


def verify_originals(root):
    project = root.parents[2]
    originals = read(root / 'original_hashes.json')
    checked = skipped = 0
    for name, expected in originals.items():
        path = project / name
        if not path.is_file():
            skipped += 1
            continue
        require(digest(path) == expected, f'Preserved original changed: {name}')
        checked += 1
    print(f'Preserved originals: {checked} unchanged; {skipped} not distributed here, skipped', flush=True)
    return originals


def verify_environment(root):
    tags = read(root / 'apriltag_installation.json')
    require(tags['expected'] == tags['pattern_count'] == len(set(tags['verified_paths'])) == 240,
            'Expected all 240 tag roots and rendered Patterns')
    review = read(root / 'qa/apriltag_review.json')
    require(review['passed'] and (root / review['image']).is_file(), 'Tag closeup review missing')
    baseline = read(root / 'house_visibility_baseline.json')
    require(HOUSE in baseline and len(baseline) > 1, 'House baseline missing')
    require(all(value['active'] and value['visibility'] == 'inherited'
                for value in baseline.values()), 'House baseline not fully visible/active')
    print(f'240 AprilTags/Patterns, closeup QA and {len(baseline)} visible house baseline prims PASS', flush=True)
    print('House evidence scope: saved settings/states and baseline; runtime inspect_request raises on any baseline change.', flush=True)


def matrix_equal(a, b, label, tolerance=0):
    before, after = np.asarray(a, dtype=float), np.asarray(b, dtype=float)
    require(before.shape == after.shape == (4, 4), f'{label}: invalid matrix shape')
    difference = float(np.max(np.abs(before - after)))
    require(difference <= tolerance, f'{label}: max matrix difference {difference}')
    return difference


def verify_continuity(root):
    original = root.parent / 'presentation_video_20261104'
    before = read(original / 'preview/03_grasp-0149.png.json')
    after = read(root / 'preview/04_deposit-0000.png.json')
    for path in ('/World/Vegetation/Bed_02/Fruits/Pepper_0003_red',
                 '/World/harvest_robot/arm_2_gripper_link'):
        matrix_equal(before['inspected'][path], after['inspected'][path], '03→04 ' + path)
    for joint, value in before['state']['joints'].items():
        require(after['state']['joints'][joint] == value, f'03→04 joint changed: {joint}')
    require(before['state']['attach_fruits'] == after['state']['attach_fruits'], '03→04 fruit attachment mismatch')
    before = read(root / 'preview/05_handoff-0149.png.json')
    after = read(root / 'preview/06_transport-0000.png.json')
    paths = {f'/World/PresentationFruits/Handoff_{number:02d}' for number in range(1, 8)}
    basket = '/World/transport_robot/cargo_box'
    before_basket = np.asarray(before['inspected'][basket], dtype=float)
    after_basket = np.asarray(after['inspected'][basket], dtype=float)
    # The travel shot deliberately starts at another position/orientation.
    # Cargo continuity is relative to the basket, not to the greenhouse world.
    before_inverse, after_inverse = np.linalg.inv(before_basket), np.linalg.inv(after_basket)
    relative_errors = []
    for path in paths:
        relative_before = before_inverse @ np.asarray(before['inspected'][path], dtype=float)
        relative_after = after_inverse @ np.asarray(after['inspected'][path], dtype=float)
        relative_errors.append(matrix_equal(relative_before, relative_after,
                                            '05→06 basket-relative ' + path, 1e-8))
    attached = {item['fruit'] for item in after['state']['attach_fruits']}
    require(paths == attached, '06 does not carry exactly the seven handoff fruit IDs')
    assets = read(root / 'handoff_assets.json')
    require(set(assets['clone_paths']) == paths, 'Handoff clone IDs differ from the installed assets')
    sources = assets['diagnostics']['fruit_sources']
    require(len(sources) == len(set(sources)) == 7 and
            all(path.endswith(('_red', '_yellow')) for path in sources),
            'Handoff colour/size provenance is not seven original red/yellow assets')
    placements = read(root / 'settings/station_transform.json')['placements']
    for stem in ('06_transport', '07_sorting'):
        state = read(root / 'settings' / f'{stem}.json')['base']
        for path, placement in placements.items():
            matrix_equal(state['placements'][path]['matrix'], placement['matrix'], stem + ' station transform')
    print('03→04 fruit/gripper exact world continuity PASS', flush=True)
    print(f'05→06 seven same fruit IDs/source colours/scales and basket-relative poses PASS '
          f'(max difference {max(relative_errors):.3g}; travel scene world pose may change)', flush=True)
    print('06/07 station and arm use the same filming transform PASS', flush=True)


def verify_inset(root):
    config = read(root / 'overlays/02_scout_insert.json')
    x, y, width, height = config['rect_px']
    require(480 <= width <= 560 and width / height == 640 / 384, 'Inset image aspect/width mismatch')
    require(x >= 0 and y >= 0 and x + width <= 1920 and y + height <= 1080, 'Inset outside frame')
    require(config['placement_status'] == 'verified on final V3 start, middle and end', 'Inset placement not reviewed')
    require(config['title'] == '예찰 이미지 예시' and config['description'] == '작물 검출 → 수확 태스크 생성',
            'Inset title/description mismatch')
    provenance = read(root / config['source_metadata'])
    for name, expected in provenance['source_files'].items():
        require(digest(root / 'assets' / name) == expected, f'Actual observation source changed: {name}')
    recorded = read(root / 'assets/02_scout_map_detections.json')['accepted']
    require(len(provenance['detections']) == len(recorded) == 4, 'Inset detection count mismatch')
    for shown, actual in zip(provenance['detections'], recorded):
        require(all(actual[key] == value for key, value in shown.items()), 'Inset fabricated/changed detection')
    for frame in (0, 75, 149):
        require((root / 'qa' / f'02_scout-inset-placement-{frame:04}.png').is_file(), 'Inset composite QA missing')
    print('Actual RGB/metadata hashes, four recorded boxes and three inset placement reviews PASS', flush=True)


def verify_edit(root):
    decisions = read(root / 'edit_decisions.json')
    require((decisions['fps'], decisions['frames'], decisions['duration_s']) == (30, 660, 22), 'Edit timeline mismatch')
    require(decisions['core_boundaries_frames'] == [0, 90, 180, 270, 360, 450, 510, 660], 'Edit cut boundaries mismatch')
    require(decisions['transitions'] == {'dissolve_duration_frames': 6, 'centres_frames': [90, 180, 360, 450, 510],
                                       'direct_cut_03_to_04_frame': 270}, 'Edit transitions mismatch')
    require(decisions['ending'] == {'stable_hold_start_frame': 600, 'fade_start_frame': 636, 'fade_duration_frames': 24},
            'Ending hold/fade mismatch')
    require(decisions['raw_sources_unchanged'], 'Raw preservation not confirmed')
    for name, expected in decisions['outputs'].items():
        require(digest(root / name) == expected, f'Edit decisions stale output hash: {name}')
    captions = (root / 'captions.ass').read_text()
    require('바구니를 열어 수확물을 전달' in captions and '과실을 해당 분류함으로 이동' in captions,
            'Updated 05/07 captions missing')
    for name in EDIT_FILES:
        last = subprocess.check_output(['ffmpeg', '-v', 'error', '-i', str(root / name),
                                        '-vf', 'select=eq(n\\,659)', '-vsync', '0', '-frames:v', '1',
                                        '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'])
        pixels = np.frombuffer(last, dtype=np.uint8)
        require(pixels.size == 1920 * 1080 * 3 and pixels.max() <= 2, f'{name}: last frame is not black')
    print('22-second edit decisions, 03→04 direct cut, updated captions and final black frame PASS', flush=True)


def verify_phase_qa(root):
    expected = {'05_handoff': [30, 41, 45, 54, 63, 75, 102, 120, 149],
                '07_sorting': [30, 78, 84, 90, 99, 111, 120, 174, 207]}
    for stem, indices in expected.items():
        evidence = read(root / 'qa' / f'{stem}-mp4-keyphases.json')
        require(evidence['source_sha256'] == digest(root / f'{stem}.mp4'), f'{stem}: stale phase QA source')
        require([row['frame'] for row in evidence['frames']] == indices, f'{stem}: phase QA frames missing')
        require((root / evidence['contact_sheet']).is_file(), f'{stem}: phase sheet missing')
        for row in evidence['frames']:
            require(abs(row['actual_time_s'] - row['frame'] / 30) < 1e-9, f'{stem}: phase time mismatch')
            require(digest(root / row['file']) == row['sha256'], f'{stem}: phase image hash mismatch')
        review = read(root / 'qa' / f'{stem}-mp4-review.json')
        require(review['passed'] and review['source_sha256'] == evidence['source_sha256'],
                f'{stem}: current MP4 visual review missing')
    print('05/07 actual MP4 key-phase extracts, source hashes and visual review records PASS', flush=True)


def main():
    root = Path(__file__).resolve().parent
    manifest = read(root / 'manifest.json')
    require({record['file'] for record in manifest['clips']} == set(RAW_FRAMES) and len(manifest['clips']) == 6,
            'Expected exactly six newly captured raw clips')
    for record in manifest['clips']:
        verify_video(root, record, RAW_FRAMES[record['file']])
        verify_capture(root, record['file'], RAW_FRAMES[record['file']])
    require({record['file'] for record in manifest['edits']} == EDIT_FILES and len(manifest['edits']) == 2,
            'Expected exactly two 22-second edits')
    for record in manifest['edits']:
        verify_video(root, record, 660)
    originals = verify_originals(root)
    reused = manifest['reused_clips']
    require(len(reused) == 1 and Path(reused[0]['file']).name == '03_grasp.mp4', 'Expected original 03 reuse')
    original_key = 'sim/runs/presentation_video_20261104/03_grasp.mp4'
    require(reused[0]['sha256'] == originals[original_key], '03 reused hash differs from preserved original')
    verify_video(root, reused[0], 150)
    require(bool(manifest['capture_tools']), 'Missing capture tool/setting hashes')
    for name, expected in manifest['capture_tools'].items():
        require(digest(root / name) == expected, f'Bundled tool/setting hash mismatch: {name}')
    verify_environment(root)
    verify_continuity(root)
    verify_inset(root)
    verify_phase_qa(root)
    verify_edit(root)
    print('V3 validation PASS. Manifest, raw clips and source files were not modified.', flush=True)


if __name__ == '__main__':
    main()
