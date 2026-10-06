"""실제 Isaac pose와 과실 중심점으로 작업영역 내 개수를 검사합니다. 제어 입력으로 쓰지 않습니다."""
import json
import math
import time
from types import SimpleNamespace
from pathlib import Path
import numpy as np


def count_snapshot(snapshot: dict, workspace: dict, expected: int, seen: set) -> dict:
    if not snapshot.get('complete'):
        raise ValueError('불완전한 scene snapshot')
    transform = np.asarray(snapshot['T_world_base'], dtype=float)
    if (transform.shape != (4, 4) or not np.isfinite(transform).all()
            or not np.allclose(transform[3], [0, 0, 0, 1])
            or not np.allclose(transform[:3, :3].T @ transform[:3, :3], np.eye(3), atol=1e-5)
            or not np.isclose(np.linalg.det(transform[:3, :3]), 1)):
        raise ValueError('잘못된 실제 로봇 pose')
    center, size = np.asarray(workspace['center_m']), np.asarray(workspace['size_m'])
    if center.shape != (3,) or size.shape != (3,) or not np.isfinite([center,size]).all() or (size <= 0).any():
        raise ValueError('작업영역 설정 오류')
    epsilon = float(workspace.get('boundary_epsilon_m', 1e-6))
    if not math.isfinite(epsilon) or not 0 <= epsilon <= .001:
        raise ValueError('작업영역 경계 오차 설정 오류')
    hits, green, identifiers = [], [], set()
    for fruit in snapshot['fruits']:
        ident = fruit['gt_id']
        if not ident or ident in identifiers:
            raise ValueError('과실 ID 누락/중복')
        identifiers.add(ident)
        world = np.asarray(fruit['center_world_m'], dtype=float)
        if world.shape != (3,) or not np.isfinite(world).all():
            raise ValueError('과실 좌표 오류')
        local = transform[:3, :3].T @ (world - transform[:3, 3])
        if np.all(np.abs(local-center) <= size/2 + epsilon):
            item = dict(fruit, center_base_m=local.tolist())
            if fruit['class_name'] in ('red', 'yellow'): hits.append(item)
            elif fruit['class_name'] == 'green': green.append(item)
    ids = {item['gt_id'] for item in hits}
    return dict(status='OK', expected_count=expected, actual_in_workspace=len(hits),
                count_delta=len(hits)-expected, repeated_gt_ids=sorted(ids & seen),
                matched_fruits=hits, ignored_green_count=len(green),
                T_world_base=transform.tolist(), workspace=workspace,
                stamp_ns=snapshot['stamp_ns'], scene_session=snapshot['scene_session'],
                criterion='fruit_center_in_provisional_box_not_IK')


class SceneEvaluator:
    def __init__(self, config: dict, root: Path) -> None:
        self.config, self.root = config, root
        self.seen = set()
        self.session = None

    def evaluate(self, goal, arrival: dict) -> dict:
        snapshot = json.loads((self.root / self.config['snapshot_file']).read_text())
        if snapshot['robot_id'] != goal.robot_id or snapshot['map_id'] != goal.map_id:
            raise ValueError('snapshot robot/map 불일치')
        age = time.monotonic() - snapshot['written_monotonic_s']
        stamp_delta = (snapshot['stamp_ns'] - arrival['stamp_ns']) / 1e9
        if not 0 <= age <= .5 or not -.25 <= stamp_delta <= .5:
            raise ValueError('도착 시점의 최신 snapshot이 없습니다.')
        if snapshot['scene_session'] != self.session:
            self.session, self.seen = snapshot['scene_session'], set()
        audit = count_snapshot(snapshot, self.config['workspace'], goal.harvest_task.expected_count, self.seen)
        audit.update(snapshot_age_s=age, arrival_stamp_delta_s=stamp_delta)
        self.seen.update(item['gt_id'] for item in audit['matched_fruits'])
        return audit


def evaluate_record(record: dict, evaluator: SceneEvaluator) -> dict:
    """주행 성공 이벤트에만 정답 비교를 붙이며 Action 결과는 변경하지 않습니다."""
    result = dict(record)
    if record['result']['result_code'] != 'SUCCESS':
        result['evaluation'] = dict(status='SKIPPED_NOT_ARRIVED')
        return result
    goal = SimpleNamespace(robot_id=record['robot_id'], map_id=record['map_id'],
        harvest_task=SimpleNamespace(expected_count=record['result']['expected_count']))
    try:
        result['evaluation'] = evaluator.evaluate(goal, record['arrival'])
    except Exception as error:
        result['evaluation'] = dict(status='UNAVAILABLE', error=str(error))
    return result


