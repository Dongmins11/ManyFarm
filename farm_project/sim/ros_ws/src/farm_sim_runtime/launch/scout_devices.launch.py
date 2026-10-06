"""시뮬 로봇 한 대의 ROS 장치 어댑터만 실행합니다. Isaac은 독립 프로세스입니다."""
import json
from pathlib import Path
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, OpaqueFunction, RegisterEventHandler, EmitEvent
from launch.event_handlers import OnProcessExit
from launch.events import Shutdown
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def setup(context) -> list:
    def value(name: str) -> str:
        return LaunchConfiguration(name).perform(context)
    if value('start_isaac') == 'true':
        raise RuntimeError('Isaac은 farm_sim_runtime isaac.launch.py로 별도 실행하세요.')
    config = (Path(value('config_file')).expanduser() if value('config_file') else
              Path(get_package_share_directory('farm_sim_config')) / 'config/scout.json')
    cfg = json.loads(config.read_text())
    adapter = Node(package='farm_sim_devices', executable='ros_adapter', namespace=cfg['robot_id'],
                   parameters=[{'config_file': str(config), 'cmd_vel_type': value('cmd_vel_type'),
                                'use_sim_time': True}], output='screen')
    return [RegisterEventHandler(OnProcessExit(target_action=adapter,
            on_exit=[EmitEvent(event=Shutdown(reason='ROS 장치 연결 종료'))])), adapter]


def generate_launch_description() -> LaunchDescription:
    return LaunchDescription([
        DeclareLaunchArgument('config_file', default_value=''),
        DeclareLaunchArgument('start_isaac', default_value='false', choices=['true', 'false']),
        DeclareLaunchArgument('cmd_vel_type', default_value='twist', choices=['twist', 'twist_stamped']),
        OpaqueFunction(function=setup),
    ])
