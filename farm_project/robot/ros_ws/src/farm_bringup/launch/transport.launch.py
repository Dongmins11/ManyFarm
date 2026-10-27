"""기존 장치·Nav2 launch와 운송 서버 조립. Isaac/RViz는 독립 실행."""
from pathlib import Path
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription, OpaqueFunction
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from transport_robot.configuration import load_profile, require_execution
from farm_bringup.docking_sensors import load_docking_sensors, camera_runtime_options


def setup(context) -> list:
    def value(name: str) -> str:
        return LaunchConfiguration(name).perform(context)
    root = Path(value('project_root')).expanduser().resolve()
    mode = value('mode')
    environment = value('environment_config')
    profile = load_profile(root,environment,mode)
    require_execution(profile)
    def include(package: str, name: str, arguments: dict):
        path = Path(get_package_share_directory(package))/'launch'/name
        return IncludeLaunchDescription(PythonLaunchDescriptionSource(str(path)),launch_arguments=arguments.items())
    actions = []
    if value('devices') == 'true':
        arguments = dict(config_file=profile['device_config'],cmd_vel_type='twist')
        actions.append(include('farm_bringup','transport_devices.launch.py',arguments))
    if value('navigation') == 'true':
        actions.append(include('farm_bringup','transport_navigation.launch.py',dict(mode=mode,
            robot_id=profile['robot_id'],map=profile['map_yaml'],nav_params=profile['nav_params'],
            route_file=profile['route_graph'],rviz='false',
            cmd_vel_output='motion/nav' if profile.get('precision_enabled') else 'cmd_vel')))
    if profile.get('precision_enabled'):
        if profile['device']['model']!='waffle':
            raise ValueError('Burger/빅핑키 정밀주행은 해당 기종 프로파일 검증 후 연결해야 합니다.')
        if value('navigation')!='true':
            raise ValueError('외부 Nav2 속도 우회 방지: 정밀주행 사용 시 navigation=true 필요')
        sensors, sensor_params = load_docking_sensors(root, profile['docking_sensors'])
        for item in profile['precision_registry']['profiles'].values():
            if item.get('base_frame', 'base_footprint') != sensors['base_frame']:
                raise ValueError('도킹 profile과 센서 base_frame 불일치')
        actions.append(Node(package='farm_docking',executable='motion_gate',namespace=profile['robot_id'],output='screen'))
        actions.append(Node(package='farm_docking',executable='precision_server',namespace=profile['robot_id'],output='screen',
            **camera_runtime_options(sensors),
            parameters=[dict(profiles_file=str(root/profile['precision_profiles']),sites_file=str(root/profile['legacy_sites']),
                log_dir=str(root/'runs/precision'),
                teach_file=str(root/'robot/config/docking/calibration/teach_{site}.yaml'),
                lidar_teach_file=str(root/'robot/config/docking/calibration/lidar_{site}.yaml'),
                skip_staging=True,cam_auto=False,autostart=False,dry_run=False,
                **sensor_params)],
            remappings=[('/cmd_vel','motion/precision'),('/odom',sensors['topics']['odom']),('/dock/cmd','precision_legacy_disabled'),
                        ('/dock/state','precision_legacy_state'),('/tf','tf'),('/tf_static','tf_static')]))
    if profile.get('mechanical_device', {}).get('backend') == 'trigger' and value('mechanical_bridge') == 'true':
        cfg = str(Path(get_package_share_directory('transport_device_bridge'))/'config'/'device_bridge.yaml')
        actions.append(Node(package='transport_device_bridge', executable='device_bridge',
            name='device_bridge', output='screen', parameters=[cfg, {'robot_ns': profile['robot_id']}],
            sigterm_timeout='50', sigkill_timeout='5'))
    remaps = [] if mode=='sim' else [('/tf','tf'),('/tf_static','tf_static')]
    actions.append(Node(package='transport_robot',executable='transport_node',namespace=profile['robot_id'],
        output='screen',sigterm_timeout='60',sigkill_timeout='5',remappings=remaps,
        parameters=[dict(project_root=str(root),environment_config=environment,mode=mode,
            use_sim_time=mode=='sim',allow_route_checks=value('allow_route_checks')=='true')]))
    return actions


def generate_launch_description() -> LaunchDescription:
    return LaunchDescription([
        DeclareLaunchArgument('project_root'),
        DeclareLaunchArgument('mode',default_value='real',choices=['real']),
        DeclareLaunchArgument('environment_config',description='기종/환경 설정을 명시한다'),
        DeclareLaunchArgument('devices',default_value='true',choices=['true','false']),
        DeclareLaunchArgument('mechanical_bridge',default_value='true',choices=['true','false'],
            description='Start OpenCR bridge; false only when one external bridge is already running'),
        DeclareLaunchArgument('navigation',default_value='true',choices=['true','false']),
        DeclareLaunchArgument('allow_route_checks',default_value='false',choices=['true','false']),
        OpaqueFunction(function=setup)])
