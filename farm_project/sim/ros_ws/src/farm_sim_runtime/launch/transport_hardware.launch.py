"""운송 가상 장치만 연결한다. 주행/도킹/업무 서버는 별도 단계에서 조립한다."""
from pathlib import Path
import json
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, OpaqueFunction
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def setup(context) -> list:
    root = Path(LaunchConfiguration('project_root').perform(context)).expanduser().resolve()
    config = root / 'sim/ros_ws/src/farm_sim_config/config/transport.json'
    device = json.loads(config.read_text())
    return [Node(package='farm_sim_devices', executable='ros_adapter',
                 namespace=device['robot_id'], output='screen',
                 parameters=[dict(config_file=str(config), use_sim_time=True)])]


def generate_launch_description() -> LaunchDescription:
    return LaunchDescription([DeclareLaunchArgument('project_root'), OpaqueFunction(function=setup)])
