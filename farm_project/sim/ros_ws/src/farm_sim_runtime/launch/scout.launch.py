"""시뮬 전용 실행 설정. 장치·업무·주행만 실행하며 Isaac/RViz는 별도 launch가 담당합니다."""
import os
from farm_sim_runtime.launch_environment import default_vision_python
from pathlib import Path

from ament_index_python.packages import get_package_share_directory
from launch import LaunchContext, LaunchDescription
from launch.action import Action
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription, OpaqueFunction
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from farm_navigation.configuration import load_environment, load_nav2_parameters, read_mapping
from farm_sim_runtime.tag_localization import tag_capture_actions


def _sim_file(root: Path, value: str) -> Path:
    """프로젝트 sim 안의 실제 설정 파일만 허용합니다. 외부를 가리키는 링크도 거절합니다."""
    path = Path(value).expanduser()
    path = (path if path.is_absolute() else root / path).resolve()
    if not path.is_relative_to((root / 'sim').resolve()):
        raise RuntimeError(f'시뮬 설정은 프로젝트 sim 안에 있어야 합니다: {path}')
    if not path.is_file():
        raise FileNotFoundError(f'시뮬 설정 파일이 없습니다: {path}')
    return path


def setup(context: LaunchContext) -> list[Action]:
    """시뮬 설정을 확인한 뒤 공통 로봇 bringup 요청만 반환합니다."""
    def value(name: str) -> str:
        return LaunchConfiguration(name).perform(context)

    if value('start_isaac') == 'true' or value('rviz') == 'true':
        raise RuntimeError('Isaac/RViz는 별도 실행합니다. 한 번에 켜려면 farm_sim_runtime all.launch.py를 사용하세요.')
    root = Path(value('project_root')).expanduser().resolve()
    environment = _sim_file(root, value('environment_config'))
    survey = value('survey') == 'true'
    profile = load_environment(environment, root, 'sim', require_survey=survey)
    for key in ('map_yaml', 'route_graph', 'nav_params', 'device_config'):
        _sim_file(root, profile[key])
    from farm_sim_runtime.station_spawn import read_station
    device_path = _sim_file(root, profile['device_config'])
    station = read_station(device_path, read_mapping(device_path))
    if station is not None:
        _sim_file(root, station['source'])
        if survey or value('navigation') == 'true':
            amcl = load_nav2_parameters(profile['nav_params'], root)['amcl']['ros__parameters']
            expected = dict(x=station['xy_m'][0], y=station['xy_m'][1], z=0.0,
                            yaw=station['yaw_rad'])
            if amcl.get('set_initial_pose') is not True or amcl.get('initial_pose') != expected:
                raise RuntimeError('station과 AMCL 초기 위치가 다릅니다. '
                                   'python sim/tools/rebuild_route_data.py를 실행하세요.')
    if survey:
        settings = read_mapping(_sim_file(root, profile['survey_config']))
        _sim_file(root, settings['vision_config'])
        if profile.get('patrol_config'):
            _sim_file(root, profile['patrol_config'])

    arguments = {name: value(name) for name in (
        'navigation', 'survey', 'vision_python', 'device', 'isaac_python',
        'start_isaac', 'headless', 'cmd_vel_type', 'tag_correction',
    )}
    arguments.update(
        mode='sim', project_root=str(root), environment_config=str(environment),
        assets_root=value('assets_root') or str(root / 'sim/assets'), rviz='false',
    )
    actions: list[Action] = []
    capture = ''
    if value('tag_correction') == 'true':
        _sim_file(root, profile['tag_localization_config'])
        actions, capture = tag_capture_actions(root, profile)
    arguments['capture_directory'] = capture
    common = Path(get_package_share_directory('farm_bringup')) / 'launch/scout.launch.py'
    actions.append(IncludeLaunchDescription(
        PythonLaunchDescriptionSource(str(common)), launch_arguments=arguments.items(),
    ))
    return actions


def generate_launch_description() -> LaunchDescription:
    """공통 로봇 launch에 시뮬 환경 설정을 전달합니다."""
    boolean = ['true', 'false']
    return LaunchDescription([
        DeclareLaunchArgument('project_root', description='farm_project 프로젝트 절대 경로'),
        DeclareLaunchArgument('environment_config', default_value=
                              'sim/ros_ws/src/farm_sim_config/config/scout_runtime.yaml'),
        DeclareLaunchArgument('rviz_config', default_value=''),
        DeclareLaunchArgument('navigation', default_value='true', choices=boolean),
        DeclareLaunchArgument('survey', default_value='true', choices=boolean),
        DeclareLaunchArgument('tag_correction', default_value='false', choices=boolean),
        DeclareLaunchArgument('rviz', default_value='false', choices=boolean),
        DeclareLaunchArgument('vision_python', default_value=default_vision_python()),
        DeclareLaunchArgument('isaac_python', default_value=os.environ.get('FARM_ISAAC_PYTHON', '')),
        DeclareLaunchArgument('assets_root', default_value=''),
        DeclareLaunchArgument('device', default_value='0'),
        DeclareLaunchArgument('start_isaac', default_value='false', choices=boolean),
        DeclareLaunchArgument('headless', default_value='false', choices=boolean),
        DeclareLaunchArgument('cmd_vel_type', default_value='twist', choices=['twist', 'twist_stamped']),
        OpaqueFunction(function=setup),
    ])
