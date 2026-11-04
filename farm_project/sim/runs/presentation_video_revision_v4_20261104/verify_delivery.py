"""Read-only V4 package validation. No manifest, GUI or source file is modified.

ffmpeg/ffprobe and NumPy are required. Visual quality remains a separate human/QA
inspection; the checks here validate the saved evidence and media specifications.
"""
from pathlib import Path
import argparse
import ast
import hashlib
import json
import subprocess

import numpy as np

RAW_FRAMES = {'05_handoff_continuity.mp4': 150, '06_07_transport_sorting.mp4': 360}
EDIT_FILES = {'ManyFarm_25s_clean.mp4', 'ManyFarm_25s_captioned.mp4'}
V3 = '../presentation_video_revision_v3_20261104/'
REUSED_FILES = {V3 + name for name in ('01_overview.mp4', '02_scout.mp4', '04_deposit.mp4')}
REUSED_FILES.add('../presentation_video_20261104/03_grasp.mp4')
LID_JOINTS = ('top_lid_left_joint', 'top_lid_right_joint', 'lid_pinion_joint')
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
    for key in ('base', 'keyframes', 'easing'):
        require(metadata.get(key) == config.get(key), f'{stem}: final settings differ from actual capture metadata: {key}')
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
    project = root.parents[3]
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


def verify_capture_session(root: Path) -> None:
    """촬영 중 관측한 GUI 실행 인자와 보존한 실제 촬영 도구를 대조한다."""
    session = read(root / 'capture_session.json')
    process = session['process_observed_during_capture']
    argv = process['argv']
    require(isinstance(process['pid'], int) and process['pid'] > 0 and
            isinstance(argv, list) and all(isinstance(arg, str) for arg in argv),
            'Missing observed capture process/PID/argv')
    require('--gui' in argv and '--all-beds' in argv and
            not any(arg == '--headless' or arg.startswith('--headless=') for arg in argv),
            'Observed capture process was not GUI/all-beds mode')
    require(session['gui_argument_present'] is True and
            session['all_beds_argument_present'] is True and
            session['headless_argument_present'] is False,
            'Capture-session flags disagree with observed argv')
    require(any(Path(arg).name == 'stage_portfolio_photos.py' for arg in argv),
            'Observed capture process does not identify the capture tool')
    require(session['capture_tool_sha256'] == digest(root / 'capture_tools/stage_portfolio_photos.py'),
            'Observed capture tool differs from preserved capture-time snapshot')
    print('Observed GUI/all-beds argv and capture-time tool SHA verified; session record only.', flush=True)


def matrix_equal(a, b, label, tolerance=0):
    before, after = np.asarray(a, dtype=float), np.asarray(b, dtype=float)
    require(before.shape == after.shape == (4, 4), f'{label}: invalid matrix shape')
    difference = float(np.max(np.abs(before - after)))
    require(difference <= tolerance, f'{label}: max matrix difference {difference}')
    return difference


