"""현재 공통 로더로 복원 데이터·관측 순서·역할별 도달성을 검사합니다. ROS 실행은 아닙니다."""
from __future__ import annotations

import json
import math
from pathlib import Path
import sys
import yaml

ROOT = Path(__file__).resolve().parents[2]
for package in ('farm_navigation', 'scout_robot'):
    sys.path.insert(0, str(ROOT / 'robot/ros_ws/src' / package))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from farm_navigation.configuration import load_environment
from farm_navigation.route import RouteGraph, load_route
from scout_robot.survey_core import StraightBed
from scout_new.patrol_config import apply_patrol, patrol_design
from rebuild_route_data import BASE, build


def main() -> None:
    task = yaml.safe_load((BASE / 'config/task.yaml').read_text())
    for relative, expected in build().items():
        load = yaml.safe_load if relative.endswith('.yaml') else json.loads
        if load((BASE / relative).read_text()) != expected:
            raise ValueError(f'원본과 생성 파일 불일치: {relative}. rebuild_route_data.py 실행 필요')
    environment = load_environment(BASE / 'config/scout_runtime.yaml', ROOT, 'sim')
    graph = RouteGraph(environment['route_graph'])
    canonical = RouteGraph(ROOT / task['graph_file'])
    patrol = json.loads((ROOT / environment['patrol_config']).read_text())
    survey = json.loads(Path(environment['survey_config']).read_text())
    survey = apply_patrol(survey, patrol, graph)
    station = task['stations']['scout_01']['xy_m']
    paths = 0
    stops = 0
    previous = station
    for section_id, config in survey['sections'].items():
        original = task['sections'][section_id]
        bed = StraightBed(load_route(environment['route_graph'], config['node_ids']), config)
        assert math.dist(bed.origin, original['survey_geometry']['start_xy_m']) < 1e-9
        assert math.dist(bed.world(bed.length, 0)[:2], original['survey_geometry']['end_xy_m']) < 1e-9
        design = patrol_design(bed, graph)
        for actual, expected in zip(design['segments'], original['observations'], strict=True):
            assert actual['segment_id'] == expected['segment_id']
            assert abs(math.remainder(bed.yaw - expected['yaw_rad'], 2 * math.pi)) < 1e-9
            position = actual['position_map_m']
            # station 출발/복귀와 모든 구역을 연속 방문하는 경로를 각각 계산합니다.
            for start, end in ((station, position), (position, station), (previous, position)):
                graph.plan(tuple(start), tuple(end))
                paths += 1
            previous = position
            stops += 1
    graph.plan(tuple(previous), tuple(station))
    paths += 1
    stats = {'scout': {'nodes': len(graph.nodes), 'edges': len(graph.edges)}}
    for role in ('harvest', 'transport'):
        role_graph = RouteGraph(BASE / f'maps/{role}_graph.geojson')
        station = task['stations'][f'{role}_01']['xy_m']
        targets = [s['harvest_route'][key] for s in task['sections'].values()
                   for key in ('entry_node_id', 'exit_node_id')]
        if role == 'transport':
            targets.append(task['stations']['sorting_station']['node_id'])
        for node in targets:
            for start, end in ((station, role_graph.nodes[node]), (role_graph.nodes[node], station)):
                role_graph.plan(tuple(start), tuple(end))
                paths += 1
        stats[role] = {'nodes': len(role_graph.nodes), 'edges': len(role_graph.edges)}
    for station in task['stations'].values():
        assert math.dist(canonical.nodes[station['node_id']], station['xy_m']) < 1e-9
    # 모든 canonical 노드가 실제 방향 엣지로 연결되는지 확인합니다.
    adjacency = {node: [] for node in canonical.nodes}
    reverse = {node: [] for node in canonical.nodes}
    for edge in canonical.edges:
        adjacency[edge.start].append(edge.end)
        reverse[edge.end].append(edge.start)
    for links in (adjacency, reverse):
        seen, todo = set(), [next(iter(links))]
        while todo:
            node = todo.pop()
            if node not in seen:
                seen.add(node)
                todo.extend(links[node])
        assert len(seen) == len(canonical.nodes)
    print(json.dumps(dict(canonical_nodes=len(canonical.nodes), canonical_edges=len(canonical.edges),
                          strongly_connected=True, sections=len(survey['sections']), observations=stops,
                          station_records=len(task['stations']), planned_paths=paths, role_graphs=stats,
                          runtime_tested=False), ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
