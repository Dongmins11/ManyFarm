"""원본 11개와 명시적 합성 5개를 분리 표시한 발표용 JSON을 만든다."""
import json
from pathlib import Path
from statistics import mean
import yaml

ROOT = Path(__file__).resolve().parents[2]

def build() -> dict:
    audit = json.loads((ROOT/'sim/docs/SCOUT_TO_SORT_SUCCESS_AUDIT.json').read_text())
    task_path = ROOT/'sim/ros_ws/src/farm_sim_config/config/task.yaml'
    sections = yaml.safe_load(task_path.read_text())['sections']
    rows = []
    for entry in audit['records']:
        if entry['row'] == 5:
            continue
        source = ROOT/entry['source']
        base = source.parent
        result = json.loads(source.read_text())
        cargo_path = base/'cargo_manifest.json'
        cargo = json.loads(cargo_path.read_text())
        paths = cargo['fruit_paths']
        assert cargo['success'] and len(set(paths)) == len(paths) == cargo['count']
        beds = {p.split('/Fruits/')[0] for p in paths}
        assert len(beds) == 1
        bed = next(iter(beds))
        scene_base = base
        if (base/'resume_manifest.json').exists():
            scene_base = Path(json.loads((base/'resume_manifest.json').read_text())['source'])
            if not scene_base.is_absolute(): scene_base = ROOT/scene_base
        scene = scene_base/'initial_scene.json'
        spec = sections[entry['section']]
        assert spec['evaluation_bed_prim'] == bed
        side = spec['survey_side']
        assert side in ('west', 'east')
        center_x = spec['physical_bed_center_map_m'][0]
        sec_count = None
        by_class = None
        if scene.exists():
            fruits = [f for f in json.loads(scene.read_text())['fruits'] if f['gt_id'].startswith(bed+'/Fruits/')]
            assert fruits and len({f['gt_id'] for f in fruits}) == len(fruits)
            fruits = [f for f in fruits if f['class_name'] in ('red', 'yellow')
                      and ((f['center_world_m'][0] < center_x) if side == 'west'
                           else (f['center_world_m'][0] > center_x))]
            sec_count = len(fruits)
            by_class = {c:sum(f['class_name'] == c for f in fruits) for c in ('red', 'yellow')}
        post = result['sorter_and_transport_return']
        assert cargo['count'] == post['input_count']
        sorted_count = post['sorted_count']
        assert 0 <= sorted_count <= cargo['count']
        rows.append(dict(row=entry['row'], data_type='recorded_simulation', synthetic=False,
            section=entry['section'], bed=bed.rsplit('/',1)[-1], classification=entry['classification'],
            overall_passed=entry['overall_passed'],
            actual_sec_fruit_count=sec_count, survey_side=side,
            scout_predicted_fruit_count=result['scout']['result']['total_expected_count'],
            harvested_basket_fruit_count=cargo['count'], sorted_fruit_count=sorted_count,
            sec_fruits_by_class=by_class,
            sources=dict(section_geometry=str(task_path.relative_to(ROOT)), result=entry['source'], basket_manifest=str(cargo_path.relative_to(ROOT)),
                         bed_initial_scene=str(scene.relative_to(ROOT)) if scene.exists() else None),
            missing_data_reason=None if scene.exists() else '원 실행의 initial_scene.json 없음. 다른 실행의 SEC 과실 수를 복사하지 않음.'))
    fields = ['actual_sec_fruit_count','scout_predicted_fruit_count','harvested_basket_fruit_count','sorted_fruit_count']
    means = {k:mean(r[k] for r in rows if r[k] is not None) for k in fields}
    recorded_rows = list(rows)
    base_rows = [r['row'] for r in recorded_rows]
    offsets = {5:(0,0,0,0), 13:(-1,0,-1,-1), 14:(0,-1,0,0), 15:(1,1,1,1), 16:(0,0,0,0)}
    for i, delta in offsets.items():
        values = {k:max(0,round(means[k])+v) for k,v in zip(fields,delta)}
        assert values['sorted_fruit_count'] <= values['harvested_basket_fruit_count'] <= values['actual_sec_fruit_count']
        rows.append(dict(row=i,data_type='synthetic',synthetic=True,section=None,bed=None,
            classification='평균 기반 합성 예시 · 실행하지 않음',overall_passed=None,**values,
            sources=None,generation=dict(base_rows=base_rows,offsets=dict(zip(fields,delta)))))
    rows.sort(key=lambda r:r['row'])
    excluded = next(e for e in audit['records'] if e['row'] == 5)
    return dict(schema_version=3,description='시뮬 기록 11개 + 합성 예시 5개. 16회 실험 결과가 아님.',
        recorded_row_count=11,synthetic_row_count=5,
        excluded_records=[dict(original_audit_row=5, source=excluded['source'],
            reason='사용자 요청으로 ROI 수정 전 10개 투입/1개 선별 기록을 이 파생 데이터에서 제외. 원본·감사 목록은 보존.',
            replacement_row=5, replacement_type='synthetic')],
        definitions=dict(actual_sec_fruit_count='초기 스냅샷에서 해당 SEC 면의 red/yellow 과실만 집계. task.yaml의 Bed 중심 x와 west/east로 구분; green 제외. 영상 가시성이나 팔 도달 가능성 필터는 적용하지 않음.',
            scout_predicted_fruit_count='scout.result.total_expected_count: 예찰이 수확 작업에 배정한 예측 합계.',
            harvested_basket_fruit_count='cargo_manifest의 실제 바구니 안 분리 과실 고유 경로 수. 선별장 input_count와 일치 확인. 레이저/수확 액션 카운터 사용 안 함.',
            sorted_fruit_count='sorter_and_transport_return.sorted_count: 기록된 선별 수.',
            synthetic='true인 행은 임의 생성값이며 실측 성공률·독립 실험 수에서 제외.'),
        limitations=['기존 실행의 가상 인계 기구를 포함한 시뮬 기록이다. 실물 장치 실험 데이터가 아니다.',
            '이전 예찰·수확 재사용 기록 및 전체 실패 기록의 분류를 보존했다.',
            '미확인 실측값은 null이다. 합성 평균 계산에서 null은 제외했다.'],
        synthetic_generation=dict(method='5번을 제외한 실측 11행 필드별 평균을 정수 반올림한 뒤 명시된 -1/0/+1 편차 적용',
            recorded_means=means,non_null_sample_counts={k:sum(r[k] is not None for r in recorded_rows) for k in fields}),records=rows)

if __name__ == '__main__':
    output = ROOT/'sim/docs/SCOUT_TO_SORT_16_RECORDS_WITH_SYNTHETIC.json'
    data = build()
    output.write_text(json.dumps(data,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
    print(output)
    for row in data['records']:
        print(row['row'],row['data_type'],*[row[k] for k in data['synthetic_generation']['recorded_means']])
