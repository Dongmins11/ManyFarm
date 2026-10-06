"""시뮬 전용 조합 실행. Isaac 한 개 + 예찰·수확 bringup + 선택 RViz."""
import os
from farm_sim_runtime.launch_environment import default_vision_python
from pathlib import Path
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription, OpaqueFunction
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration


def setup(context) -> list:
    def value(name: str) -> str:
        return LaunchConfiguration(name).perform(context)

    shared = {name: value(name) for name in ('project_root', 'environment_config')}
    if value('harvest') == 'true' and shared['environment_config'] == 'sim/ros_ws/src/farm_sim_config/config/scout_runtime.yaml':
        shared['environment_config'] = 'sim/ros_ws/src/farm_sim_config/config/scout_fleet_runtime.yaml'
    actions = []

    def include(package: str, filename: str, arguments: dict) -> None:
        path = Path(get_package_share_directory(package)) / 'launch' / filename
        actions.append(IncludeLaunchDescription(PythonLaunchDescriptionSource(str(path)),
                                                launch_arguments=arguments.items()))

    if value('isaac') == 'true':
        include('farm_sim_runtime', 'isaac.launch.py', dict(shared, **{
            name: value(name) for name in ('isaac_python', 'assets_root', 'headless')},
            fleet_config=value('fleet_config') if value('harvest') == 'true' else ''))
    if value('scout') == 'true':
        include('farm_sim_runtime', 'scout.launch.py', dict(shared, start_isaac='false', rviz='false',
            **{name: value(name) for name in ('navigation', 'survey', 'vision_python', 'device', 'headless')}))
    if value('rviz') == 'true':
        monitor = dict(shared)
        fleet_view = value('harvest') == 'true' and value('scout') == 'true'
        if value('harvest') == 'true' and value('scout') != 'true':
            monitor['environment_config'] = value('harvest_environment_config')
        include('farm_bringup', 'rviz.launch.py', dict(monitor, mode='sim',
            rviz_config=value('rviz_config') or ('sim/ros_ws/src/farm_sim_config/config/scout_harvest.rviz' if fleet_view else '')))
    if value('harvest') == 'true':
        include('farm_sim_runtime', 'harvest.launch.py', dict(project_root=value('project_root'),
            mode='sim', environment_config=value('harvest_environment_config')))
    return actions


def generate_launch_description() -> LaunchDescription:
    boolean = ['true', 'false']
    return LaunchDescription([
        DeclareLaunchArgument('project_root'),
        DeclareLaunchArgument('environment_config', default_value=
                              'sim/ros_ws/src/farm_sim_config/config/scout_runtime.yaml'),
        DeclareLaunchArgument('isaac', default_value='true', choices=boolean),
        DeclareLaunchArgument('scout', default_value='true', choices=boolean),
        DeclareLaunchArgument('harvest', default_value='false', choices=boolean),
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
        DeclareLaunchArgument('device', default_value='0'),
        OpaqueFunction(function=setup),
    ])