def verify_motion(root: Path) -> set:
    """베이크된 근거의 기구 순서·6개 보존·혼합 배치·집기·엔딩을 검사한다."""
    evidence = read(root / 'settings/06_07_motion_evidence.json')
    fruits = evidence['fruits']
    ids = {item['id'] for item in fruits}
    require(len(fruits) == len(ids) == 6, 'Expected exactly six unique fruit IDs')
    colours = {item['id']: item['color'].lower() for item in fruits}
    require(list(colours.values()).count('red') == list(colours.values()).count('yellow') == 3,
            'Expected red3/yellow3')
    require(len({item['source'] for item in fruits}) == 6, 'Fruit source IDs must remain distinct')
    groups = evidence['groups']
    require(len(groups) == 2 and all(len(group) == len(set(group)) == 3 for group in groups.values()),
            'Expected two groups with three fruit IDs each')
    require(set().union(*(set(group) for group in groups.values())) == ids, 'Group ID mismatch')
    require(all({colours[x] for x in group} == {'red', 'yellow'} for group in groups.values()),
            'Each group must contain mixed colours')
    mechanism = evidence['mechanism']
    timing = [mechanism[key] for key in ('gate_open_start_s', 'gate_open_end_s', 'tilt_start_s',
                                       'tilt_max_s', 'tilt_restore_end_s', 'gate_close_end_s')]
    require(timing == sorted(timing) and timing[-1] - timing[0] <= 4.0 + 1e-9,
            'Gate→tilt→restore→close must complete within four seconds')
    frames = evidence['frames']
    require(len(frames) in (360, 361) and [f['frame'] for f in frames] == list(range(len(frames))),
            'Expected a complete 30Hz 12-second motion ledger')
    require(all(abs(f['time_s'] - i / 30) < 1e-9 for i, f in enumerate(frames)),
            'Motion ledger times differ from 30Hz')
    request = read(root / 'settings/06_07_transport_sorting.json')
    require(len(request['keyframes']) == len(frames), 'Motion evidence/keyframe count mismatch')
    for saved, row in zip(request['keyframes'], frames):
        require(abs(saved['time'] - row['time_s']) < 1e-9, 'Motion evidence/keyframe time mismatch')
        for name in ids:
            matrix_equal(saved['state']['placements'][name]['matrix'],
                         row['fruit_states'][name]['world_matrix'], 'Motion evidence pose ' + name, 1e-8)
        for name, value in row['mechanism'].items():
            require(abs(saved['state']['joints'][name] - value) < 1e-9, 'Motion evidence joint mismatch: ' + name)
    for row in frames:
        require(set(row['fruit_states']) == ids, f"Frame {row['frame']}: fruit ID loss/creation")
        require(all(abs(row['mechanism'][joint]) <= 1e-9 for joint in LID_JOINTS),
                f"Frame {row['frame']}: top lid opened")
        for fruit in row['fruit_states'].values():
            require(fruit['location'] in ('cargo', 'lane', 'gripper', 'bin'), 'Invalid fruit location')
            matrix = np.asarray(fruit['world_matrix'], dtype=float)
            require(matrix.shape == (4, 4) and np.isfinite(matrix).all(), 'Invalid fruit transform')
    require(all(f['location'] == 'cargo' for f in frames[0]['fruit_states'].values()),
            'All six must start in cargo; gripper must start empty')
    require(any(all(f['location'] == 'lane' for f in row['fruit_states'].values()) for row in frames),
            'No frame shows all six delivered to the mixed input groups')
    picks = evidence['picks']
    require(len(picks) >= 2 and {p['color'].lower() for p in picks} == {'red', 'yellow'},
            'Both red and yellow pickup/release events required')
    require(len({p['id'] for p in picks}) == len(picks), 'Repeated pickup ID')
    for pick in picks:
        require(pick['id'] in ids and colours[pick['id']] == pick['color'].lower(), 'Pickup ID/colour mismatch')
        require(1 <= pick['attach_time_s'] < pick['release_time_s'] <= 9,
                'Pickup and release must occur in the eight-second action interval')
        require(any(row['fruit_states'][pick['id']]['location'] == 'gripper' for row in frames
                    if pick['attach_time_s'] <= row['time_s'] < pick['release_time_s']),
                'No held interval for declared pickup')
        require(frames[270]['fruit_states'][pick['id']]['location'] == 'bin',
                'Picked fruit not in bin by start of ending hold')
    for row in frames[270:330]:
        for fruit_id in ids:
            matrix_equal(frames[270]['fruit_states'][fruit_id]['world_matrix'],
                         row['fruit_states'][fruit_id]['world_matrix'], 'Ending hold ' + fruit_id, 1e-8)
    audit = read(root / 'settings/06_07_convex_fruit_audit.json')
    require(audit == evidence['qa']['fruit_geometry_audit'], 'Separate convex audit differs from baked evidence')
    require(audit['rendered_frames'] == 360 and not audit['positive_overlaps'],
            'Fruit convex overlap audit missing or positive')
    require(audit['min_lane_side_clearance_m'] > 0 and audit['min_intake_support_gap_m'] >= -1e-6,
            'Fruit lane boundary/support check failed')
    require(audit['hold_max_matrix_delta'] <= 1e-8, 'Convex audit ending hold changed')
    require(evidence['geometry']['upper_lid_max_excess_m'] <= 1e-8 and not evidence['qa']['lid_excess_events'],
            'Upper-lid clearance audit failed')
    require(max(item['residual'] for item in evidence['qa']['ik_residuals']) < 1e-5,
            'Arm target IK residual exceeds geometric threshold')
    print('Motion-record checks complete: six IDs/red3 yellow3, mixed3+3, lid closure, timing, picks and hold. Independent equipment-contact audit is still required.')
    return ids


