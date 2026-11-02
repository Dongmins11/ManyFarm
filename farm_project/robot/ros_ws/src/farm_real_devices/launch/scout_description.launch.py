"""PC 전용 전체 모델 확인. 하드웨어/카메라/주행 노드는 실행하지 않는다."""
import json
from pathlib import Path
from ament_index_python.packages import get_package_share_directory
from launch import LaunchContext, LaunchDescription
from launch.actions import DeclareLaunchArgument, OpaqueFunction
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue
from farm_real_devices.description import load_description


def show_description(context: LaunchContext) -> list:
    """장치 설정을 사용해 전체 모델의 관절 상태와 TF를 발행한다."""
    share = Path(get_package_share_directory('farm_real_devices'))
    config = json.loads(Path(LaunchConfiguration('config_file').perform(context)).read_text())
    description = load_description(config, share / 'description', full=True)
    return [
        Node(package='robot_state_publisher', executable='robot_state_publisher',
             name='scout_preview_state_publisher',
             parameters=[{'robot_description': ParameterValue(description, value_type=str)}]),
        Node(package='joint_state_publisher', executable='joint_state_publisher',
             name='scout_preview_joint_states'),
    ]


def generate_launch_description() -> LaunchDescription:
    share = Path(get_package_share_directory('farm_real_devices'))
    return LaunchDescription([
        DeclareLaunchArgument('config_file', default_value=str(share / 'config/scout_devices_real.json')),
        OpaqueFunction(function=show_description),
    ])
