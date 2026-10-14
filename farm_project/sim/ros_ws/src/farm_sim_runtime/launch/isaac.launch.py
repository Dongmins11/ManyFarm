"""Isaac 환경만 실행합니다. ROS 장치 어댑터·Nav2·업무 서버·RViz는 시작하지 않습니다."""
import json
import os
from pathlib import Path
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, ExecuteProcess, OpaqueFunction, RegisterEventHandler, EmitEvent
from launch.event_handlers import OnProcessExit
from launch.events import Shutdown
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from farm_navigation.configuration import load_environment
from farm_sim_runtime.station_spawn import read_station


def setup(context) -> list:
    import farm_common, farm_navigation, farm_sim_devices, farm_sim_runtime

    def value(name: str) -> str:
        return LaunchConfiguration(name).perform(context)

    root = Path(value('project_root')).expanduser().resolve()
    environment = (root / value('environment_config')).resolve()
    if not environment.is_relative_to(root / 'sim'):
        raise ValueError('Isaac 환경 설정은 sim 안에 있어야 합니다.')
    profile = load_environment(environment, root, 'sim', require_survey=False)
    config = Path(profile['device_config']).resolve()
    if not config.is_relative_to(root / 'sim'):
        raise ValueError('가상 장치 설정은 sim 안에 있어야 합니다.')
    read_station(config, json.loads(config.read_text()))
    executable = Path(value('isaac_python')).expanduser()
    if not value('isaac_python') or not executable.is_file() or not os.access(executable, os.X_OK):
        raise RuntimeError('isaac_python에 Isaac 환경의 Python 실행 파일을 지정하세요.')
    # venv 심볼릭 링크를 resolve하지 않아 해당 Python 환경을 보존합니다.
    executable = executable.absolute()
    assets = Path(value('assets_root')).expanduser().resolve() if value('assets_root') else root / 'sim/assets'
    runner = Path(farm_sim_runtime.__file__).resolve().parent / 'run_sim.py'
    command = [str(executable), str(runner), '--project-root', str(root),
               '--config', str(config), '--assets-root', str(assets)]
    if value('fleet_config'):
        from farm_sim_runtime.fleet_config import load_fleet
        fleet = (root / value('fleet_config')).resolve()
        load_fleet(root, fleet)
        runner = runner.with_name('run_fleet.py')
        command = [str(executable), str(runner), '--project-root', str(root),
                   '--fleet-config', str(fleet), '--assets-root', str(assets)]
    for module in (farm_common, farm_navigation, farm_sim_devices, farm_sim_runtime):
        command += ['--module-path', str(Path(module.__file__).resolve().parent.parent)]
    if value('headless') == 'true':
        command.append('--headless')
    if value('physics_device') != 'profile':
        command += ['--physics-device', value('physics_device')]
    if value('performance_log'):
        if not value('fleet_config'):
            raise ValueError('performance_log는 fleet 실행에서 사용합니다.')
        command += ['--performance-log', str(root / value('performance_log'))]
    env = dict(os.environ)
    for key in ('PYTHONPATH', 'PYTHONHOME', 'LD_LIBRARY_PATH', 'AMENT_PREFIX_PATH',
                'CMAKE_PREFIX_PATH', 'COLCON_PREFIX_PATH'):
        env.pop(key, None)
    env.update(VIRTUAL_ENV=str(executable.parent.parent), PYTHONUNBUFFERED='1')
    process = ExecuteProcess(cmd=command, env=env, output='screen',
                             sigterm_timeout='15', sigkill_timeout='15')
    actions = [RegisterEventHandler(OnProcessExit(target_action=process,
               on_exit=[EmitEvent(event=Shutdown(reason='Isaac 환경 종료'))])), process]
    if value('fleet_config'):
        relay = Node(package='farm_sim_devices', executable='clock_relay', output='screen',
                     parameters=[dict(fleet_config=str(fleet), use_sim_time=False)])
        actions += [RegisterEventHandler(OnProcessExit(target_action=relay,
                    on_exit=[EmitEvent(event=Shutdown(reason='Isaac clock 연결 종료'))])), relay]
    return actions


def generate_launch_description() -> LaunchDescription:
    return LaunchDescription([
        DeclareLaunchArgument('project_root'),
        DeclareLaunchArgument('environment_config', default_value=
                              'sim/ros_ws/src/farm_sim_config/config/scout_runtime.yaml'),
        DeclareLaunchArgument('isaac_python', default_value=os.environ.get('FARM_ISAAC_PYTHON', '')),
        DeclareLaunchArgument('assets_root', default_value=''),
        DeclareLaunchArgument('fleet_config', default_value=''),
        DeclareLaunchArgument('headless', default_value='false', choices=['true', 'false']),
        DeclareLaunchArgument('physics_device', default_value='profile', choices=['profile', 'cpu', 'gpu']),
        DeclareLaunchArgument('performance_log', default_value=''),
        OpaqueFunction(function=setup),
    ])
