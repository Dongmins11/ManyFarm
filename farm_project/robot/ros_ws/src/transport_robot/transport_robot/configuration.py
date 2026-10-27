"""환경·목적지·기종 설정 검증. 실측 전 설정은 경로 미리보기만 허용한다."""
from pathlib import Path
from typing import Any
import math
import re
from farm_navigation.configuration import read_mapping, resolve_file, load_environment
from farm_navigation.navigation_types import NavigationSettings
from farm_navigation.route import RouteGraph


def load_profile(root: Path, filename: str, mode: str) -> dict[str, Any]:
    if mode not in ('real', 'sim'):
        raise ValueError('mode는 real 또는 sim이어야 합니다.')
    environment = resolve_file(root, filename)
    if not environment.is_relative_to(root) or environment.is_relative_to(root/'sim') != (mode == 'sim'):
        raise ValueError('환경 파일의 real/sim 경로 혼용')
    profile = load_environment(environment, root, mode, require_survey=False)
    return_mode = profile.get('station_return_mode', 'marker_docking')
    if return_mode not in ('marker_docking', 'navigation_only'):
        raise ValueError('알 수 없는 station_return_mode')
    if return_mode == 'navigation_only' and mode != 'sim':
        raise ValueError('마커 없는 스테이션 복귀는 sim에서만 허용합니다.')
    if not re.fullmatch(r'[A-Za-z][A-Za-z0-9_]*', profile['robot_id']):
        raise ValueError('robot_id는 단일 ROS namespace여야 합니다.')
    settings = NavigationSettings.from_mapping(profile['navigation'])
    if profile.get('traffic', {}).get('enabled'):
        raise ValueError('운송 교통 허가 연결 전에는 traffic.enabled를 사용할 수 없습니다.')
    if profile.get('precision_enabled') and (settings.tf_recovery_enabled or settings.collision_retry_count):
        raise ValueError('정밀 도킹의 단일 출력 연결에는 별도 Nav2 정지 publisher를 사용할 수 없습니다.')
    if settings.mode != 'follow_path' or settings.parallel_approach:
        raise ValueError('1차 운송은 기본 그래프 FollowPath만 사용합니다.')
    for key in ('device_config', 'map_yaml', 'nav_params', 'route_graph', 'destinations'):
        path = resolve_file(root, profile[key])
        if not path.is_relative_to(root) or path.is_relative_to(root/'sim') != (mode == 'sim'):
            raise ValueError(f'{key}: 환경/프로젝트 경로 혼용')
        profile[key] = str(path)
    registry = read_mapping(profile['destinations'])
    if registry.get('map_id') != profile['map_id'] or registry.get('mode') != mode:
        raise ValueError('목적지 설정의 지도/환경 불일치')
    profile['registry'] = registry
    device = read_mapping(profile['device_config'])
    if device.get('model') not in ('burger','waffle','waffle_pi','vicpinky'):
        raise ValueError('기존 장치 연결이 지원하는 모델을 지정하세요.')
    profile['device'] = device
    if profile.get('precision_enabled'):
        profile['precision_registry']=read_mapping(resolve_file(root,profile['precision_profiles']))
    if profile.get('pickup_workflow', {}).get('enabled'):
        profile['pickup_targets'] = read_mapping(resolve_file(root, profile['pickup_targets_file']))
    return profile


def require_execution(profile: dict[str, Any]) -> None:
    """외부 브릿지 사용 여부와 무관하게 설정 검증을 생략하지 않는다."""
    if profile.get('execution_enabled') is not True:
        raise ValueError('실측·장치·Nav2 설정 확인 후 execution_enabled를 활성화하세요.')
    if profile['mode'] == 'sim':
        if profile['device'].get('use_sim_time') is not True:
            raise ValueError('sim 장치는 use_sim_time=true가 필요합니다.')
    elif profile['device'].get('hardware_configured') is not True:
        raise ValueError('device hardware_configured가 false입니다.')


