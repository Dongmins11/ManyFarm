"""실측 수량 차이를 저장 로그로 감사하고 예찰/선별 판정을 오프라인 재실행한다.

원본 실행·데이터·운영 설정을 수정하지 않는다. GT 최근접 대응은 평가용 가설이다.
실행: python3 sim/tools/analyze_scout_sort_losses.py
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import math
import sys
import tempfile
from collections import defaultdict
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'robot/ros_ws/src/scout_robot'))
from scout_robot.survey_core import StraightBed, Survey
from scout_robot.survey_policy import SurveyPolicy


def read(path: Path) -> dict:
    return json.loads(path.read_text())


def relative(path: Path) -> str:
    return str(path.relative_to(ROOT))


def analyze() -> dict:
    dataset = ROOT/'sim/docs/SCOUT_TO_SORT_16_RECORDS_WITH_SYNTHETIC.json'
    vision_path = ROOT/'sim/vendor/hcr3a_20261008/HCR3A_SIM_TEAM_20261008/workspace/src/sorting_station/hcr/zone_preview.py'
    spec = importlib.util.spec_from_file_location('audit_hcr_vision', vision_path)
    vision = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(vision)
    zones_path = ROOT/'sim/ros_ws/src/farm_sim_config/config/sorter_camera_zones.json'
    zones = read(zones_path)['rois']
    output = []
    for row in read(dataset)['records']:
        if row['synthetic']:
            continue
        base = (ROOT/row['sources']['result']).parent
        result = read(base/'result.json')
        scout_id = result['scout']['result']['harvest_tasks'][0]['window_id'].split('_')[0]
        survey_path = ROOT/'sim/runs/scout_survey'/scout_id/'survey.json'
        survey = read(survey_path)
        section = row['section']
        saved = survey['sections'][section]['survey']
        cfg = survey['config']['sections'][section]
        geometry = cfg['survey_geometry']
        route = [('start', *geometry['start_xy_m'], 0), ('end', *geometry['end_xy_m'], 0)]
        replay = Survey(StraightBed(route, cfg), f'{scout_id}_{section}',
                        survey['config']['association_distance_m'], policy=SurveyPolicy(saved['survey_policy']))
        observations = []
        ids_equal = True
        session = None
        for path in sorted((survey_path.parent/section).glob('observation_*/map_detections.json')):
            mapped = read(path)
            raw = read(path.with_name('observation.json'))
            session = raw['metadata']['session']
            ids = replay.ingest(mapped['accepted'], mapped['segment_id'])
            ids_equal &= ids == mapped['ids']
            observations.append(dict(source=relative(path), segment=mapped['segment_id'],
                accepted=len(mapped['accepted']), ignored=mapped['ignored'], depth_rejected=raw['rejected'],
                detections=[dict(id=i, **d) for i, d in zip(mapped['ids'], mapped['accepted'])]))
        final = replay.record()
        assert ids_equal and final['total_expected_count'] == saved['total_expected_count']
        assert [w['member_ids'] for w in final['windows']] == [w['member_ids'] for w in saved['windows']]
        gt = None
        matching = []
        groups = defaultdict(list)
        cargo = read(base/'cargo_manifest.json')['fruit_paths']
        if row['sources']['bed_initial_scene']:
            scene = read(ROOT/row['sources']['bed_initial_scene'])
            gt = [f for f in scene['fruits'] if f['gt_id'].startswith(cfg['evaluation_bed_prim']+'/Fruits/')
                  and f['class_name'] in ('red', 'yellow')
                  and ((f['center_world_m'][0] < cfg['physical_bed_center_map_m'][0]) == (cfg['survey_side'] == 'west'))]
            assert len(gt) == row['actual_sec_fruit_count']
            for fruit in saved['fruits']:
                distances = sorted((math.dist(fruit['position_map_m'], f['center_world_m']), f['gt_id'])
                                   for f in gt if f['class_name'] == fruit['class_name'].lower())
                distance, target = distances[0]
                match = dict(track=fruit['id'], gt_candidate=target, distance_m=distance,
                             second_best_distance_m=distances[1][0], samples=fruit['position_samples'])
                matching.append(match)
                groups[target].append(fruit)
        duplicates = []
        for target, tracks in groups.items():
            if len(tracks) < 2:
                continue
            a, b = tracks[:2]
            duplicates.append(dict(gt_candidate=target, track_ids=[t['id'] for t in tracks],
                first_observation_distance_m=math.dist(a['position_first_map_m'], b['position_first_map_m']),
                association_gate_m=survey['config']['association_distance_m'],
                detections=[d for o in observations for d in o['detections'] if d['id'] in {t['id'] for t in tracks}]))
        scout_session = session
        resume = read(base/'resume_manifest.json') if (base/'resume_manifest.json').exists() else None
        if resume:
            session = resume['source_session']
        expected_tasks = {x['result']['task_id']: x['result'] for x in result['harvest_results']}
        arms = []
        harvest_base = Path(resume['source']) if resume else base
        final_scene_path = harvest_base/'final_scene.json'
        final_fruits = {f['gt_id']: f for f in read(final_scene_path)['fruits']} if final_scene_path.exists() else {}
        for request_path in sorted((ROOT/'sim/runs/robotarm/student'/session).glob('*/request.json')):
            request = read(request_path)
            if request['window_id'] not in {w['window_id'] for w in saved['windows']}:
                continue
            assert request['task_id'] in expected_tasks, '수확 task_id 불일치'
            arm_dir = request_path.parent
            arm_result = read(arm_dir/'result.json')
            assert arm_result['success_count'] == expected_tasks[request['task_id']]['harvested_count']
            perf = read(arm_dir/'performance.json') if (arm_dir/'performance.json').exists() else {}
            inventories = []
            target_events = []
            last_control = None
            previous_state = None
            timeouts = []
            for line_number, line in enumerate((arm_dir/'trace.jsonl').open(), 1):
                event = json.loads(line)
                kind = event['event']
                if kind == 'CAMERA_INVENTORY':
                    inventories.append(dict(line=line_number, **event))
                elif kind == 'STUDENT_CONTROL':
                    note = event.get('note', {})
                    policy = note.get('policy_note') or {}
                    visual = policy.get('visual_servo') or {}
                    last_control = dict(line=line_number, time_s=event['time_s'],
                        note={k:note.get(k) for k in ('state','target_id','failure')},
                        release_latched=policy.get('release_latched'),
                        visual={k:visual.get(k) for k in ('captured_proxy','observed_transfer_phase','observed_tray_release_latched')})
                    state = json.dumps(event.get('note'), sort_keys=True)
                    if state != previous_state:
                        previous_state = state
                elif kind in ('TARGET', 'STUDENT_ASSIGNED', 'CANDIDATES'):
                    target_events.append(dict(line=line_number, **event))
                elif kind == 'PERFORMANCE_EVENT' and 'timeout' in event.get('reason', ''):
                    timeouts.append(dict(event=event, preceding_control=last_control))
            initial_inventory = []
            if inventories:
                start = inventories[0]['time_s']
                initial_inventory = [x for x in inventories if x['time_s'] <= start+3.01]
            rejected = []
            for inv in initial_inventory:
                lo, hi = inv['task_workspace_min_m'], inv['task_workspace_max_m']
                for detection in inv['detections']:
                    point = detection.get('grasp_estimate_arm_m')
                    if not detection.get('candidate_valid') or point is None:
                        continue
                    excess = [max(lo[i]-point[i], point[i]-hi[i], 0) for i in range(3)]
                    if max(excess) > 0:
                        rejected.append(dict(line=inv['line'], label=detection['label'], point=point, excess_m=excess))
            arms.append(dict(source=relative(arm_dir), window=request['window_id'], expected=request['expected_count'],
                result=arm_result, events=perf.get('events', []),
                initial_inventory_frames=len(initial_inventory),
                initial_visible_range=([min(x['visible_ripe_count'] for x in initial_inventory), max(x['visible_ripe_count'] for x in initial_inventory)] if initial_inventory else None),
                initial_target_range=([min(len(x['targets']) for x in initial_inventory), max(len(x['targets']) for x in initial_inventory)] if initial_inventory else None),
                last_initial_inventory=initial_inventory[-1] if initial_inventory else None,
                workspace_rejection_count=len(rejected),
                workspace_rejection_examples=rejected[:2]+rejected[-2:] if rejected else [],
                timeouts=timeouts, target_events=target_events))
        missing_evidence = []
        for fruit in gt or []:
            if fruit['gt_id'] in cargo:
                continue
            tracks = {m['track'] for m in matching if m['gt_candidate'] == fruit['gt_id']}
            windows = [w['window_id'] for w in saved['windows'] if tracks.intersection(w['member_ids'])]
            projections = []
            for arm in arms:
                if arm['window'] not in windows:
                    continue
                meta_path = ROOT/arm['source']/'camera_initial_metadata.json'
                meta = read(meta_path)['rear']
                point = np.linalg.inv(np.asarray(meta['world_from_optical']['rgb'])) @ np.array([*fruit['center_world_m'],1])
                uvz = np.asarray(meta['intrinsics']['rgb']) @ point[:3]
                projections.append(dict(window=arm['window'], metadata=relative(meta_path),
                    rear_native_uv=(uvz[:2]/uvz[2]).tolist(), optical_depth_m=float(point[2]),
                    image=arm['source']+'/rear_initial.png'))
            final_fruit = final_fruits.get(fruit['gt_id'])
            missing_evidence.append(dict(gt_id=fruit['gt_id'], initial_center=fruit['center_world_m'],
                final_center=final_fruit['center_world_m'] if final_fruit else None,
                final_scene=relative(final_scene_path) if final_fruit else None,
                displacement_m=math.dist(fruit['center_world_m'],final_fruit['center_world_m']) if final_fruit else None,
                candidate_windows=windows, initial_camera_projections=projections))
        arms.sort(key=lambda a:a['window'])
        assert len(arms) == len(saved['windows'])
        post = result['sorter_and_transport_return']
        physical = post['physical_sorting']
        image_path = base/'sorting/camera_rgb.png'
        bgr = cv2.imread(str(image_path))
        assert bgr is not None
        image_replay = {name:dict(zip(('state','red_ratio','yellow_ratio'), vision.classify(bgr[y:y+h,x:x+w], .08,90,60)))
                        for name,(x,y,w,h) in zones.items()}
        broad_roi_scan = {}
        for dy in (40,60,80,100):
            broad_roi_scan[str(dy)] = {name:dict(zip(('state','red_ratio','yellow_ratio'),
                vision.classify(bgr[y+dy:y+dy+h, max(0,x-10):x+w+10],.08,90,60)))
                for name,(x,y,w,h) in zones.items()}
        # 진단용 Y 이동만 오프라인 비교한다. 운영 ROI는 변경하지 않는다.
        shift_scan = {str(dy):{name:vision.classify(bgr[y+dy:y+dy+h,x:x+w],.08,90,60)[0]
                              for name,(x,y,w,h) in zones.items()} for dy in (-10,-5,0,5,10,15,20,30)}
        deposits = []
        for line in (base/'sorting/integration_events.jsonl').open():
            event = json.loads(line)
            if event['event'] in ('virtual_deposit','deposit_result'):
                deposits.append(event)
        assert post['input_count'] == len(cargo)
        assert sum(not f['sorted'] for f in physical['fruits']) == post['input_count']-post['sorted_count']
        output.append(dict(row=row['row'], section=section, classification=row['classification'],
            counts={k:row[k] for k in ('actual_sec_fruit_count','scout_predicted_fruit_count','harvested_basket_fruit_count','sorted_fruit_count')},
            source=row['sources']['result'], scout_source=relative(survey_path), scout_sim_session=scout_session, original_sim_session=session,
            scout_replay=dict(id_sequences_equal=ids_equal, expected_equal=True, window_members_equal=True),
            scout_observations=observations, gt_candidate_matches=matching, duplicate_candidates=duplicates,
            gt_without_nearest_track=([f['gt_id'] for f in gt if f['gt_id'] not in groups] if gt is not None else None),
            gt_not_in_basket=([f['gt_id'] for f in gt if f['gt_id'] not in cargo] if gt is not None else None),
            basket_outside_sec=([p for p in cargo if p not in {f['gt_id'] for f in gt}] if gt is not None else None),
            missing_fruit_evidence=missing_evidence, arms=arms, arm_laser_success_sum=sum(a['result']['success_count'] for a in arms),
            sorting=dict(source=relative(base/'sorting'), input=post['input_count'], sorted=post['sorted_count'],
                remaining=[f for f in physical['fruits'] if not f['sorted']], events=physical['events'],
                final_state=read(base/'sorting/state.json'), deposits=deposits,
                replay=image_replay, offline_roi_y_shift_scan=shift_scan, offline_wider_roi_scan=broad_roi_scan,
                image_sha256=hashlib.sha256(image_path.read_bytes()).hexdigest())))
    sys.path.insert(0, str(ROOT/'robot/ros_ws/src/hcr_sorting'))
    from hcr_sorting.core import Journal, Settings, Supervisor
    with tempfile.TemporaryDirectory() as tmp:
        journal = Journal(Path(tmp)/'replay.sqlite3')
        controller = Supervisor(journal, Settings())
        observation = lambda t, i: dict(monotonic=t, ready=True, camera_session='offline', counter=i,
                                        zone_states={n:'NO_COLOR' for n in 'ABCD'})
        controller.tick(10., observation(10., 0), [(10.,1,0,0,0)])
        assert controller.start('offline-test', 'offline-batch', 10.)
        for index in range(1, 41):
            now = 10.+index/10
            controller.tick(now, observation(now,index), [(now,1,0,0,0)])
        empty_replay = controller.result
        assert empty_replay['result_code'] == 'SUCCESS'
        journal.db.close()
    return dict(description='원본 실측 로그 감사. 합성 행 제외. GT 최근접은 동색 3D 평가 후보이며 객체 ID 증명이 아님.',
        scope='오프라인 기록 재생; 새 Isaac 전체 주행/물리 재실행 없음',
        no_color_completion_replay=empty_replay,
        dataset_sha256=hashlib.sha256(dataset.read_bytes()).hexdigest(),
        classifier_source=relative(vision_path), classifier_sha256=hashlib.sha256(vision_path.read_bytes()).hexdigest(),
        replay_roi_source=relative(zones_path), replay_rois=zones, records=output)


if __name__ == '__main__':
    report = analyze()
    path = ROOT/'sim/docs/SCOUT_TO_SORT_LOSS_ANALYSIS.json'
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False)+'\n')
    for row in report['records']:
        print(row['row'], row['counts'], 'laser',row['arm_laser_success_sum'],
              'duplicates',len(row['duplicate_candidates']), 'replay',row['sorting']['replay'])
    print(path)