def verify_independent_geometry(root: Path) -> None:
    """현재 설정에 대한 별도 기구 감사를 요구한다. 과실쌍 검사로 대체하지 않는다."""
    audit = read(root / 'qa/06_07_independent_geometry_audit.json')
    require(audit['request_sha256'] == digest(root / 'settings/06_07_transport_sorting.json'),
            'Independent geometry audit belongs to an older capture request')
    require(audit['request_unchanged_at_check_end'] is True and audit['frames_checked'] == 361,
            'Independent geometry audit incomplete or input changed during audit')
    require(not audit['joint_limit_events'], 'Independent audit reports joint-limit violations')
    # 전체 접촉 판정 schema가 없는 구버전 감사는 최종 완료 근거로 사용할 수 없다.
    require('blocking_events' in audit and 'contact_policy' in audit,
            'Independent contact classification pending; fruit-pair checks alone are insufficient')
    require(not audit['blocking_events'], 'Independent geometry audit still contains blocking contacts')
    require(not audit['blocking_arm_station_events'], 'Independent audit still contains arm/station contacts')
    policy = {'actual_vertex_tolerance_m': .00005, 'allowed_grip_pad_penetration_m': .00205,
              'pre_attach_contact_window_s': .1, 'arm_station_radius_tolerance_m': .00001}
    require(audit['contact_policy'] == policy, 'Independent contact acceptance policy changed')
    motion = read(root / 'settings/06_07_motion_evidence.json')
    require(audit['evidence_sha256'] == digest(root / 'settings/06_07_motion_evidence.json'),
            'Independent audit belongs to older motion evidence')
    require(audit['all_sources_unchanged_at_check_end'] is True, 'Audit inputs changed during computation')
    sources = audit['source_hashes']
    require({'settings/06_07_transport_sorting.json', 'settings/06_07_motion_evidence.json',
             'settings/06_07_source_joint_geometry.json', 'qa/06_07_actual_robot_cubes.json'} <= set(sources),
            'Independent audit input hashes incomplete')
    for path, expected in sources.items():
        require(digest(root / path) == expected, 'Independent audit source changed: ' + path)
    cubes = read(root / 'qa/06_07_actual_robot_cubes.json')
    for role, geometry in cubes.items():
        require(digest(root.parents[2] / geometry['source']) == geometry['source_sha256'],
                'Independent Cube measurements use an older USD: ' + role)
    picks = {pick['id']: pick for pick in motion['picks']}

    def allowed_pad(row: dict) -> bool:
        pick = picks.get(row['fruit'])
        return bool(pick and ('/left_pad/' in row['obstacle'] or '/right_pad/' in row['obstacle'])
                    and pick['attach_time_s'] - .1 <= row['time_s'] < pick['release_time_s']
                    and row['actual_vertex_max_penetration_m'] <= .00205)

    for row in audit['allowed_grip_pad_contacts']:
        require(allowed_pad(row), 'Unexpected finger/released/unselected contact classified as normal pad contact')
        frame = motion['frames'][row['frame']]
        require(abs(frame['time_s'] - row['time_s']) < 1e-9 and
                frame['fruit_states'][row['fruit']]['phase'] == row['phase'], 'Allowed contact phase mismatch')
    for row in audit['conservative_hull_only_events']:
        require(row['actual_vertex_max_penetration_m'] <= .00005, 'Actual penetration labelled hull-only warning')
    for row in audit['excluded_nonphysical_tcp_marker_contacts']:
        require('/tcp/visuals/' in row['obstacle'], 'Physical geometry incorrectly excluded as TCP visual marker')
    for row in audit['max_actual_vertex_events_by_phase']:
        require(row['actual_vertex_max_penetration_m'] <= .00005 or allowed_pad(row)
                or '/tcp/visuals/' in row['obstacle'], 'Actual contact omitted from blocking classification')
    require(all(row['intersection_inscribed_radius_m'] <= .00001
                for row in audit['actual_arm_cube_station_intersections']), 'Arm/station intersection omitted from blockers')
    triangle = read(root / 'qa/06_07_support_triangle_audit.json')
    require(triangle['request_sha256'] == audit['request_sha256'] and
            triangle['evidence_sha256'] == audit['evidence_sha256'] and
            triangle['audit_sha256'] == digest(root / 'qa/06_07_independent_geometry_audit.json'),
            'Triangle audit is not tied to the current request/evidence/equipment audit')
    require(triangle['request_matches_independent_audit'] is True and
            triangle['evidence_matches_independent_audit'] is True and
            triangle['all_sources_unchanged_at_check_end'] is True and
            triangle['topology_source_unchanged'] is True, 'Triangle audit source checks incomplete')
    for path, expected in triangle['source_hashes'].items():
        require(digest(root / path) == expected, 'Triangle audit source changed: ' + path)
    topology_path = root / 'qa/06_07_actual_fruit_triangles.json'
    require(triangle['topology_sha256'] == digest(topology_path), 'Triangle topology changed')
    topology = read(topology_path)
    require(digest(root.parents[2] / topology['source']) == topology['source_sha256'],
            'Original triangle mesh USD changed')
    require(set(topology['meshes']) == {f['source'] for f in motion['fruits']}, 'Triangle audit fruit sources differ')
    require(triangle['original_mesh_points_max_delta_m'] <= 1e-10, 'Triangle topology differs from original mesh points')
    station_hulls = [row for row in audit['conservative_hull_only_events']
                     if row['obstacle'].startswith('/World/HCRStation/')]
    require(triangle['hull_only_station_events_checked'] == len(station_hulls),
            'Triangle audit missed a conservative station-contact event')
    require(triangle['threshold_m'] == .00005 and not triangle['blocking_events'] and
            triangle['actual_triangle_max_penetration_m'] <= .00005,
            'Triangle surface penetration remains or its numerical threshold changed')
    print('Current-input independent joint/equipment audit verified; normal selected pad contacts are distinguished from release collisions. Discrete geometric scope only.')


