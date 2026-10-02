"""실물 장치만 실행합니다. Nav2·미션·카메라는 여기서 중복 실행하지 않습니다."""
import json
import os
from pathlib import Path
import tempfile
import re
from ament_index_python.packages import get_package_share_directory
from launch import LaunchContext, LaunchDescription
from launch.actions import (DeclareLaunchArgument, GroupAction, IncludeLaunchDescription,
                            OpaqueFunction, RegisterEventHandler, SetEnvironmentVariable)
from launch.event_handlers import OnShutdown
from launch.launch_description_sources import PythonLaunchDescriptionSource, AnyLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import PushRosNamespace, SetRemap, Node


def start_devices(context: LaunchContext) -> list:
    """기존 미니관제의 하드웨어 bringup을 재사용합니다."""
    config = json.loads(Path(LaunchConfiguration('config_file').perform(context)).read_text())
    model = config['model']
    robot_id = config['robot_id']
    velocity_type = LaunchConfiguration('cmd_vel_type').perform(context)
    if model not in ('burger', 'waffle', 'waffle_pi', 'vicpinky'):
        raise ValueError(f'지원하지 않는 실물 모델: {model}')
    if not isinstance(robot_id, str) or not robot_id.strip():
        raise ValueError('robot_id가 필요합니다.')
    actions = [PushRosNamespace(robot_id)]
    # 기존 드라이버의 절대 토픽도 로봇 namespace 안으로 모읍니다.
    for topic in ('tf', 'tf_static', 'odom', 'scan', 'scan_filtered', 'cmd_vel', 'joint_states'):
        actions.append(SetRemap(src='/' + topic, dst=topic))
    if model == 'vicpinky':
        if velocity_type != 'twist':
            raise ValueError('기존 vicpinky 연결은 cmd_vel_type:=twist를 사용합니다.')
        launch = Path(get_package_share_directory('vicpinky_bringup')) / 'launch/bringup.launch.xml'
        actions.append(IncludeLaunchDescription(AnyLaunchDescriptionSource(str(launch)),
                       launch_arguments={'use_sim_time': 'false'}.items()))
    else:
        share = Path(get_package_share_directory('turtlebot3_bringup'))
        parameter_dir = share / 'param'
        if os.environ.get('ROS_DISTRO') == 'humble':
            parameter_dir /= 'humble'
        parameters = (parameter_dir / (model + '.yaml')).read_text()
        # 모터·바퀴 보정값은 원본을 유지하고 속도 메시지 형식만 상위 런치와 맞춥니다.
        parameters, count = re.subn(r'(enable_stamped_cmd_vel:\s*)(true|false)',
                                    lambda match: match[1] + ('true' if velocity_type == 'twist_stamped' else 'false'), parameters)
        if count != 1:
            raise ValueError('기존 드라이버의 enable_stamped_cmd_vel 설정을 확인하세요.')
        with tempfile.NamedTemporaryFile(mode='w', prefix='farm_base_', suffix='.yaml', delete=False) as output:
            output.write(parameters)
            parameter_file = Path(output.name)
        def cleanup(context: LaunchContext) -> list:
            parameter_file.unlink(missing_ok=True)
            return []
        actions.extend([
            RegisterEventHandler(OnShutdown(on_shutdown=[OpaqueFunction(function=cleanup)])),
            SetEnvironmentVariable('TURTLEBOT3_MODEL', model),
            SetEnvironmentVariable('LDS_MODEL', config['lds_model']),
            IncludeLaunchDescription(PythonLaunchDescriptionSource(str(share / 'launch/robot.launch.py')),
                launch_arguments={'namespace': '', 'use_sim_time': 'false',
                                  'usb_port': config['usb_port'], 'tb3_param_dir': str(parameter_file)}.items())])
    mount=config.get('camera_mount')
    if mount:
        # 기존 run_camera_mount.sh 값을 재사용합니다. 같은 TF를 별도로 실행하지 않습니다.
        def fixed(parent: str, child: str, xyz: list, rpy: list) -> Node:
            args=['--frame-id',parent,'--child-frame-id',child]
            for key,value in zip(('x','y','z','roll','pitch','yaw'),[*xyz,*rpy]):args.extend(['--'+key,str(value)])
            return Node(package='tf2_ros',executable='static_transform_publisher',arguments=args,output='screen')
        actions.append(fixed(mount['parent_frame'],mount['link_frame'],mount['xyz_m'],mount['rpy_rad']))
        actions.append(fixed(mount['link_frame'],mount['optical_frame'],[0,0,0],mount['optical_rpy_rad']))
    return [GroupAction(actions=actions)]


def generate_launch_description() -> LaunchDescription:
    default = Path(get_package_share_directory('farm_real_devices')) / 'config/scout_devices_real.json'
    return LaunchDescription([
        DeclareLaunchArgument('config_file', default_value=str(default)),
        DeclareLaunchArgument('cmd_vel_type', default_value='twist', choices=['twist', 'twist_stamped']),
        OpaqueFunction(function=start_devices)])
