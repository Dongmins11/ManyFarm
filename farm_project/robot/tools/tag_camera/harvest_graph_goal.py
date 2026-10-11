#!/usr/bin/env python3
"""현재 설정의 그래프에서 시험 Goal을 생성한다. ROS·이동 요청은 실행하지 않는다."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import uuid
import yaml


def build_goal(root: Path, node_id: int = 14, heading_from: int = 13,
               section_id: str = 'SEC_01') -> dict:
    """설정에서 ID·좌표를 읽고 진입 엣지 방향을 최종 yaw로 사용한다."""
    env = yaml.safe_load((root / 'robot/config/environments/harvest_real.yaml').read_text())
    config = json.loads((root / env['harvest_config']).read_text())
    if any(config[k] != env[k] for k in ('robot_id', 'map_id')):
        raise ValueError('수확/환경 식별자 불일치')
    if config['completion_policy'] != 'ARRIVAL_ONLY_NO_HARVEST':
        raise ValueError('이 도구는 이동 전용 시험만 지원합니다.')
    if section_id != config.get('default_section_id') or len(config['sections']) != 1:
        raise ValueError('등록되지 않은 section_id')
    features = json.loads((root / env['route_graph']).read_text())['features']
    points = {f['properties']['id']: f['geometry']['coordinates'][:2]
              for f in features if f['geometry']['type'] == 'Point'}
    edges = {(f['properties']['startid'], f['properties']['endid'])
             for f in features if f['geometry']['type'] in ('LineString', 'MultiLineString')}
    if (heading_from, node_id) not in edges:
        raise ValueError('최종 방향 기준 노드에서 목표로 연결된 방향 엣지가 없습니다.')
    x, y = points[node_id]
    a, b = points[heading_from]
    if not all(math.isfinite(v) for v in (x, y, a, b)) or (x, y) == (a, b):
        raise ValueError('잘못된 목표/방향 기준 좌표')
    return dict(robot_id=config['robot_id'], map_id=config['map_id'],
                harvest_task=dict(task_id='graph_test_' + uuid.uuid4().hex,
                    window_id='manual_test_node' + str(node_id),
                    goal_pose=dict(frame_id=env['navigation']['map_frame'],
                                   position=dict(x=x, y=y, z=0.0), yaw=math.atan2(y-b, x-a)),
                    expected_count=0),
                timestamp=datetime.now(timezone.utc).isoformat())


def main() -> None:
    """인자를 읽고 JSON을 표준 출력한다."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project-root', type=Path, default=Path(__file__).resolve().parents[3])
    parser.add_argument('--node', type=int, default=14)
    parser.add_argument('--heading-from', type=int, default=13)
    parser.add_argument('--section', default='SEC_01')
    args = parser.parse_args()
    print(json.dumps(build_goal(args.project_root.resolve(), args.node, args.heading_from,
                               args.section), ensure_ascii=False))


if __name__ == '__main__':
    main()
