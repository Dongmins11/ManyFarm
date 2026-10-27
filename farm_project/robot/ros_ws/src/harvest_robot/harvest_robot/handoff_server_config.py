"""기존 주행 파라미터로 영구 인계 서버 구성을 만든다. 원본은 수정하지 않는다."""
from copy import deepcopy
import math
from dataclasses import asdict, replace
from farm_navigation.arc_isolation import isolated_parameters
from farm_navigation.wall_trial_support import isolated_parameters as wall_parameters
from farm_navigation.navigation_types import NavigationSettings
from .transfer_retreat import retreat_profile, alignment_parameters


def flatten(values: dict, prefix: str = '') -> dict:
    output = {}
    for name, value in values.items():
        key = prefix + name
        if isinstance(value, dict):
            output.update(flatten(value, key + '.'))
        else:
            output[key] = value
    return output


def build_server_config(nav: dict, robot_id: str, wall: dict,
                        settings: NavigationSettings, use_sim_time: bool,
                        *, footprint_padding: float | None = None) -> dict:
    prefix = '/' + robot_id + '/handoff'
    root = '/' + robot_id
    cp = flatten(nav['controller_server']['ros__parameters'])
    cm = flatten(nav['local_costmap']['local_costmap']['ros__parameters'])
    # 인계 전용 복사본에만 적용한다. 일반 주행 원본과 실행 중 설정은 수정하지 않는다.
    if footprint_padding is not None:
        if (isinstance(footprint_padding, bool)
                or not isinstance(footprint_padding, (int, float))
                or not math.isfinite(footprint_padding) or footprint_padding < 0):
            raise ValueError('인계 footprint padding은 유한한 0 이상의 m 값이어야 합니다.')
        cm['footprint_padding'] = float(footprint_padding)
    cm['use_sim_time'] = cp['use_sim_time'] = use_sim_time
    scan, odom = root + '/scan_filtered', root + '/odom'
    values = isolated_parameters(cp, cm, prefix, scan, odom)
    server = values[prefix + '/controller_server']['ros__parameters']
    wp = wall_parameters(cp, cm, prefix, scan, odom, wall)[prefix + '/controller_server']['ros__parameters']
    for name, value in wp.items():
        if name.startswith(('WallAlign.', 'wall_goal.', 'wall_progress.', 'wall_alignment.')):
            server[name] = value
    station = nav['controller_server']['ros__parameters']['StationReverse']
    for plugin, fields in retreat_profile(station).items():
        server.update({plugin + '.' + key: value for key, value in fields.items()})
    # 원본 StationReverse는 그대로 두고 전진 보정 전용 인스턴스를 등록한다.
    correction = dict(retreat_profile(station)['Retreat'])
    correction.update(plugin='farm_nav2_controller::SettlingRegulatedPurePursuitController',
        allow_reversing=False, use_rotate_to_heading=False)
    server.update({'WindowCorrection.'+k: v for k, v in correction.items()})
    server.update({'window_goal.plugin': 'nav2_controller::SimpleGoalChecker',
        'window_goal.stateful': False, 'window_goal.xy_goal_tolerance': .003,
        'window_goal.yaw_goal_tolerance': .03490658503988659,
        'window_progress.plugin': 'nav2_controller::PoseProgressChecker',
        'window_progress.required_movement_radius': .005,
        'window_progress.required_movement_angle': .04,
        'window_progress.movement_time_allowance': 15.0})
    server['controller_plugins'] += ['WallAlign', 'Retreat', 'WindowCorrection']
    server['goal_checker_plugins'] += ['window_goal']
    server['progress_checker_plugins'] += ['window_progress']
    server['goal_checker_plugins'] += ['wall_goal', 'retreat_goal']
    server['progress_checker_plugins'] += ['wall_progress', 'retreat_progress']
    # 작은 실제 속도도 완료 판정기에 전달한다. 기존 일반 서버에는 적용하지 않는다.
    for axis in ('x', 'y', 'theta'):
        server['min_' + axis + '_velocity_threshold'] = 0.0
    for plugin in server['progress_checker_plugins']:
        if server.get(plugin+'.plugin') == 'nav2_controller::PoseProgressChecker':
            server[plugin+'.plugin'] = 'farm_wall_controller::WaitingProgressChecker'
    profiles = {}
    for stage, ids in {
        'departure': ('TransferArc', 'transfer_arc_goal', 'transfer_arc_progress'),
        'wall': ('WallAlign', 'wall_goal', 'wall_progress'),
        'retreat': ('Retreat', 'retreat_goal', 'retreat_progress'),
        'return': ('TransferArc', 'transfer_arc_goal', 'transfer_arc_progress'),
        'window': ('WindowCorrection', 'window_goal', 'window_progress'),
    }.items():
        profiles[stage] = asdict(replace(settings, mode='follow_path', map_frame=cm['global_frame'],
            odom_topic=odom, controller_node=prefix+'/controller_server', follow_action=prefix+'/follow_path',
            controller_id=ids[0], goal_checker_id=ids[1], progress_checker_id=ids[2],
            arrival_tolerance_m=.008, heading_tolerance_rad=.05235987755982989,
            tf_recovery_enabled=False))
    profiles['wall'].update(arrival_tolerance_m=wall['controller']['distance_tolerance'],
                            heading_tolerance_rad=wall['controller']['angle_tolerance'])
    profiles['retreat']['heading_tolerance_rad'] = .2617993877991494
    spin = alignment_parameters(prefix, settings.base_frame, use_sim_time=use_sim_time)
    spin['spin.plugin'] = 'farm_wall_controller::WaitingSpin'
    return dict(prefix=prefix, values=values, spin=spin, costmap=deepcopy(cm),
                profile={'navigation': profiles, 'spin_endpoint': prefix+'/spin'}, scan=scan, odom=odom)
