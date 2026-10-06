"""시뮬 task.yaml과 원본 연결 그래프에서 현재 공통 코드용 설정을 생성합니다."""
from __future__ import annotations

from copy import deepcopy
import json
import math
from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parents[2]
PREFIX = 'sim/ros_ws/src/farm_sim_config/'
BASE = ROOT / PREFIX


def role_graph(source: dict, role: str) -> dict:
    """공통 탐색기가 읽지 않는 통행 역할을 데이터 생성 시 적용합니다."""
    result = deepcopy(source)
    edges = [f for f in result['features'] if f['geometry']['type'] == 'LineString'
             and role in f['properties']['allowed_roles']]
    used = {f['properties'][key] for f in edges for key in ('startid', 'endid')}
    points = [f for f in result['features'] if f['geometry']['type'] == 'Point'
              and f['properties']['id'] in used]
    result['features'] = points + edges
    result['metadata']['derived_for_role'] = role
    return result


def insert_boundary(graph: dict, node_id: str, xy: list[float]) -> None:
    """원본 YAML의 베드 경계를 기존 직선 엣지에 삽입합니다. 새 통로는 만들지 않습니다."""
    matches = []
    for feature in graph['features']:
        geom = feature['geometry']
        if geom['type'] != 'LineString':
            continue
        a, b = geom['coordinates']
        length = math.dist(a, b)
        if min(math.dist(a, xy), math.dist(b, xy)) > 1e-6 and abs(
                math.dist(a, xy) + math.dist(xy, b) - length) < 1e-8:
            matches.append(feature)
    if len(matches) != 2:
        raise ValueError(f'{node_id}: 경계가 원본 양방향 직선 엣지에 있지 않습니다.')
    graph['features'].append({'type': 'Feature', 'geometry': {'type': 'Point', 'coordinates': xy},
                              'properties': {'id': node_id, 'frame': 'map',
                                             'role': 'survey_boundary', 'source': 'task.yaml'}})
    for feature in matches:
        graph['features'].remove(feature)
        a, b = feature['geometry']['coordinates']
        for index, (start, end, line) in enumerate([
                (feature['properties']['startid'], node_id, [a, xy]),
                (node_id, feature['properties']['endid'], [xy, b])]):
            part = deepcopy(feature)
            part['properties'].update(id=f"{feature['properties']['id']}:{node_id}:{index}",
                                      startid=start, endid=end, cost=math.dist(*line))
            part['geometry']['coordinates'] = line
            graph['features'].append(part)


def harvest_workspace(harvest: dict) -> dict:
    """오른팔 장착점·작업 범위(m)로 논리 base_footprint 평가 상자를 계산합니다."""
    mount, work = harvest['mount_xy_base_m'], harvest['work_offset_xy_base_m']
    lower, upper = harvest['height_offsets_m']
    return dict(
        frame='base_footprint',
        center_m=[round(mount[0] + work[0], 12), round(mount[1] + work[1], 12),
                  round(harvest['height_reference_m'] + (lower + upper) / 2, 12)],
        size_m=[harvest['width_m'], harvest['depth_m'], round(upper - lower, 12)],
        boundary_epsilon_m=1e-6, source=harvest['geometry_status'])


