"""공통 수확 bringup. 환경별 장치/지도 선택과 동일한 수확 서버를 조립합니다."""
from pathlib import Path
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription, OpaqueFunction
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from farm_navigation.configuration import load_environment, resolve_file


def setup(context) -> list:
    def value(key: str) -> str:
        return LaunchConfiguration(key).perform(context)
    mode = value('mode')
    if mode == 'real' and value('devices') == 'true':
        raise RuntimeError('수확 real 장치 연결은 미구현입니다. 외부 실물 드라이버 연결 후 devices:=false와 실물 환경 설정을 지정하세요.')
    root = Path(value('project_root')).expanduser().resolve()
    selected = value('environment_config')
    if not selected:
        if mode == 'real':
            raise ValueError('실물 harvest environment_config를 명시하세요. 시뮬 설정을 대신 사용하지 않습니다.')
        selected = 'sim/ros_ws/src/farm_sim_config/config/harvest_runtime.yaml'
    environment = resolve_file(root, selected)
    profile = load_environment(environment, root, mode, require_survey=False)
    paths = [environment, resolve_file(root, profile['harvest_config'])]
    paths += [Path(profile[key]) for key in ('device_config','map_yaml','nav_params','route_graph')]
    if any(path.is_relative_to(root/'sim') != (mode == 'sim') for path in paths):
        raise ValueError('시뮬 설정은 sim 내부, 실물 설정은 sim 외부에 있어야 합니다.')
    def include(package: str, name: str, arguments: dict):
        path = Path(get_package_share_directory(package))/'launch'/name
        return IncludeLaunchDescription(PythonLaunchDescriptionSource(str(path)), launch_arguments=arguments.items())
    actions = []
    if value('devices') == 'true':
        actions.append(include('farm_sim_runtime','scout_devices.launch.py',
            dict(config_file=profile['device_config'],start_isaac='false',cmd_vel_type='twist')))
    if value('navigation') == 'true':
        actions.append(include('farm_bringup','scout_navigation.launch.py',
            dict(mode=mode,robot_id=profile['robot_id'],map=profile['map_yaml'],nav_params=profile['nav_params'],
                 route_file=profile['route_graph'],rviz='false')))
    actions.append(Node(package='harvest_robot',executable='harvest_node',namespace=profile['robot_id'],
        output='screen',sigterm_timeout='60',sigkill_timeout='5',parameters=[dict(
            project_root=str(root),environment_config=str(environment),mode=mode,use_sim_time=mode=='sim')]))
    return actions


def generate_launch_description() -> LaunchDescription:
    return LaunchDescription([
        DeclareLaunchArgument('project_root'),
        DeclareLaunchArgument('mode',default_value='real',choices=['sim','real']),
        DeclareLaunchArgument('environment_config',default_value=''),
        DeclareLaunchArgument('devices',default_value='true',choices=['true','false']),
        DeclareLaunchArgument('navigation',default_value='true',choices=['true','false']),
        OpaqueFunction(function=setup)])