def destination(profile: dict[str, Any], graph: RouteGraph, station_id: str) -> tuple[tuple[float,float],float]:
    item = profile['registry']['destinations'].get(station_id)
    if not item or item.get('configured') is not True:
        raise ValueError(f'목적지 매핑/방향 미확정: {station_id}')
    if 'entry_node_id' in item:
        a,b=item['entry_node_id'],item.get('observation_node_id')
        if type(a) is not int or type(b) is not int or a not in graph.nodes or b not in graph.nodes or a==b:
            raise ValueError('진입점/관측점 노드 오류')
        if not any(e.start==a and e.end==b for e in graph.edges):raise ValueError('진입점→관측점 직접 edge 필요')
        direction=profile['precision_registry']['profiles'][item['docking_profile']]['entry']['direction']
        if direction not in ('forward','reverse'):raise ValueError('진입 direction 오류')
        ax,ay=graph.nodes[a];bx,by=graph.nodes[b]
        yaw=item.get('entry_yaw_rad')
        if yaw is None:yaw=math.atan2(by-ay,bx-ax)+(math.pi if direction=='reverse' else 0.)
        if isinstance(yaw,bool) or not isinstance(yaw,(int,float)) or not math.isfinite(yaw):raise ValueError('entry_yaw_rad must be finite or null')
        return graph.nodes[a], math.atan2(math.sin(yaw),math.cos(yaw))
    node = item.get('approach_node_id')
    yaw = item.get('approach_yaw_rad')
    heading_from = item.get('approach_heading_from_node_id')
    if heading_from is not None:
        if heading_from not in graph.nodes or heading_from == node:
            raise ValueError('Invalid approach heading reference')
        a, b = graph.nodes[heading_from], graph.nodes[node]
        yaw = math.atan2(b[1]-a[1], b[0]-a[0])
    if isinstance(node, bool) or node not in graph.nodes:
        raise ValueError('목적지 노드가 현재 그래프에 없습니다.')
    if isinstance(yaw, bool) or not isinstance(yaw,(int,float)) or not math.isfinite(yaw):
        raise ValueError('접근 yaw(rad)를 실측·확정하세요.')
    return graph.nodes[node], float(yaw)


def validate_precision(profile: dict, request_profile: str, target: int = -1, docking: int = -1, *, require_clearance: bool = True) -> None:
    """목적지로 움직이기 전에 정밀주행의 필수 매핑을 검증한다."""
    item=profile.get('precision_registry',{}).get('profiles',{}).get(request_profile,{})
    if not profile.get('precision_enabled') or not item.get('configured') or (require_clearance and not item.get('clearance_corridor_verified')):
        raise ValueError('정밀주행 프로파일/이격 통로 미검증')
    if target>=0 and target!=item.get('target_marker_id'):raise ValueError('대상 마커 역할 매핑 불일치')
    if docking>=0 and docking!=item.get('docking_marker_id'):raise ValueError('도킹 마커 역할 매핑 불일치')


def validate_unload_workflow(profile, station_id):
    workflow = profile.get('unload_workflows', {}).get(station_id, {})
    if not workflow.get('auto_clear'):
        return False
    name = workflow.get('clearance_profile')
    item = profile.get('precision_registry', {}).get('profiles', {}).get(name, {})
    if not item.get('configured') or 'CLEAR' not in item.get('allowed_operations', []):
        raise ValueError('하역 후 CLEAR 프로파일 미설정')
    if item.get('target_marker_id') != workflow.get('marker_id') or item.get('docking_marker_id') != workflow.get('marker_id'):
        raise ValueError('하역 후 CLEAR 마커 불일치')
    if not item.get('clearance_corridor_verified') and not (item.get('bounded_trial') and workflow.get('allow_bounded_clearance_trial') is True):
        raise ValueError('하역 후 이격 프로파일 검증/한정 시험 설정 필요')
    return True