def build() -> dict[str, dict]:
    """미션 구현을 바꾸지 않고 route_file/node_ids와 patrol 계약에 맞춥니다."""
    task = yaml.safe_load((BASE / 'config/task.yaml').read_text())
    source = json.loads((ROOT / task['graph_file']).read_text())
    graphs = {role: role_graph(source, role) for role in ('scout', 'harvest', 'transport')}
    graph_path = PREFIX + 'maps/graph.geojson'
    survey_keys = ('robot_id', 'map_id', 'base_frame', 'vision_config', 'output_dir',
                   'goal_timeout_s', 'arrival_tolerance_m', 'heading_tolerance_rad', 'settle_s',
                   'overlap_fraction', 'association_distance_m', 'association_band_half_depth_m',
                   'evaluation')
    survey = {key: deepcopy(task[key]) for key in survey_keys}
    survey.update(schema_version=1, sections={})
    patrol = dict(schema_version=1, robot_id=task['robot_id'], map_id=task['map_id'],
                  route_graph=graph_path, sections={})
    for section_id, section in task['sections'].items():
        start, end = f'{section_id}_START', f'{section_id}_END'
        geometry = section['survey_geometry']
        insert_boundary(graphs['scout'], start, geometry['start_xy_m'])
        insert_boundary(graphs['scout'], end, geometry['end_xy_m'])
        bed = deepcopy(section)
        observations = bed.pop('observations')
        bed.update(route_file=graph_path,
                   node_ids=[start] + [o['node_id'] for o in observations] + [end])
        survey['sections'][section_id] = bed
        patrol['sections'][section_id] = dict(on_complete='WAIT_FOR_COMMAND', segments=[
            dict(segment_id=o['segment_id'], observation_node_id=o['node_id']) for o in observations])
    # Isaac은 ROS의 YAML 환경을 사용하지 않도록 JSON으로 전달합니다.
    spawn = dict(schema_version=1, map_id=task['map_id'], stations=deepcopy(task['stations']),
                 T_map_world=task['evaluation']['T_map_world'])
    nav = yaml.safe_load((BASE / 'config/nav2_scout.yaml').read_text())
    station = task['stations'][task['robot_id']]
    nav['amcl']['ros__parameters'].update(set_initial_pose=True, initial_pose=dict(
        x=station['xy_m'][0], y=station['xy_m'][1], z=0.0, yaw=station['yaw_rad']))
    outputs = {'config/station_spawn.json': spawn, 'config/nav2_scout.yaml': nav,
            'maps/graph.geojson': graphs['scout'],
            'maps/harvest_graph.geojson': graphs['harvest'],
            'maps/transport_graph.geojson': graphs['transport'],
            'config/scout_survey.json': survey, 'config/scout_patrol.json': patrol}
    if (BASE / 'config/harvest_audit.json').is_file():
        # 예찰 목표 생성과 도착 평가가 같은 장착점·범위를 사용하도록 원본을 공유합니다.
        workspaces = [harvest_workspace(section['harvest']) for section in task['sections'].values()]
        if not workspaces or any(workspace != workspaces[0] for workspace in workspaces[1:]):
            raise ValueError('수확 로봇 평가 상자는 모든 구역에서 같은 로봇 기하를 사용해야 합니다.')
        audit = json.loads((BASE / 'config/harvest_audit.json').read_text())
        audit['evaluation']['workspace'] = workspaces[0]
        outputs['config/harvest_audit.json'] = audit
    if (BASE / 'config/nav2_harvest.yaml').is_file():
        harvest_nav = yaml.safe_load((BASE / 'config/nav2_harvest.yaml').read_text())
        harvest_station = task['stations']['harvest_01']
        harvest_nav['amcl']['ros__parameters']['initial_pose'] = dict(
            x=harvest_station['xy_m'][0], y=harvest_station['xy_m'][1], z=0., yaw=harvest_station['yaw_rad'])
        harvest_task = json.loads((BASE / 'config/harvest_task.json').read_text())
        harvest_task['segments'] = [o['segment_id'] for section in task['sections'].values() for o in section['observations']]
        outputs['config/nav2_harvest.yaml'] = harvest_nav
        outputs['config/harvest_task.json'] = harvest_task
    if (BASE / 'config/harvest_fleet.json').is_file():
        fleet_device = json.loads((BASE / 'config/scout.json').read_text())
        fleet_device['publish_clock'] = False
        fleet_profile = yaml.safe_load((BASE / 'config/scout_runtime.yaml').read_text())
        fleet_profile['device_config'] = PREFIX + 'config/scout_fleet.json'
        outputs['config/scout_fleet.json'] = fleet_device
        outputs['config/scout_fleet_runtime.yaml'] = fleet_profile
    return outputs


def main() -> None:
    outputs = build()
    for relative, data in outputs.items():
        text = (yaml.safe_dump(data, allow_unicode=True, sort_keys=False) if relative.endswith('.yaml')
                else json.dumps(data, ensure_ascii=False, indent=2) + '\n')
        (BASE / relative).write_text(text)
    print(f'sim 경로·관측·station·AMCL 설정 {len(outputs)}개 생성 완료')


if __name__ == '__main__':
    main()
