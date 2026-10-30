"""실물 복귀 원호 시험 조립. 기존 수확 launch는 수정 없이 한 번만 포함한다."""
import atexit
from pathlib import Path
import tempfile
import yaml
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription, OpaqueFunction
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from farm_navigation.configuration import load_environment, load_nav2_parameters, read_mapping, resolve_file
from farm_navigation.transfer_arc import ArcSpec
from harvest_robot.station_corner_config import server_config


def save_parameters(values: dict) -> str:
    """launch 수명 동안만 사용하는 파생 설정을 저장한다. 원본 YAML은 보존한다."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as stream:
        yaml.safe_dump(values, stream, sort_keys=False)
        path = stream.name
    atexit.register(Path(path).unlink, missing_ok=True)
    return path


def setup(context: object) -> list:
    def value(name: str) -> str:
        return LaunchConfiguration(name).perform(context)
    root = Path(value('project_root')).expanduser().resolve()
    environment = resolve_file(root, value('environment_config'))
    profile = load_environment(environment, root, 'real', require_survey=False)
    if environment.is_relative_to(root/'sim') or not value('handoff_config'):
        raise ValueError('실물 프로필과 기존 인계 출력 연결 설정이 필요합니다.')
    radius = ArcSpec(radius=float(value('corner_radius_m'))).radius
    selected = read_mapping(environment)
    selected['station_corner_radius_m'] = radius
    docking_values = None
    docking_file = LaunchConfiguration('docking_config', default='').perform(context)
    if docking_file:
        from harvest_robot.station_docking import load_config, server_config as docking_server_config
        docking_path = resolve_file(root, docking_file)
        docking = load_config(root, str(docking_path))
        selected['station_docking_config'] = str(docking_path)
        docking_values = docking_server_config(load_nav2_parameters(profile['nav_params'], root),
                                                profile['robot_id'], docking)
    environment_file = save_parameters(selected)
    values = server_config(load_nav2_parameters(profile['nav_params'], root), profile['robot_id'])
    server_file = save_parameters(values)
    prefix = '/'+profile['robot_id']+'/station_corner'
    tf = [(topic, '/'+profile['robot_id']+'/'+topic.lstrip('/')) for topic in ('/tf', '/tf_static')]
    common = Path(get_package_share_directory('farm_bringup'))/'launch/harvest.launch.py'
    arguments = {name: value(name) for name in
                 ('project_root', 'handoff_config', 'devices', 'tag_correction', 'tag_camera', 'capture_directory')}
    arguments.update(mode='real', navigation='true', environment_config=environment_file)
    actions = [
        IncludeLaunchDescription(PythonLaunchDescriptionSource(str(common)), launch_arguments=arguments.items()),
        Node(package='nav2_controller', executable='controller_server', name='controller_server',
             namespace=prefix, output='screen', parameters=[server_file],
             remappings=tf+[('cmd_vel', 'raw_nav')]),
        Node(package='nav2_behaviors', executable='behavior_server', name='behavior_server',
             namespace=prefix, output='screen', parameters=[server_file],
             remappings=tf+[('cmd_vel', 'raw_nav')]),
        Node(package='nav2_lifecycle_manager', executable='lifecycle_manager', name='lifecycle_manager',
             namespace=prefix, output='screen', parameters=[dict(use_sim_time=False, autostart=True,
                 node_names=['controller_server', 'behavior_server'], bond_timeout=0.0)])]
    if docking_values is not None:
        docking_prefix = '/'+profile['robot_id']+'/station_docking'
        actions.extend([
            Node(package='nav2_controller', executable='controller_server', name='controller_server',
                 namespace=docking_prefix, output='screen', parameters=[save_parameters(docking_values)],
                 remappings=tf+[('cmd_vel', 'raw_nav')]),
            Node(package='nav2_lifecycle_manager', executable='lifecycle_manager', name='lifecycle_manager',
                 namespace=docking_prefix, output='screen', parameters=[dict(use_sim_time=False,
                 autostart=True, node_names=['controller_server'], bond_timeout=0.0)])])
    return actions


def generate_launch_description() -> LaunchDescription:
    return LaunchDescription([
        DeclareLaunchArgument('project_root'), DeclareLaunchArgument('handoff_config'),
        DeclareLaunchArgument('environment_config', default_value='robot/config/environments/harvest_station_return_jetson_real.yaml'),
        DeclareLaunchArgument('docking_config', default_value=''),
        DeclareLaunchArgument('corner_radius_m', default_value='0.20'),
        DeclareLaunchArgument('devices', default_value='true', choices=['true', 'false']),
        DeclareLaunchArgument('tag_correction', default_value='true', choices=['true', 'false']),
        DeclareLaunchArgument('tag_camera', default_value='auto', choices=['auto', 'true', 'false']),
        DeclareLaunchArgument('capture_directory', default_value=''), OpaqueFunction(function=setup)])
