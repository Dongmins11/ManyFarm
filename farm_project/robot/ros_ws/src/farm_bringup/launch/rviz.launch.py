"""모니터링만 실행합니다. 로봇 장치·주행·업무 서버를 시작하지 않습니다."""
from pathlib import Path
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, OpaqueFunction
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from farm_navigation.configuration import read_mapping, resolve_file


def setup(context) -> list:
    def value(name: str) -> str:
        return LaunchConfiguration(name).perform(context)

    root = Path(value('project_root')).expanduser().resolve()
    mode = value('mode')
    environment = resolve_file(root, value('environment_config'))
    profile = read_mapping(environment)
    if profile['mode'] != mode:
        raise ValueError('RViz mode와 환경 설정이 다릅니다.')
    selected = value('rviz_config') or profile.get('rviz_config')
    if selected:
        config = resolve_file(root, selected)
    elif mode == 'real':
        config = Path(get_package_share_directory('scout_robot')) / 'config/scout.rviz'
    else:
        raise ValueError('시뮬 환경에 rviz_config를 지정하세요.')
    if not config.is_file():
        raise FileNotFoundError(config)
    if mode == 'sim' and (not environment.is_relative_to(root / 'sim')
                          or not config.resolve().is_relative_to(root / 'sim')):
        raise ValueError('시뮬 환경/RViz 설정은 sim 안에 있어야 합니다.')
    robot_id = profile['robot_id']
    remaps = [('/initialpose', f'/{robot_id}/initialpose')]
    if mode == 'real':
        remaps += [('/tf', f'/{robot_id}/tf'), ('/tf_static', f'/{robot_id}/tf_static')]
    return [Node(package='rviz2', executable='rviz2', name='farm_rviz', output='screen',
                 arguments=['-d', str(config)], parameters=[{'use_sim_time': mode == 'sim'}],
                 remappings=remaps)]


def generate_launch_description() -> LaunchDescription:
    return LaunchDescription([
        DeclareLaunchArgument('project_root'),
        DeclareLaunchArgument('mode', choices=['sim', 'real']),
        DeclareLaunchArgument('environment_config', description='모니터링할 환경 프로파일'),
        DeclareLaunchArgument('rviz_config', default_value=''),
        OpaqueFunction(function=setup),
    ])
