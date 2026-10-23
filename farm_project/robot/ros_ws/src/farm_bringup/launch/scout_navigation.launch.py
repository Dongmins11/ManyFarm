"""Common localization/navigation; map and parameters are selected by mode."""
from pathlib import Path
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, OpaqueFunction, LogInfo
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from launch_ros.descriptions import ParameterFile
from nav2_common.launch import RewrittenYaml
from farm_navigation.configuration import load_nav2_parameters, materialize_nav2_parameters


def _bt_xml_parameters(nav_params: str, root: Path | None = None) -> dict[str, str]:
    """선택한 Nav2 설정 옆의 상대 BT 경로를 실행 위치와 무관하게 해석합니다."""
    parameters = load_nav2_parameters(nav_params, root).get('bt_navigator', {}).get('ros__parameters', {})
    result = {}
    for key in ('default_nav_to_pose_bt_xml', 'default_nav_through_poses_bt_xml'):
        value = parameters.get(key)
        # 미지정/빈 경로는 기존 Nav2 기본 BT 선택을 그대로 사용한다.
        if value is None or value == '':
            continue
        result[key] = value
    return result


def setup(context):
    value = lambda name: LaunchConfiguration(name).perform(context)
    sim = value('mode') == 'sim'
    config = Path(get_package_share_directory('farm_sim_config')) if sim else None
    selected = {}
    for name, relative in [('map', 'maps/farm_map.yaml'),
                           ('nav_params', 'config/nav2_scout.yaml'),
                           ('route_file', 'maps/graph.geojson')]:
        path = Path(value(name)) if value(name) else (config / relative if sim else None)
        if path is None or not path.is_file():
            raise RuntimeError(f'{name}: 실제 존재하는 파일을 지정하세요. real 설정은 아직 준비되지 않았습니다.')
        selected[name] = str(path.absolute())
    # 프레임 이름은 유지하고 실물 TF·센서 토픽을 장치 namespace에 연결합니다.
    namespace = value('robot_id')
    root = Path(LaunchConfiguration('project_root', default=str(Path.cwd())).perform(context)).expanduser().resolve()
    bt_xml = _bt_xml_parameters(selected['nav_params'], root)
    params = ParameterFile(RewrittenYaml(
        source_file=materialize_nav2_parameters(selected['nav_params'], root), root_key=namespace,
        param_rewrites={'use_sim_time': 'true' if sim else 'false'},
        convert_types=True), allow_substs=False)
    tag_sync = value('tag_scan_sync') == 'true'
    if tag_sync and not value('tag_map_id'):
        raise ValueError('시각 동기 AMCL에는 선택한 환경의 map_id가 필요합니다.')
    servers = [
        ('nav2_map_server', 'map_server'), ('farm_tag_amcl' if tag_sync else 'nav2_amcl', 'amcl'),
        ('nav2_controller', 'controller_server'), ('nav2_planner', 'planner_server'),
        ('nav2_behaviors', 'behavior_server'), ('nav2_bt_navigator', 'bt_navigator'),
        ('nav2_velocity_smoother', 'velocity_smoother'),
    ]
    actions = [LogInfo(msg='Scout Nav2 설정 파일: '+selected['nav_params'])]
    for package, name in servers:
        extra = [{'yaml_filename': selected['map']}] if name == 'map_server' else []
        if name == 'amcl' and tag_sync:
            extra = [{'tag_robot_id': namespace, 'tag_map_id': value('tag_map_id')}]
        elif name == 'bt_navigator' and bt_xml:
            extra = [bt_xml]
        remaps = []
        if name in ('controller_server', 'behavior_server'):
            remaps = [('cmd_vel', value('controller_output'))]
        elif name == 'velocity_smoother':
            remaps = [('cmd_vel', 'cmd_vel_nav'), ('cmd_vel_smoothed', 'cmd_vel')]
        if not sim:
            remaps += [('/'+topic, '/'+namespace+'/'+topic)
                       for topic in ('tf', 'tf_static', 'scan', 'scan_filtered', 'odom', 'map')]
        actions.append(Node(package=package, executable=name, name=name,
                            namespace=namespace, output='screen',
                            parameters=[params, *extra], remappings=remaps))
    actions.append(Node(package='nav2_lifecycle_manager', executable='lifecycle_manager',
        name='lifecycle_manager_navigation', namespace=namespace, output='screen',
        parameters=[{'use_sim_time': sim, 'autostart': True,
                     'node_names': [name for _, name in servers], 'bond_timeout': 10.0}]))
    actions.append(Node(package='scout_robot', executable='route_preview',
        namespace=namespace, output='screen',
        parameters=[{'use_sim_time': sim, 'route_file': selected['route_file']}]))
    if value('rviz') == 'true':
        rviz = Path(get_package_share_directory('scout_robot')) / 'config/scout.rviz'
        actions.append(Node(package='rviz2', executable='rviz2', name='scout_rviz',
            output='screen', arguments=['-d', str(rviz)],
            parameters=[{'use_sim_time': sim}],
            remappings=[('/initialpose', f'/{namespace}/initialpose')]))
    return actions


def generate_launch_description():
    return LaunchDescription([
        DeclareLaunchArgument('controller_output', default_value='cmd_vel_nav'),
        DeclareLaunchArgument('robot_id', default_value='scout_01'),
        DeclareLaunchArgument('project_root', default_value=str(Path.cwd())),
        DeclareLaunchArgument('mode', default_value='sim', choices=['sim', 'real']),
        DeclareLaunchArgument('map', default_value=''),
        DeclareLaunchArgument('nav_params', default_value=''),
        DeclareLaunchArgument('route_file', default_value=''),
        DeclareLaunchArgument('tag_scan_sync', default_value='false', choices=['true', 'false']),
        DeclareLaunchArgument('tag_map_id', default_value=''),
        DeclareLaunchArgument('rviz', default_value='false', choices=['true', 'false']),
        OpaqueFunction(function=setup),
    ])
