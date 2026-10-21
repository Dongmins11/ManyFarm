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
                expected_minus_harvested=expected-harvested,
                scout_count_ratio=expected/actual if actual else None,
                harvest_to_expected_ratio=harvested/expected if expected else None,
                harvest_to_actual_ratio=harvested/actual if actual else None)


def _save(path: Path, data: dict) -> None:
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps(data, ensure_ascii=False, indent=2)+'\n')
    temp.replace(path)


def write_performance(output: Path) -> dict:
    """원본 시도를 유지하고 SEC별 최종 성공/최신 시도를 중복 없이 따로 보여 준다."""
    from compare_scout_truth import compare
    surveys = {}
    for path in sorted(output.glob('SEC*_attempt_*/artifacts/scout_survey/*/survey.json')):
        data = json.loads(path.read_text())
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
        if source.exists() and scout.get('task_id') in surveys:
            try:
                scene = json.loads(source.read_text())
                if not scene.get('complete'):
                    raise ValueError('불완전한 정답 snapshot')
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
            data = json.loads(path.read_text())
            windows.append(data)
            events.extend(dict(x, window_id=data['window_id'], evidence=str(path)) for x in data['events'])
        counts = Counter(x['reason'] for x in events)
        performances.update(counts)
        if state.get('status') == 'FAILED':
            failures[state.get('error', 'unknown')] += 1
        row = dict(attempt=directory.name, section=section, status=state.get('status'),
                   policy=state.get('harvest_policy', 'legacy'), counts=ratios(actual, expected, harvested),
                   completed_windows=sum(x['result_code']=='SUCCESS' for x in harvest),
                   total_windows=len(scout.get('harvest_tasks', [])), scout_evaluation=evaluation,
                   performance_events=events, performance_reason_counts=dict(counts),
                   windows=windows, action_error=state.get('error'),
                   diagnostics=[])
        event_path = directory / 'events.jsonl'
        if event_path.exists():
            for line in event_path.read_text().splitlines():
                event = json.loads(line)
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
                  action_failure_reasons=dict(failures), performance_reason_counts_all_attempts=dict(performances),
                  sections={key: {k:v for k,v in row.items() if k not in ('windows','performance_events')}
                            for key,row in latest.items()},
                  attempt_reports=[str(output/row['attempt']/'performance_report.json') for row in rows])
    _save(output / 'performance_summary.json', result)
    return result


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('campaign', type=Path)
    print(json.dumps(write_performance(parser.parse_args().campaign)['sections'], ensure_ascii=False, indent=2))
