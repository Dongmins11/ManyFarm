"""예찰 내부 ID 재연결. map 표면 좌표(m)와 색상을 사용하며 한 관측은 일대일 대응한다."""
import math


def match_observations(detections: list[dict], fruits: list[dict], *,
                       max_distance_m: float, ambiguity_margin_m: float) -> tuple[dict, list[dict]]:
    """양쪽 최근접 후보가 일치하고 차선 후보와 충분히 떨어진 경우만 기존 ID를 선택한다."""
    if not math.isfinite(max_distance_m) or not 0 < max_distance_m < .5:
        raise ValueError('max_distance_m must be between 0 and 0.5')
    if not math.isfinite(ambiguity_margin_m) or not 0 <= ambiguity_margin_m < max_distance_m:
        raise ValueError('invalid ambiguity_margin_m')
    rows = [[] for _ in detections]
    cols = [[] for _ in fruits]
    for i, d in enumerate(detections):
        p = d['position_map_m']
        if len(p) != 3 or not all(math.isfinite(v) for v in p):
            raise ValueError('invalid map position')
        for j, f in enumerate(fruits):
            if d['class_name'] != f['class_name']:
                continue
            # 대표 좌표의 중앙값은 작업창에 유지하고 매칭은 가장 최근 실제 측정으로 한다.
            q = f.get('position_latest_map_m', f['position_map_m'])
            distance = math.dist(p, q)
            if distance <= max_distance_m:
                rows[i].append((distance, j)); cols[j].append((distance, i))
    for candidates in rows + cols:
        candidates.sort()
    assigned, diagnostics = {}, []
    for i, candidates in enumerate(rows):
        record = dict(detection_index=i, candidates=[dict(fruit_id=fruits[j]['id'],distance_m=d) for d,j in candidates])
        if not candidates:
            record['reason'] = 'no_same_class_candidate'
        else:
            distance,j = candidates[0]
            reverse = cols[j]
            unique = (len(candidates)==1 or candidates[1][0]-distance > ambiguity_margin_m)
            reciprocal = reverse[0][1]==i and (len(reverse)==1 or reverse[1][0]-distance > ambiguity_margin_m)
            if unique and reciprocal:
                assigned[i] = j
                record.update(reason='matched', fruit_id=fruits[j]['id'], distance_m=distance)
            else:
                record['reason'] = 'ambiguous_new_identity'
        diagnostics.append(record)
    return assigned, diagnostics
