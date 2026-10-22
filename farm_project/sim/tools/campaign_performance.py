"""예찰/수확 실적의 오프라인 집계. 정답은 제어·Action 판정에 전달하지 않는다."""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def ratios(actual: int | None, expected: int, harvested: int) -> dict:
    """개수 비율은 정밀도/재현율과 구분한다. 중복/과검출 때문에 1을 넘을 수 있다."""
    return dict(actual_target_count=actual, expected_count=expected, harvested_count=harvested,
                actual_minus_expected=actual-expected if actual is not None else None,
                expected_minus_harvested=expected-harvested,
                scout_count_ratio=expected/actual if actual else None,
                harvest_to_expected_ratio=harvested/expected if expected else None,
                harvest_to_actual_ratio=harvested/actual if actual else None)


def _save(path: Path, data: dict) -> None:
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps(data, ensure_ascii=False, indent=2)+'\n')
    temp.replace(path)


def loss_breakdown(evaluation: dict, windows: list, directory: Path) -> dict:
    """객체 대응 손실과 개수 차이를 분리한다. 미확인 원인을 AI 오류로 확정하지 않는다."""
    if evaluation.get('status') != 'OK':
        return dict(status='UNAVAILABLE', reason=evaluation.get('reason'))
    detected = {x['gt_id'] for x in evaluation['matches']}
    missed = set(evaluation['missed_gt_ids'])
    covered = {x for w in evaluation['window_checks'] for x in w['matched_gt_ids']}
    arm = {}
    evidence_errors = []
    for path in sorted(directory.glob('artifacts/robotarm/student/*/*/performance.json')):
        try:
            data = json.loads(path.read_text())
        except (OSError, ValueError) as error:
            evidence_errors.append(dict(path=str(path), error=str(error)))
            continue
        wid = data['window_id']
        entry = dict(camera_gt=set(), attempted_gt=set(), passage_associated_gt=set(),
                     unresolved_camera_ids=set(), evidence=str(path))
        trace = path.with_name('trace.jsonl')
        if trace.exists():
            for line in trace.open():
                try:
                    event = json.loads(line)
                except ValueError as error:
                    evidence_errors.append(dict(path=str(trace), error=str(error)))
                    break
                if event['event'] == 'CANDIDATES':
                    for item in event.get('candidates', []):
                        if item.get('target_id'):
                            entry['camera_gt'].add(item['target_id'])
                        else:
                            entry['unresolved_camera_ids'].add(item.get('camera_target_id'))
                elif event['event'] == 'TARGET' and event.get('target_id'):
                    entry['attempted_gt'].add(event['target_id'])
                elif event['event'] == 'ATTEMPT_RESULT' and event.get('success') and event.get('target_id'):
                    entry['passage_associated_gt'].add(event['target_id'])
        arm[wid] = entry
    cases = []
    arm_counts = Counter()
    for w in evaluation['window_checks']:
        entry = arm.get(w['window_id'])
        for gt in set(w['matched_gt_ids']):
            if entry is None:
                category = 'window_not_completed_or_evidence_missing'
            elif gt in entry['passage_associated_gt']:
                category = 'laser_passage_associated_with_target'
            elif gt in entry['attempted_gt']:
                category = 'attempted_without_confirmed_basket_passage'
            elif gt in entry['camera_gt']:
                category = 'camera_target_not_attempted'
            elif entry['unresolved_camera_ids']:
                category = 'camera_identity_unresolved'
            else:
                category = 'not_selected_by_arm_camera'
            arm_counts[category] += 1
            cases.append(dict(window_id=w['window_id'], gt_id=gt, category=category,
                              evidence=entry['evidence'] if entry else None))
    return dict(status='OK', evidence_errors=evidence_errors,
        scout=dict(not_matched_to_scout_ids=sorted(missed),
                   detected_without_window_gt_ids=sorted(detected-covered),
                   unique_gt_missing_from_windows=sorted((detected|missed)-covered),
                   possible_duplicate_detection_ids=evaluation['possible_duplicate_ids'],
                   duplicate_window_gt_owners=evaluation['duplicate_window_gt_owners'],
                   unmatched_prediction_ids=evaluation['unmatched_ids'],
                   unmatched_window_member_ids=[dict(window_id=w['window_id'], ids=w['unmatched_member_ids'])
                                               for w in evaluation['window_checks'] if w['unmatched_member_ids']],
                   matched_unique_window_target_count=len(covered)),
        arm=dict(matched_window_object_case_counts=dict(arm_counts), cases=cases,
                 note='카메라 선택 목록/평가 ID 대응 기준. 레이저 통과의 물체 ID는 확정하지 않는다. 누락 영상 검출 자체와 선택 제외를 구분할 증거가 없으면 원인 미확정.'),
        likely_causes=dict(
            not_matched_to_scout_ids=['가림/시야 밖', 'AI 미검출', '깊이 거부', '위치 오차/객체 대응 실패'],
            detected_without_window_gt_ids=['작업 범위/윈도우 배정 조건', '경로/윈도우 생성 제약'],
            not_selected_by_arm_camera=['가림/AI 미검출', '깊이/작업범위 필터', '객체 대응 오차'],
            attempted_without_confirmed_basket_passage=['파지/절단/이송 실패', '낙하', '60초 제한 후 재시도 실패'],
            possible_duplicate_detection_ids=['다중 시점 ID 연결 실패', 'RGB-D 위치 편차'],
            unassigned_fruit_detached=['팔/집게의 인접 과실 접촉']),
        interpretation='모든 원인은 후보이며 사건/영상 근거 없이 확정하지 않는다. A-B/B-C 단순 차이는 중복·과검출 때문에 객체별 누락과 다를 수 있다.')


