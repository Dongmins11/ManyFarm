import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch_ros.actions import Node


def generate_launch_description():
    cfg = os.path.join(get_package_share_directory('transport_device_bridge'),
                       'config', 'device_bridge.yaml')
    return LaunchDescription([
        Node(
            package='transport_device_bridge',
            executable='device_bridge',
            name='device_bridge',
            parameters=[cfg],
            output='screen',
        ),
    ])
