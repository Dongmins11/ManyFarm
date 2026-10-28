"""시뮬 수확 장치·Nav2·공통 수확 서버와 선택적 영상 태그 보정을 조립한다."""
import json
import math
from pathlib import Path
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription, OpaqueFunction
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from farm_navigation.configuration import load_environment, load_nav2_parameters, read_mapping
from farm_sim_runtime.tag_localization import tag_capture_actions
from farm_sim_runtime.fleet_config import validate_harvest_action


def setup(context) -> list:
    def value(key: str) -> str:
        return LaunchConfiguration(key).perform(context)
    mode = value('mode')
    if mode != 'sim':
        raise RuntimeError('수확 real 장치 연결은 미구현입니다. 실물 담당자 인수 후 연결하세요. 가상 장치로 대체하지 않습니다.')
    root = Path(value('project_root')).expanduser().resolve()
    env = (root / value('environment_config')).resolve()
    profile = load_environment(env, root, mode, require_survey=False)
    for path in [env, *[Path(profile[k]) for k in ('device_config','nav_params','route_graph','map_yaml')],
                 (root / profile['harvest_config']).resolve()]:
        if not path.resolve().is_relative_to(root / 'sim'):
            raise ValueError('수확 시뮬 설정은 sim 안에 있어야 합니다.')
    # 시험 초기 배치와 작업 종료 후 돌아갈 스테이션은 별도다.
    spawn_file = value('initial_spawn_config') or profile['station_config']
    station = json.loads((root / spawn_file).read_text())['stations'][profile['robot_id']]
    initial = load_nav2_parameters(profile['nav_params'], root)['amcl']['ros__parameters']
    pose = initial['initial_pose']
    device = json.loads(Path(profile['device_config']).read_text())
    task = read_mapping(root / profile['harvest_config'])
    if task.get('completion_policy') == 'ARRIVAL_THEN_ARM':
        physics = read_mapping(root / device['runtime']['robotarm_physics_config'])
        validate_harvest_action(task, device, physics)
    if (device['robot_id'] != profile['robot_id'] or device['map_id'] != profile['map_id']
            or not initial.get('set_initial_pose')
            or math.dist([pose['x'], pose['y']], station['xy_m']) > 1e-6
            or abs(math.remainder(pose['yaw'] - station['yaw_rad'], 2*math.pi)) > 1e-6):
        raise ValueError('수확 장치/AMCL/station 설정이 다릅니다. sim/tools/rebuild_route_data.py를 실행하세요.')
    def include(package: str, file: str, args: dict):
        path = Path(get_package_share_directory(package)) / 'launch' / file
        return IncludeLaunchDescription(PythonLaunchDescriptionSource(str(path)), launch_arguments=args.items())
    actions = []
    capture = ''
    if value('tag_correction') == 'true':
        actions, capture = tag_capture_actions(root, profile)
    actions += [include('farm_bringup', 'harvest.launch.py',
                    dict(project_root=str(root), mode=mode, environment_config=str(env),
                         handoff_config=value('handoff_config'),
                         tag_correction=value('tag_correction'), tag_camera='false', capture_directory=capture))]
    # 인계 시험은 기존 runner의 별도 계측을 유지한다. 일반 수확 audit은 그대로다.
    if not value('handoff_config'):
        actions.append(Node(package='farm_sim_harvest', executable='harvest_audit', namespace=profile['robot_id'],
                 output='screen', parameters=[dict(project_root=str(root),
                     audit_config=str(env.parent / 'harvest_audit.json'), use_sim_time=True)]))
    return actions



def generate_launch_description() -> LaunchDescription:
    return LaunchDescription([
        DeclareLaunchArgument('project_root'),
        DeclareLaunchArgument('handoff_config', default_value=''),
        DeclareLaunchArgument('initial_spawn_config', default_value=''),
        DeclareLaunchArgument('mode', default_value='sim', choices=['sim','real']),
        DeclareLaunchArgument('environment_config', default_value=
                              'sim/ros_ws/src/farm_sim_config/config/harvest_runtime.yaml'),
        DeclareLaunchArgument('tag_correction', default_value='false', choices=['true', 'false']),
        OpaqueFunction(function=setup)])