def write_report(output: Path, result: dict) -> None:
    """비교 가능한 SEC별 A/B/C 및 상세 JSON 근거를 읽을 수 있는 보고서로 쓴다."""
    lines = ['# SEC01~16 예찰·수확 시험', '', f"갱신: {result['updated_at']}", '',
             'A=해당 관측면·작업 높이의 실제 red/yellow. B=예찰 expected 합계. C=바구니 레이저 통과.',
             '전체 배치 수와 제외 사유는 JSON에 별도 기록. 각 SEC는 새 장면이므로 전체 합계는 관측면 시험 합계다.', '',
             '| SEC | 상태 | A | B | C | B/A | C/B | C/A |', '|---|---|---:|---:|---:|---:|---:|---:|']
    details = []
    for sec, row in sorted(result['sections'].items()):
        c = row['counts']
        values = [sec, row['status'], c['actual_target_count'], c['expected_count'], c['harvested_count']]
        values += [f"{c[k]:.1%}" if c[k] is not None else '미확인'
                   for k in ('scout_count_ratio', 'harvest_to_expected_ratio', 'harvest_to_actual_ratio')]
        lines.append('| ' + ' | '.join(str(x) for x in values) + ' |')
        loss = row.get('loss_breakdown', {})
        if loss.get('status') == 'OK':
            details += ['', f"## {sec} 원인 분류", '',
                f"예찰 최종 ID 미대응: {len(loss['scout']['not_matched_to_scout_ids'])}개(가림/AI/깊이/위치 오차 원인 미확정)",
                f"검출 ID 대응 성공, 윈도우 없음: {len(loss['scout']['detected_without_window_gt_ids'])}개",
                f"중복 검출 후보: {len(loss['scout']['possible_duplicate_detection_ids'])}개; 중복 윈도우 소속: {len(loss['scout']['duplicate_window_gt_owners'])}개",
                '팔 대상별 분류: ' + json.dumps(loss['arm']['matched_window_object_case_counts'], ensure_ascii=False),
                '성능 사건: ' + json.dumps(row['performance_reason_counts'], ensure_ascii=False),
                f"근거: {row['attempt']}/performance_report.json", '']
    lines += details
    lines += ['', '## 오류 및 해석', '',
              json.dumps(result['action_failure_reasons'], ensure_ascii=False),
              '동일 오류 누적3회 생략은 summary.json의 skipped_sections 및 skip_reason.json 참조.',
              '객체별 원인 후보/원본 경로는 performance_summary.json 및 각 시도 performance_report.json 참조.',
              '실패 시도는 최종 수확 실적에 중복 합산하지 않는다. 개수 비율은 정밀도/재현율이 아니다.',
              'C는 레이저 계수이며 통과한 물체의 ID 확정과는 구분한다.']
    (output/'report.md').write_text('\n'.join(lines)+'\n')


