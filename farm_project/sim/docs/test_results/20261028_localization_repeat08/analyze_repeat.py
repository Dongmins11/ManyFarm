"""저장된 반복시험의 AMCL/odom/실제 자세를 같은 시뮬 시각에서 비교한다."""
import json
import math
import sys
from bisect import bisect_right
from datetime import datetime
from pathlib import Path
import numpy as np

base = Path(sys.argv[1])
meta = json.loads((base/'repeat_metadata.json').read_text())
assert len(meta['drive_files']) == 1, meta
raw_path = Path(meta['drive_files'][0])
raw = [json.loads(line) for line in raw_path.open()]
events = [json.loads(line) for line in (base/'events.jsonl').open()]
result = json.loads((base/'result.json').read_text())
times = np.array([r['sim_time_s'] for r in raw])
truths = np.array([[r['T_world_base'][0][3], r['T_world_base'][1][3],
                   math.atan2(r['T_world_base'][1][0], r['T_world_base'][0][0])] for r in raw])
truths[:, 2] = np.unwrap(truths[:, 2])

def matrix(p: list) -> np.ndarray:
    c, s = math.cos(p[2]), math.sin(p[2])
    return np.array([[c, -s, p[0]], [s, c, p[1]], [0., 0., 1.]])

def pose(position: dict, quaternion: dict) -> list:
    return [position['x'], position['y'], 2*math.atan2(quaternion['z'], quaternion['w'])]

def stamp(data: dict) -> float:
    t = data['header']['stamp']
    return t['sec'] + t['nanosec']/1e9

def truth(t: float) -> np.ndarray:
    return np.array([np.interp(t, times, truths[:, i]) for i in range(3)])

def error(estimate: np.ndarray, actual: np.ndarray) -> dict:
    delta = estimate[:2, 2] - actual[:2, 2]
    return dict(xy_cm=(100*delta).tolist(), norm_cm=float(np.linalg.norm(delta)*100))

# station 설정에 T_map_world가 없으면 단위행렬이다. 실제 자세는 평가에만 사용한다.
station = json.loads((base/'runtime/stations.json').read_text())
assert np.allclose(station.get('evaluation', {}).get('T_map_world', np.eye(4)), np.eye(4))
tfs = [e for e in events if e['kind'] == 'harvest_map_odom']
tf_times = [e['mono_ns'] for e in tfs]
rows, amcl, anchor = [], [], None
for event in events:
    if event['kind'] not in ('harvest_odom', 'harvest_amcl'):
        continue
    data = event['data']; t = stamp(data)
    if t < times[0] or t > times[-1]:
        continue
    p = data['pose']['pose']; measured = matrix(pose(p['position'], p['orientation']))
    actual = matrix(truth(t))
    if event['kind'] == 'harvest_amcl':
        amcl.append(dict(sim_time_s=t, at=event['at'], error=error(measured, actual)))
        continue
    if anchor is None:
        anchor = actual @ np.linalg.inv(measured)
    index = bisect_right(tf_times, event['mono_ns'])-1
    if index < 0:
        continue
    transform = tfs[index]['data']['transform']
    estimated = matrix(pose(transform['translation'], transform['rotation'])) @ measured
    rows.append(dict(sim_time_s=t, at=event['at'], actual=truth(t).tolist(),
        map_pose=[float(estimated[0, 2]), float(estimated[1, 2]), math.atan2(estimated[1, 0], estimated[0, 0])],
        map_error=error(estimated, actual), odom_error=error(anchor@measured, actual)))
jobs = {j['role']: j for j in result.get('frontend_final', {}).get('jobs', [])}
final_result = result.get('dock_final', jobs.get('harvest', {})).get('result', {})
pickup_result = result.get('pickup_final', jobs.get('transport', {})).get('result', {})
end_at = final_result.get('timestamp') or result['harvest']['result']['timestamp']
end = datetime.fromisoformat(end_at).timestamp()
final = min(rows, key=lambda row: abs(datetime.fromisoformat(row['at']).timestamp()-end))
window = json.loads((base/'window.json').read_text())['goal_pose']; target = np.array([window['position']['x'], window['position']['y']])
final = dict(final, result_timestamp=end_at, receive_offset_s=datetime.fromisoformat(final['at']).timestamp()-end,
    actual_goal_distance_cm=float(np.linalg.norm(target-np.array(final['actual'][:2]))*100),
    map_goal_distance_cm=float(np.linalg.norm(target-np.array(final['map_pose'][:2]))*100))
summary = dict(attempt=base.name, passed=result['passed'], dock_ready=result.get('dock_ready', False),
    error=(pickup_result.get('error_message') if pickup_result.get('result_code') == 'FAILED' else final_result.get('error_message')) or result.get('error', ''),
    restore_evaluated=bool(final_result.get('transport_clear')), dock_result=final_result,
    pickup_result=pickup_result, final=final,
    max_amcl=max(amcl, key=lambda row: row['error']['norm_cm']),
    max_odom_error_cm=max(row['odom_error']['norm_cm'] for row in rows),
    raw_drive=str(raw_path), method='USD 자세를 시뮬 시각으로 선형 보간. odom은 초기 자세만 오프라인 정합. map은 직전 수신 TF와 odom의 외부 재구성이며 내부 validator 직접 기록이 아님.')
(base/'localization_analysis.json').write_text(json.dumps(dict(summary=summary, amcl_samples=amcl, odom_map_samples=rows), ensure_ascii=False, indent=2)+'\n')
print(json.dumps(summary, ensure_ascii=False, indent=2))
