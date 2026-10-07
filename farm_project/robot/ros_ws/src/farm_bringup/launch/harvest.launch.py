"""공통 수확 bringup. 환경별 장치/지도 선택과 동일한 수확 서버를 조립합니다."""
from pathlib import Path
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription, OpaqueFunction
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from farm_navigation.configuration import load_environment, resolve_file, read_mapping


def setup(context) -> list:
    def value(key: str) -> str:
        return LaunchConfiguration(key).perform(context)
    mode = value('mode')
    root = Path(value('project_root')).expanduser().resolve()
    selected = value('environment_config')
    if not selected:
        selected = ('robot/config/environments/harvest_real.yaml' if mode == 'real' else
                    'sim/ros_ws/src/farm_sim_config/config/harvest_runtime.yaml')
    environment = resolve_file(root, selected)
    profile = load_environment(environment, root, mode, require_survey=False)
    paths = [environment, resolve_file(root, profile['harvest_config'])]
    paths += [Path(profile[key]) for key in ('device_config','map_yaml','nav_params','route_graph')]
    if any(path.is_relative_to(root/'sim') != (mode == 'sim') for path in paths):
        raise ValueError('시뮬 설정은 sim 내부, 실물 설정은 sim 외부에 있어야 합니다.')
    def include(package: str, name: str, arguments: dict):
        path = Path(get_package_share_directory(package))/'launch'/name
        return IncludeLaunchDescription(PythonLaunchDescriptionSource(str(path)), launch_arguments=arguments.items())
    tag_on = value('tag_correction') == 'true'
    # auto는 보정 ON일 때만 검출을 함께 켠다. OFF 비교도 tag_camera:=true 가능.
    camera_mode = value('tag_camera')
    camera_on = camera_mode == 'true' or (camera_mode == 'auto' and tag_on and not value('capture_directory'))
    if camera_on and value('capture_directory'):
        raise ValueError('자동 촬영과 외부 capture_directory를 동시에 지정할 수 없습니다.')
    if camera_on and mode != 'real':
        raise ValueError('실물 USB 카메라 실행은 mode=real 전용입니다. sim은 외부 capture_directory를 사용하세요.')
    capture_config = resolve_file(root, profile['tag_capture_config']) if camera_on else None
    tag_path = None
    if tag_on:
        from farm_tag_localization.runtime import validate_binding
        tag_path = resolve_file(root, profile['tag_localization_config'])
        if tag_path.is_relative_to(root/'sim') != (mode == 'sim'):
            raise ValueError('태그 설정의 sim/real 경로 불일치')
        validate_binding(read_mapping(tag_path), profile, root)
        if not camera_on and not value('capture_directory'):
            raise ValueError('tag_correction=true에는 현재 capture_directory가 필요합니다.')
    tf_remaps = [] if mode == 'sim' else [
        ('/tf', '/' + profile['robot_id'] + '/tf'),
        ('/tf_static', '/' + profile['robot_id'] + '/tf_static')]
    actions = []
    if value('devices') == 'true':
        if mode == 'real':
            actions.append(include('farm_real_devices','scout_devices.launch.py',
                dict(config_file=profile['device_config'],cmd_vel_type='twist')))
        else:
            actions.append(include('farm_sim_runtime','scout_devices.launch.py',
                dict(config_file=profile['device_config'],start_isaac='false',cmd_vel_type='twist')))
    if value('navigation') == 'true':
        actions.append(include('farm_bringup','scout_navigation.launch.py',
            dict(mode=mode,robot_id=profile['robot_id'],map=profile['map_yaml'],nav_params=profile['nav_params'],
                 route_file=profile['route_graph'],rviz='false')))
    harvest_config = read_mapping(resolve_file(root, profile['harvest_config']))
    if value('navigation') == 'true' and harvest_config.get('movement_mode') == 'route_then_pose':
        route_params = resolve_file(root, profile['route_server_params'])
        from launch_ros.descriptions import ParameterFile
        from nav2_common.launch import RewrittenYaml
        parameters = ParameterFile(RewrittenYaml(source_file=str(route_params),
            root_key=profile['robot_id'], param_rewrites={'use_sim_time': 'true' if mode == 'sim' else 'false'},
            convert_types=True), allow_substs=False)
        actions.append(Node(package='nav2_route', executable='route_server', name='route_server',
            namespace=profile['robot_id'], output='screen', remappings=tf_remaps,
            parameters=[parameters, {'graph_filepath': profile['route_graph'],
                'route_frame': profile['navigation'].get('map_frame', 'map'),
                'base_frame': profile['navigation'].get('base_frame', 'base_footprint')}]))
        actions.append(Node(package='nav2_lifecycle_manager', executable='lifecycle_manager',
            name='route_lifecycle_manager', namespace=profile['robot_id'], output='screen',
            parameters=[{'use_sim_time': mode == 'sim', 'autostart': True,
                'node_names': ['route_server'], 'bond_timeout': 10.0}]))
    actions.append(Node(package='harvest_robot',executable='harvest_node',namespace=profile['robot_id'],
        output='screen',sigterm_timeout='60',sigkill_timeout='5',remappings=tf_remaps,parameters=[dict(
            project_root=str(root),environment_config=str(environment),mode=mode,use_sim_time=mode=='sim',
            tag_correction=tag_on)]))
    if camera_on:
        # 캡처 세션이 자기 카메라/검출/어댑터만 소유한다. 실패를 주행 취소에 연결하지 않는다.
        actions.append(Node(package='farm_tag_localization',executable='tag_capture_session',
            output='screen',sigterm_timeout='60',sigkill_timeout='5',arguments=[
                '--project-root',str(root),'--capture-config',str(capture_config),
                '--robot-id',profile['robot_id'],
                *(['--correction-config',str(tag_path)] if tag_on else [])]))
    elif tag_on:
        actions.append(Node(package='farm_tag_localization',executable='tag_amcl_adapter',
            namespace=profile['robot_id'],output='screen',remappings=tf_remaps,parameters=[dict(
                project_root=str(root),config_file=str(tag_path),
                capture_directory=value('capture_directory'),use_sim_time=mode=='sim')]))
    return actions


def generate_launch_description() -> LaunchDescription:
    return LaunchDescription([
        DeclareLaunchArgument('project_root'),
        DeclareLaunchArgument('mode',default_value='real',choices=['sim','real']),
        DeclareLaunchArgument('environment_config',default_value=''),
        DeclareLaunchArgument('devices',default_value='true',choices=['true','false']),
        DeclareLaunchArgument('navigation',default_value='true',choices=['true','false']),
        DeclareLaunchArgument('tag_correction',default_value='false',choices=['true','false']),
        DeclareLaunchArgument('capture_directory',default_value=''),
        DeclareLaunchArgument('tag_camera',default_value='auto',choices=['auto','true','false']),
        OpaqueFunction(function=setup)])
