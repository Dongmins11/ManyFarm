"""시뮬 전용 조합 실행. Isaac 한 개 + 예찰·수확 bringup + 운송 가상 장치 + 선택 RViz."""
import os
from farm_sim_runtime.launch_environment import default_vision_python
from pathlib import Path
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import (DeclareLaunchArgument, GroupAction, IncludeLaunchDescription,
                            LogInfo, OpaqueFunction, SetEnvironmentVariable)
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration


def setup(context) -> list:
    def value(name: str) -> str:
        return LaunchConfiguration(name).perform(context)

    shared = {name: value(name) for name in ('project_root', 'environment_config')}
    transport = value('transport') == 'true'
    fleet = value('fleet_config')
    if transport and fleet == 'sim/ros_ws/src/farm_sim_config/config/harvest_fleet.json':
        fleet = 'sim/ros_ws/src/farm_sim_config/config/' + (
            'transport_fleet.json' if value('scout') == 'true' or value('harvest') == 'true'
            else 'transport_hardware_fleet.json')
    if transport:
        from farm_sim_runtime.fleet_config import load_fleet
        configs, _ = load_fleet(Path(value('project_root')).resolve(), Path(fleet))
        if 'transport_01' not in {c['robot_id'] for c in configs}:
            raise ValueError('transport=true에는 운송 장치를 포함한 fleet_config가 필요합니다.')
    if (value('harvest') == 'true' or transport) and shared['environment_config'] == 'sim/ros_ws/src/farm_sim_config/config/scout_runtime.yaml':
        shared['environment_config'] = 'sim/ros_ws/src/farm_sim_config/config/scout_fleet_runtime.yaml'
    actions = []
    # 전체 시뮬의 ROS 자식 프로세스에만 적용한다. 호출자/실물 실행 환경은 바꾸지 않는다.
    external_dds = (context.environment.get('FASTRTPS_DEFAULT_PROFILES_FILE')
                    or context.environment.get('FASTDDS_DEFAULT_PROFILES_FILE'))
    if external_dds:
        actions.append(LogInfo(msg='외부 DDS 프로파일 유지(기본 프로파일 자동 선택 생략): ' + external_dds))
    else:
        dds_profile = (Path(value('project_root')).expanduser().resolve()
                       / 'sim/ros_ws/src/farm_sim_config/config/fastdds_discovery.xml')
        if not dds_profile.is_file():
            raise FileNotFoundError(f'시뮬 DDS 수신 버퍼 프로파일이 없습니다: {dds_profile}')
        actions += [SetEnvironmentVariable('FASTRTPS_DEFAULT_PROFILES_FILE', str(dds_profile)),
                    LogInfo(msg='시뮬 DDS 수신 버퍼: 2MiB 요청, 프로파일=' + str(dds_profile))]

    def include(package: str, filename: str, arguments: dict) -> None:
        path = Path(get_package_share_directory(package)) / 'launch' / filename
        actions.append(IncludeLaunchDescription(PythonLaunchDescriptionSource(str(path)),
                                                launch_arguments=arguments.items()))

    if value('isaac') == 'true':
        include('farm_sim_runtime', 'isaac.launch.py', dict(shared, **{
            name: value(name) for name in ('isaac_python', 'assets_root', 'headless', 'physics_device', 'performance_log', 'duration_s')},
            fleet_config=fleet if value('harvest') == 'true' or transport else ''))
    if transport:
        include('farm_sim_runtime', 'transport_hardware.launch.py', dict(project_root=value('project_root')))
    if value('scout') == 'true':
        include('farm_sim_runtime', 'scout.launch.py', dict(shared, start_isaac='false', rviz='false',
            **{name: value(name) for name in ('navigation', 'survey', 'vision_python', 'device', 'headless', 'tag_correction')}))
    if value('rviz') == 'true':
        monitor = dict(shared)
        fleet_view = value('harvest') == 'true' and value('scout') == 'true'
        if value('harvest') == 'true' and value('scout') != 'true':
            monitor['environment_config'] = value('harvest_environment_config')
        include('farm_bringup', 'rviz.launch.py', dict(monitor, mode='sim',
            rviz_config=value('rviz_config') or ('sim/ros_ws/src/farm_sim_config/config/scout_harvest.rviz' if fleet_view else '')))
    if value('harvest') == 'true':
        include('farm_sim_runtime', 'harvest.launch.py', dict(project_root=value('project_root'),
            mode='sim', environment_config=value('harvest_environment_config'),
            tag_correction=value('tag_correction')))
    return [GroupAction(actions=actions, scoped=True)]


def generate_launch_description() -> LaunchDescription:
    boolean = ['true', 'false']
    return LaunchDescription([
        DeclareLaunchArgument('project_root'),
        DeclareLaunchArgument('environment_config', default_value=
                              'sim/ros_ws/src/farm_sim_config/config/scout_runtime.yaml'),
        DeclareLaunchArgument('isaac', default_value='true', choices=boolean),
        DeclareLaunchArgument('scout', default_value='true', choices=boolean),
        DeclareLaunchArgument('harvest', default_value='false', choices=boolean),
        DeclareLaunchArgument('transport', default_value='false', choices=boolean),
        DeclareLaunchArgument('tag_correction', default_value='false', choices=boolean),
        DeclareLaunchArgument('harvest_environment_config', default_value=
                              'sim/ros_ws/src/farm_sim_config/config/harvest_runtime.yaml'),
        DeclareLaunchArgument('fleet_config', default_value=
                              'sim/ros_ws/src/farm_sim_config/config/harvest_fleet.json'),
        DeclareLaunchArgument('rviz', default_value='true', choices=boolean),
        DeclareLaunchArgument('navigation', default_value='true', choices=boolean),
        DeclareLaunchArgument('survey', default_value='true', choices=boolean),
        DeclareLaunchArgument('isaac_python', default_value=os.environ.get('FARM_ISAAC_PYTHON', '')),
        DeclareLaunchArgument('vision_python', default_value=default_vision_python()),
        DeclareLaunchArgument('assets_root', default_value=''),
        DeclareLaunchArgument('rviz_config', default_value=''),
        DeclareLaunchArgument('headless', default_value='false', choices=boolean),
        DeclareLaunchArgument('physics_device', default_value='profile', choices=['profile', 'cpu', 'gpu']),
        DeclareLaunchArgument('performance_log', default_value=''),
        DeclareLaunchArgument('duration_s', default_value=''),
        DeclareLaunchArgument('device', default_value='0'),
        OpaqueFunction(function=setup),
    ])