def write_performance(output: Path) -> dict:
    """원본 시도를 유지하고 SEC별 최종 성공/최신 시도를 중복 없이 따로 보여 준다."""
    from compare_scout_truth import compare
    surveys = {}
    evidence_errors = []
    for path in sorted(output.glob('SEC*_attempt_*/artifacts/scout_survey/*/survey.json')):
        try:
            data = json.loads(path.read_text())
        except (OSError, ValueError) as error:
            evidence_errors.append(dict(path=str(path), error=str(error)))
            continue
        surveys.setdefault(data.get('goal', {}).get('task_id'), (path, data))
    rows, latest, failures, performances = [], {}, Counter(), Counter()
    baseline = output / 'evaluation_scene_initial.json'
    for directory in sorted(output.glob('SEC*_attempt_*')):
        path = directory / 'result.json'
        if not path.exists():
            continue
        state = json.loads(path.read_text())
        section = state.get('section', directory.name.split('_attempt_')[0])
        scout = state.get('scout_result', {}).get('result', {})
        harvest = [x['result'] for x in state.get('harvest_results', [])]
        expected = sum(t['expected_count'] for t in scout.get('harvest_tasks', []))
        harvested = sum(x['harvested_count'] for x in harvest)
        source = directory / 'initial_scene.json'
        retrospective = not source.exists()
        if retrospective:
            source = baseline
        evaluation = dict(status='UNAVAILABLE', reason='수확 전 정답 또는 예찰 상세 보고 없음')
        actual = None
        scene_total = None
        if source.exists() and scout.get('task_id') in surveys:
            try:
                scene = json.loads(source.read_text())
                if not scene.get('complete'):
                    raise ValueError('불완전한 정답 snapshot')
                scene_total = len(scene['fruits'])
                truth = dict(fruits=[dict(f, bed_prim=f['gt_id'].split('/Fruits/')[0],
                                         class_name=f['class_name'].capitalize()) for f in scene['fruits']])
                survey_path, survey = surveys[scout['task_id']]
                compared = compare(survey, truth, ROOT, .03)
                evaluation = dict(status='OK', scene_source=str(source),
                                  survey_source=str(survey_path), retrospective_same_scene=retrospective,
                                  **compared['sections'][section])
                actual = evaluation['placed_target_count']
            except Exception as error:
                evaluation = dict(status='UNAVAILABLE', reason=str(error))
        events, windows = [], []
        for path in sorted(directory.glob('artifacts/robotarm/student/*/*/performance.json')):
            try:
                data = json.loads(path.read_text())
            except (OSError, ValueError) as error:
                evidence_errors.append(dict(path=str(path), error=str(error)))
                continue
            windows.append(data)
            events.extend(dict(x, window_id=data['window_id'], evidence=str(path)) for x in data['events'])
        counts = Counter(x['reason'] for x in events)
        performances.update(counts)
        if state.get('status') == 'FAILED':
            failures[state.get('error', 'unknown')] += 1
        row = dict(attempt=directory.name, section=section, status=state.get('status'),
                   policy=state.get('harvest_policy', 'legacy'), counts=ratios(actual, expected, harvested),
                   scene_placed_fruit_count=scene_total,
                   scout_observation_counts=({key: sum(o.get(key,0) for o in surveys[scout['task_id']][1].get('observations',[]) if o.get('section') == section) for key in ('valid_depth_detection_count','depth_rejected_count','section_accepted_count','outside_section_count')} if scout.get('task_id') in surveys else {}),
                   loss_breakdown=loss_breakdown(evaluation, windows, directory),
                   completed_windows=sum(x['result_code']=='SUCCESS' for x in harvest),
                   total_windows=len(scout.get('harvest_tasks', [])), scout_evaluation=evaluation,
                   performance_events=events, performance_reason_counts=dict(counts),
                   windows=windows, action_error=state.get('error'),
                   diagnostics=[])
        event_path = directory / 'events.jsonl'
        if event_path.exists():
            for line in event_path.read_text().splitlines():
                try:
                    event = json.loads(line)
                except ValueError as error:
                    evidence_errors.append(dict(path=str(event_path), error=str(error)))
                    break
                if event.get('kind') == 'diagnostic_error':
                    row['diagnostics'].append(event)
        _save(directory / 'performance_report.json', row)
        rows.append(row)
        if section not in latest or latest[section]['status'] != 'SUCCESS':
            latest[section] = row
    result = dict(updated_at=datetime.now(timezone.utc).isoformat(),
                  scope='각 SEC의 작업 높이/관측면/경로 내 red/yellow; 정답은 평가 전용',
                  limitations=['개수 비율은 객체별 정밀도/재현율이 아니다.',
                               '실제 수확은 익명 레이저 통과이며 물체 ID를 확정하지 않는다.',
                               'retrospective_same_scene은 동일 지도 가정의 후속 초기 장면 평가다.',
                               'legacy 시도에는 새 성능 사건 계측이 없으므로 사건0으로 해석하지 않는다.'],
                  evidence_errors=evidence_errors,
                  action_failure_reasons=dict(failures), performance_reason_counts_all_attempts=dict(performances),
                  sections={key: {k:v for k,v in row.items() if k not in ('windows','performance_events')}
                            for key,row in latest.items()},
                  attempt_reports=[str(output/row['attempt']/'performance_report.json') for row in rows])
    _save(output / 'performance_summary.json', result)
    write_report(output, result)
    return result


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('campaign', type=Path)
    print(json.dumps(write_performance(parser.parse_args().campaign)['sections'], ensure_ascii=False, indent=2))
