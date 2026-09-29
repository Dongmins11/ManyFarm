"""Explicit motion entry point. Running this launch starts the selected route."""
from pathlib import Path
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, OpaqueFunction, EmitEvent
from launch.substitutions import LaunchConfiguration
from launch.events import Shutdown
from launch_ros.actions import Node


def setup(context):
    sim = LaunchConfiguration('mode').perform(context) == 'sim'
    path = LaunchConfiguration('route_file').perform(context)
    if not path and sim:
        path = str(Path(get_package_share_directory('farm_sim_config')) / 'maps/graph.geojson')
    if not path or not Path(path).is_file():
        raise RuntimeError('route_file에 사용할 GeoJSON 파일을 지정하세요.')
    ids = [int(x) for x in LaunchConfiguration('node_ids').perform(context).split(',')]
    return [Node(package='scout_robot', executable='drive_route', namespace='scout_01',
        output='screen', sigterm_timeout='20', sigkill_timeout='20',
        on_exit=[EmitEvent(event=Shutdown(reason='경로 주행 프로그램 종료'))],
        parameters=[{'use_sim_time': sim, 'route_file': str(Path(path).absolute()),
                     'node_ids': ids,
                     'goal_timeout_s': float(LaunchConfiguration('goal_timeout_s').perform(context))}])]


def generate_launch_description():
    return LaunchDescription([
        DeclareLaunchArgument('mode', default_value='sim', choices=['sim', 'real']),
        DeclareLaunchArgument('route_file', default_value=''),
        DeclareLaunchArgument('node_ids', default_value='1,2,3,4,5,6,7,8'),
        DeclareLaunchArgument('goal_timeout_s', default_value='300.0'),
        OpaqueFunction(function=setup),
    ])
