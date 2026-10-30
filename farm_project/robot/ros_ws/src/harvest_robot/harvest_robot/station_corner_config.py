"""실물 복귀 전용 서버 설정. 원본 Nav2·인계 서버 설정을 변경하지 않는다."""
from dataclasses import replace
import math
from farm_navigation.arc_isolation import isolated_parameters
from farm_navigation.navigation_types import NavigationSettings
from farm_navigation.transfer_arc import ArcSpec
from .handoff_server_config import flatten
from .transfer_retreat import retreat_profile, alignment_parameters


def server_config(nav: dict, robot_id: str) -> dict:
    """기존 costmap과 후진 플러그인 설정을 독립 namespace에 조립한다."""
    prefix = '/' + robot_id + '/station_corner'
    controller = flatten(nav['controller_server']['ros__parameters'])
    costmap = flatten(nav['local_costmap']['local_costmap']['ros__parameters'])
    values = isolated_parameters(controller, costmap, prefix,
                                 '/'+robot_id+'/scan_filtered', '/'+robot_id+'/odom')
    server = values[prefix+'/controller_server']['ros__parameters']
    # 전진 코너 기록 약 0.054m/s를 참고한 실물 복귀 전용 값이다. 인계 기본값은 유지한다.
    server.update({'TransferArc.desired_linear_vel': .05,
                   'TransferArc.arc_max_linear_vel': .05,
                   'TransferArc.arc_max_angular_vel': .30})
    server['controller_plugins'].append('StationReverse')
    server.update({key: value for key, value in controller.items() if key.startswith('StationReverse.')})
    if 'StationReverse.plugin' not in server:
        raise ValueError('기존 StationReverse 설정이 필요합니다.')
    # 긴 접근은 기존 속도를 유지하되 종점에서는 기존 이탈 최저속도로 감속한다.
    retreat = retreat_profile(nav['controller_server']['ros__parameters']['StationReverse'])['Retreat']
    for key in ('min_approach_linear_velocity', 'regulated_linear_scaling_min_speed'):
        server['StationReverse.'+key] = retreat[key]
    server['StationReverse.skip_position_approach_rotation'] = True
    # 전진 HarvestWork 설정을 읽어 복귀 접근 인스턴스에만 연결한다. 원본은 수정하지 않는다.
    server['StationReverse.use_work_curvature'] = True
    for key in ('use_fixed_curvature_lookahead', 'curvature_lookahead_dist',
                'interpolate_curvature_after_goal'):
        server['StationReverse.'+key] = controller['HarvestWork.'+key]
    # 위치 완료 후 정지하고 별도 Spin으로 방향을 맞춘다. 최종 스테이션 판정은 불변이다.
    server['goal_checker_plugins'].append('approach_position_goal')
    server.update({'approach_position_goal.plugin': 'nav2_controller::SimpleGoalChecker',
        'approach_position_goal.stateful': False,
        'approach_position_goal.xy_goal_tolerance': controller['general_goal_checker.xy_goal_tolerance'],
        'approach_position_goal.yaw_goal_tolerance': math.pi})
    values[prefix+'/behavior_server'] = {'ros__parameters': alignment_parameters(
        prefix, costmap['robot_base_frame'], use_sim_time=costmap.get('use_sim_time', False))}
    # 전체 costmap 메시지만 읽으므로 변경 셀 누락 없이 최신 지도를 검사한다.
    values[prefix+'/local_costmap/local_costmap']['ros__parameters']['always_send_full_costmap'] = True
    return values


def navigation_settings(settings: NavigationSettings, robot_id: str, *, arc: bool) -> NavigationSettings:
    """코너 진입/원호에만 기존 원호 goal/progress checker를 선택한다."""
    prefix = '/' + robot_id + '/station_corner'
    limits = ArcSpec()
    return replace(settings, mode='follow_path', parallel_approach=False,
        map_frame='odom' if arc else settings.map_frame,
        follow_action=prefix+'/follow_path', controller_node=prefix+'/controller_server',
        controller_id='TransferArc' if arc else 'StationReverse',
        goal_checker_id='transfer_arc_goal' if arc else 'approach_position_goal',
        progress_checker_id='transfer_arc_progress',
        arrival_tolerance_m=limits.endpoint_tolerance if arc else settings.arrival_tolerance_m,
        heading_tolerance_rad=limits.yaw_tolerance if arc else math.tau)
