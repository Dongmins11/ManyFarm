"""공통 시작점. real/sim의 장치 연결부만 선택합니다."""
import os
from pathlib import Path
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument,IncludeLaunchDescription,OpaqueFunction
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration


def select_mode(context):
    mode=LaunchConfiguration('mode').perform(context)
    if mode not in ('sim','real'):raise RuntimeError('mode는 sim 또는 real이어야 합니다.')
    package='farm_sim_runtime' if mode=='sim' else 'farm_real_devices'
    file=Path(get_package_share_directory(package))/'launch/scout_devices.launch.py'
    args={name:LaunchConfiguration(name) for name in ('assets_root','isaac_python','start_isaac','headless','cmd_vel_type')}
    actions = [IncludeLaunchDescription(PythonLaunchDescriptionSource(str(file)),launch_arguments=args.items())]
    if LaunchConfiguration('navigation').perform(context) == 'true':
        if LaunchConfiguration('cmd_vel_type').perform(context) != 'twist':
            raise RuntimeError('이번 Nav2 설정은 cmd_vel_type:=twist를 사용합니다.')
        navigation = Path(get_package_share_directory('farm_bringup'))/'launch/scout_navigation.launch.py'
        nav_args = {name: LaunchConfiguration(name) for name in ('mode', 'map', 'nav_params', 'route_file', 'rviz')}
        actions.append(IncludeLaunchDescription(PythonLaunchDescriptionSource(str(navigation)), launch_arguments=nav_args.items()))
    return actions


def generate_launch_description():
    return LaunchDescription([
        DeclareLaunchArgument('mode',default_value='sim',choices=['sim','real']),
        DeclareLaunchArgument('assets_root',default_value=os.environ.get('FARM_ASSETS_ROOT','')),
        DeclareLaunchArgument('isaac_python',default_value=os.environ.get('FARM_ISAAC_PYTHON','')),
        DeclareLaunchArgument('start_isaac',default_value='true',choices=['true','false']),
        DeclareLaunchArgument('headless',default_value='false',choices=['true','false']),
        DeclareLaunchArgument('cmd_vel_type',default_value='twist',choices=['twist','twist_stamped']),
        DeclareLaunchArgument('navigation',default_value='false',choices=['true','false']),
        DeclareLaunchArgument('rviz',default_value='true',choices=['true','false']),
        DeclareLaunchArgument('map',default_value=''),
        DeclareLaunchArgument('nav_params',default_value=''),
        DeclareLaunchArgument('route_file',default_value=''),
        OpaqueFunction(function=select_mode),
    ])
