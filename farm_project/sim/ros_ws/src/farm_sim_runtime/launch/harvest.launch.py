"""수확 장치·Nav2·HarvestTask 서버. 실물 장치 연결은 인수인계 후 구현합니다."""
import json
import math
from pathlib import Path
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription, OpaqueFunction
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from farm_navigation.configuration import load_environment, read_mapping


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
    station = json.loads((env.parent / 'station_spawn.json').read_text())['stations'][profile['robot_id']]
    initial = read_mapping(Path(profile['nav_params']))['amcl']['ros__parameters']
    pose = initial['initial_pose']
    device = json.loads(Path(profile['device_config']).read_text())
    if (device['robot_id'] != profile['robot_id'] or device['map_id'] != profile['map_id']
            or not initial.get('set_initial_pose')
            or math.dist([pose['x'], pose['y']], station['xy_m']) > 1e-6
            or abs(math.remainder(pose['yaw'] - station['yaw_rad'], 2*math.pi)) > 1e-6):
        raise ValueError('수확 장치/AMCL/station 설정이 다릅니다. sim/tools/rebuild_route_data.py를 실행하세요.')
    def include(package: str, file: str, args: dict):
        path = Path(get_package_share_directory(package)) / 'launch' / file
        return IncludeLaunchDescription(PythonLaunchDescriptionSource(str(path)), launch_arguments=args.items())
    return [include('farm_bringup', 'harvest.launch.py',
                    dict(project_root=str(root), mode=mode, environment_config=str(env))),
            Node(package='farm_sim_harvest', executable='harvest_audit', namespace=profile['robot_id'],
                 output='screen', parameters=[dict(project_root=str(root),
                     audit_config=str(env.parent / 'harvest_audit.json'), use_sim_time=True)])]



def generate_launch_description() -> LaunchDescription:
    return LaunchDescription([
        DeclareLaunchArgument('project_root'),
        DeclareLaunchArgument('mode', default_value='sim', choices=['sim','real']),
        DeclareLaunchArgument('environment_config', default_value=
                              'sim/ros_ws/src/farm_sim_config/config/harvest_runtime.yaml'),
        OpaqueFunction(function=setup)])