def verify_continuity(root: Path, ids: set) -> None:
    """GUI 실제 저장 행렬을 사용해 바구니 상대 적재 자세와 재사용 컷을 대조한다."""
    original = root.parent / 'presentation_video_20261104'
    v3 = root.parent / 'presentation_video_revision_v3_20261104'
    before = read(original / 'preview/03_grasp-0149.png.json')
    after = read(v3 / 'preview/04_deposit-0000.png.json')
    for path in ('/World/Vegetation/Bed_02/Fruits/Pepper_0003_red',
                 '/World/harvest_robot/arm_2_gripper_link'):
        matrix_equal(before['inspected'][path], after['inspected'][path], '03→04 ' + path)
    before = read(root / 'preview/05_handoff_continuity-0149.png.json')
    after = read(root / 'preview/06_07_transport_sorting-0000.png.json')
    basket = '/World/transport_robot/cargo_box'
    inverse_before = np.linalg.inv(np.asarray(before['inspected'][basket], dtype=float))
    inverse_after = np.linalg.inv(np.asarray(after['inspected'][basket], dtype=float))
    errors = [matrix_equal(inverse_before @ np.asarray(before['inspected'][p]),
                           inverse_after @ np.asarray(after['inspected'][p]),
                           '05→combined cargo-relative ' + p, 1e-8) for p in ids]
    for info in (before, after):
        require(all(abs(info['state']['joints'][joint]) <= 1e-9 for joint in LID_JOINTS),
                '05 final/combined initial lid closure mismatch')
    assets = read(root / 'handoff_assets.json')
    source_by_clone = dict(zip(assets['clone_paths'], assets['diagnostics']['fruit_sources']))
    require(ids <= set(source_by_clone), 'GUI assets missing active motion IDs')
    unused = set(source_by_clone) - ids
    for stem in ('05_handoff_continuity', '06_07_transport_sorting'):
        request = read(root / 'settings' / (stem + '.json'))
        require(unused <= set(request['base'].get('hide', [])), stem + ': unused legacy clone not hidden from start')
        for state in [request['base']] + [row['state'] for row in request['keyframes']]:
            require(not unused.intersection(state.get('show', [])), stem + ': unused legacy clone shown')
            require(not unused.intersection(state.get('placements', {})), stem + ': unused legacy clone animated')
    sources = [source_by_clone[path] for path in ids]
    require(sum(p.endswith('_red') for p in sources) == sum(p.endswith('_yellow') for p in sources) == 3,
            'GUI clones differ from red3 yellow3')
    expected_sources = {f['source'] for f in read(root / 'settings/06_07_motion_evidence.json')['fruits']}
    require(set(sources) == expected_sources, 'GUI clone sources differ from declared motion sources')
    print(f'03→04 exact world pose; 05→combined six cargo-relative poses/lid closure PASS (max {max(errors):.3g})')


