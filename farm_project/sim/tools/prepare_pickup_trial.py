"""실물 운송 인계 설정을 보존하고 시뮬 시험의 프레임·장치·배치만 연결한다."""
import copy
import json
from pathlib import Path
import subprocess

import yaml

from prepare_harvest_handoff import ROOT, CONFIG

SOURCE = '9686aca909cb52191862ee3500c62fadf7a8ed38'


def prepare_pickup(runtime: Path, window: dict, *, sorter: bool = False) -> None:
    """첫 윈도우의 북쪽에서 실제 42 접근→차체 회전→41 도킹을 시험한다."""
    def read_source(path: str) -> dict:
        return yaml.safe_load(subprocess.check_output(
            ['git', 'show', SOURCE+':farm_project/'+path], cwd=ROOT))

    def write(name: str, value: dict) -> str:
        path = runtime/name
        path.write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n')
        return str(path.relative_to(ROOT))

    source = read_source('robot/config/environments/transport_docking_trial.yaml')
    targets = read_source('robot/config/docking/waffle_marker_targets.yaml')
    for target in targets['targets'].values():
        if target.get('base_frame') == 'base_footprint':
            target['base_frame'] = 'transport_01/base_footprint'
    target_path = write('pickup_targets.json', targets)
    profile = yaml.safe_load((CONFIG/'transport_runtime.yaml').read_text())
    original_device_backend = copy.deepcopy(profile['mechanical_device'])
    profile['pickup_workflow'] = copy.deepcopy(source['pickup_workflow'])
    profile['pickup_targets_file'] = target_path
    profile['pickup_profile'] = source['pickup_profile']
    profile['mechanical_device'] = copy.deepcopy(source['mechanical_device'])
    profiles = read_source('robot/config/docking/waffle_profiles.yaml')['profiles']
    names = ['harvest_approach_42','harvest_dock_41','harvest_clear',
             'sort_01_distance_trial','sort_departure_distance_trial']
    if sorter:names.append('sort_01')  # 공통 SorterApproach의 주행 중 마커 관측 프로파일.
    selected = {name:profiles[name] for name in names}
    def frames(value: object) -> object:
        if isinstance(value,dict):return {k:frames(v) for k,v in value.items()}
        if isinstance(value,list):return [frames(v) for v in value]
        return 'transport_01/'+value if isinstance(value,str) and value in (
            'base_footprint','base_link','base_scan','odom') else value
    selected = frames(selected)
    # 승인된 시뮬 관측 수명·전환 여유만 적용하며 실제 도킹 허용범위는 보존한다.
    route_handoff = selected['harvest_approach_42']['route_handoff']
    observation_before = route_handoff['observation_timeout_s']
    margin_before = route_handoff.get('approach_margin_m', 0.)
    sim_handoff = yaml.safe_load(
        (CONFIG/'docking/transport_profiles.yaml').read_text()
    )['profiles']['harvest_approach_42']['route_handoff']
    for key in ('observation_timeout_s', 'approach_margin_m'):
        route_handoff[key] = sim_handoff[key]
    for item in selected.values():
        item['collision_guard']['nav2_file'] = str(CONFIG/'nav2_transport.yaml')
    # 시험 초기 배치와 AMCL 초기값은 동일한 기존 그래프 게이트에서 가져온다.
    graph = json.loads((ROOT/profile['route_graph']).read_text())
    # 선별장 이격의 지도 방향/노드만 시뮬 자료에 결합한다. 실물 거리·속도·판정 유지.
    destinations = yaml.safe_load((ROOT/profile['destinations']).read_text())['destinations']
    sorter = destinations['SORT_01']
    exit_nodes = {f['properties']['endid'] for f in graph['features']
        if f['geometry']['type'] in ('LineString','MultiLineString')
        and f['properties']['startid'] == sorter['approach_node_id']}
    if len(exit_nodes) != 1:
        raise ValueError('선별장 접근점에서 나가는 단일 기존 경로 필요')
    departure = selected['sort_departure_distance_trial']['distance_departure']
    departure_before = copy.deepcopy(departure)
    departure['map_yaw_rad'] = sorter['approach_yaw_rad']
    departure['exit_rotation'].update(graph_file=str(ROOT/profile['route_graph']),
        from_node_id=sorter['approach_node_id'], to_node_id=next(iter(exit_nodes)))
    profile['precision_profiles'] = write('precision_profiles.json',dict(profiles=selected))
    nodes = {f['properties']['id']: f['geometry']['coordinates']
             for f in graph['features'] if f['geometry']['type'] == 'Point'}
    initial = nodes[20102]
    stations = json.loads((runtime/'stations.json').read_text())
    yaw = window['goal_pose']['yaw']
    stations['stations']['transport_01'].update(xy_m=initial[:2], yaw_rad=yaw)
    write('stations.json', stations)
    nav = yaml.safe_load((CONFIG/'nav2_transport.yaml').read_text())
    nav['amcl']['ros__parameters']['initial_pose'] = dict(x=initial[0], y=initial[1], z=0., yaw=yaw)
    profile['nav_params'] = write('nav2_transport.json', nav)
    device = json.loads((CONFIG/'transport.json').read_text())
    device['camera']['ros_info_reliable'] = True
    device['runtime']['diagnostic_period_s'] = .05
    profile['device_config'] = write('transport.json', device)
    write('transport_runtime.json', profile)
    fleet = json.loads((runtime/'fleet.json').read_text())
    fleet['device_configs'] = [profile['device_config'] if p.endswith('/transport.json') else p
                               for p in fleet['device_configs']]
    layout = json.loads((ROOT/fleet['docking_markers']).read_text())
    marker = next(m for m in layout['markers'] if m['id'] == 42)
    before = copy.deepcopy(marker)
    # 회전 전 북쪽 접근, +90도 차체 회전 후 41번 북쪽 도킹. USD 자산축 기준.
    marker.update(center_m=[.34, window['goal_pose']['position']['x']-initial[0], .081], right=[0, 1, 0],
                  basis='PROVISIONAL_TRIAL: north approach before SEC01 +90deg handoff rotation; not measured hardware')
    fleet['docking_markers'] = write('layout.json', layout)
    write('fleet.json', fleet)
    params = dict(use_sim_time=True, camera_frame_id='transport_01/camera_optical_frame',
        profiles_file=str(ROOT/profile['precision_profiles']), sites_file=str(runtime/'sites.json'),
        pose_control_file=str(runtime/'pickup_targets.json'), pose_control_target='harvest_42_wait_pose',
        log_dir=str(runtime.parent/'precision'), skip_staging=True, cam_auto=False, autostart=False,
        dry_run=False, camera_input_backend='ros', image_topic='camera/image_raw',
        info_topic='camera/camera_info', lidar_topic='scan', marker_pose_mode='tf_observe',
        marker_base_frame='transport_01/base_footprint', odom_frame='transport_01/odom', pose_output_enabled=True)
    write('sites.json', {'sorter':read_source('robot/config/docking/legacy_waffle_sites.yaml')['sorter']}
          if sorter else dict(sites={}))
    (runtime/'precision.yaml').write_text(yaml.safe_dump({'/**': {'ros__parameters': params}}, sort_keys=False))
    # 원본 운송은 그래프 위 목표만 접수한다. 윈도우 측방 오프셋은 시험 입력에서 명시한다.
    goal = copy.deepcopy(window['goal_pose'])
    goal['position']['x'] = initial[0]
    write('pickup_goal.json', goal)
    write('pickup_adaptations.json', dict(source_commit=SOURCE,
        source_workflow=source['pickup_workflow'], selected_workflow=profile['pickup_workflow'],
        source_mechanical_device=source['mechanical_device'],
        original_sim_mechanical_device=original_device_backend,
        selected_mechanical_device=profile['mechanical_device'],
        selected_precision_profiles=list(selected),
        sorter_environment_before=departure_before, sorter_environment_selected=departure,
        numeric_control_changes=[dict(parameter='harvest_approach_42.route_handoff.observation_timeout_s',
            original=observation_before, selected=route_handoff['observation_timeout_s'],
            reason='2026-10-29 user approved sim wall-time observation budget; real source unchanged'),
            dict(parameter='harvest_approach_42.route_handoff.approach_margin_m',
                original=margin_before, selected=route_handoff['approach_margin_m'],
                reason='2026-10-29 user approved 10cm sim handoff headroom; docking envelope unchanged')],
        marker42_before=before, marker42_after=marker,
        original_window_pose=window['goal_pose'], graph_staging_pose=goal,
        frontend_window_pose_contract_unresolved=True, initial_pose_only=True))