def verify_edit(root: Path) -> None:
    decisions = read(root / 'edit_decisions.json')
    require((decisions['fps'], decisions['frames'], decisions['duration_s']) == (30, 750, 25),
            'Expected 25 seconds/750 frames')
    require(decisions['core_boundaries_frames'] == [0, 90, 180, 270, 360, 450, 750], 'Cut boundaries changed')
    require(decisions['transitions'] == {'dissolve_duration_frames': 6, 'centres_frames': [90, 180, 360, 450],
            'direct_cut_03_to_04_frame': 270}, 'Unexpected transition inside continuous segment')
    require(decisions['continuous_segment'] == {'file': '06_07_transport_sorting.mp4',
            'timeline_frames': [450, 750], 'source_frames': [30, 330], 'internal_cuts': [], 'action_end_frame': 690},
            'Continuous segment must map source [1,11) to edit [15,25)')
    require(decisions['ending'] == {'stable_hold_start_frame': 690, 'fade_start_frame': 726, 'fade_duration_frames': 24},
            'Expected two-second ending including final0.8s fade')
    require(decisions['raw_sources_unchanged'], 'Raw source preservation not confirmed')
    for name, expected in decisions['outputs'].items():
        require(digest(root / name) == expected, 'Stale edit output hash: ' + name)
    captions = (root / 'captions.ass').read_text()
    for line in ('운송 · 선별', '선별장 도킹 · 수확물 배출', '혼합 과실을 색상별로 분류'):
        require(line in captions, 'Missing V4 caption: ' + line)
    require(decisions['inset']['placement_status'] == 'verified on final V3 start, middle and end',
            'Reused actual observation inset changed')
    for name in EDIT_FILES:
        data = subprocess.check_output(['ffmpeg', '-v', 'error', '-i', str(root / name),
                '-vf', 'select=eq(n\\,749)', '-vsync', '0', '-frames:v', '1', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'])
        pixels = np.frombuffer(data, dtype=np.uint8)
        require(pixels.size == 1920 * 1080 * 3 and pixels.max() <= 2, name + ': final frame not black')
    print('25-second edit, continuous source mapping, original scout inset/captions and ending fade PASS')


def verify_phase_qa(root: Path) -> None:
    for stem in ('05_handoff_continuity', '06_07_transport_sorting', 'ManyFarm_25s_captioned'):
        evidence = read(root / 'qa' / f'{stem}-mp4-keyphases.json')
        require(evidence['source_sha256'] == digest(root / (stem + '.mp4')), stem + ': stale QA source')
        require((root / evidence['contact_sheet']).is_file(), stem + ': missing phase sheet')
        require(len(evidence['frames']) >= 9, stem + ': insufficient phase coverage')
        for row in evidence['frames']:
            require(digest(root / row['file']) == row['sha256'], stem + ': stale QA frame')
        review = read(root / 'qa' / f'{stem}-mp4-review.json')
        require(review['passed'] is True and review['source_sha256'] == evidence['source_sha256'],
                stem + ': direct visual inspection not completed for current MP4')
    final = read(root / 'qa/visual_review.json')
    require(final['passed'] is True, 'Final direct visual inspection pending')
    for name in list(RAW_FRAMES) + sorted(EDIT_FILES):
        require(final['videos'][name] == digest(root / name), 'Final review stale: ' + name)
    print('Actual MP4 key-phase evidence and current direct visual review records PASS')


def preflight(root: Path) -> None:
    """촬영과 무관한 준비 검사이며 V4 영상 PASS를 만들지 않는다."""
    originals = verify_originals(root)
    for name in REUSED_FILES:
        path = root / name
        require(path.is_file(), 'Missing reused source: ' + name)
        key = path.resolve().relative_to(root.parents[3]).as_posix()
        require(originals[key] == digest(path), 'Reused source changed: ' + name)
    for name in ('assemble_v4.py', 'extract_phase_qa.py', 'build_manifest.py', 'verify_delivery.py'):
        ast.parse((root / name).read_text(), filename=name)
    require((root.parent / 'presentation_video_revision_v3_20261104/assets/02_scout_insert_card.png').is_file(),
            'Existing scout inset card missing')
    print('PREPARED: reused sources, preservation hashes and Python syntax checked. V4 capture/visual/media checks NOT RUN.')


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--preflight', action='store_true', help='준비 파일만 검사. 촬영/영상 성공 판정 아님')
    args = parser.parse_args()
    root = Path(__file__).resolve().parent
    if args.preflight:
        preflight(root)
        return
    manifest = read(root / 'manifest.json')
    require({r['file'] for r in manifest['clips']} == set(RAW_FRAMES) and len(manifest['clips']) == 2,
            'Expected exactly two newly captured raw clips')
    for record in manifest['clips']:
        verify_video(root, record, RAW_FRAMES[record['file']])
        verify_capture(root, record['file'], RAW_FRAMES[record['file']])
    require({r['file'] for r in manifest['edits']} == EDIT_FILES and len(manifest['edits']) == 2,
            'Expected both 25-second edits')
    for record in manifest['edits']:
        verify_video(root, record, 750)
    originals = verify_originals(root)
    require({r['file'] for r in manifest['reused_clips']} == REUSED_FILES and len(manifest['reused_clips']) == 4,
            'Original 01..04 reuse missing')
    for record in manifest['reused_clips']:
        key = (root / record['file']).resolve().relative_to(root.parents[3]).as_posix()
        require(record['sha256'] == originals[key], 'Reused file changed against initial baseline')
        verify_video(root, record, 150)
    require(bool(manifest['capture_tools']), 'Missing tool/settings snapshots')
    for key in ('capture_tools', 'reused_assets'):
        for name, expected in manifest[key].items():
            require(digest(root / name) == expected, 'Tool/settings/reused asset hash mismatch: ' + name)
    require(set(manifest['evidence_sha256']) == set(manifest['evidence']), 'Missing final evidence hash records')
    require(manifest['evidence'].get('capture_session') == 'capture_session.json' and
            manifest.get('gui') is True and manifest.get('all_beds') is True,
            'GUI capture-session evidence missing from manifest')
    for name, path in manifest['evidence'].items():
        require(digest(root / path) == manifest['evidence_sha256'][name], 'Final evidence changed: ' + path)
    verify_capture_session(root)
    verify_environment(root)
    ids = verify_motion(root)
    verify_independent_geometry(root)
    verify_continuity(root, ids)
    verify_edit(root)
    verify_phase_qa(root)
    print('V4 validation PASS. Manifest, raw captures and source files were not modified.')


if __name__ == '__main__':
    main()
