"""로봇 한 대의 장치·주행·예찰 서버 실행. Isaac/RViz는 독립 실행합니다."""
import os
from pathlib import Path
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription, OpaqueFunction
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from farm_navigation.configuration import load_environment, resolve_file


def select_mode(context) -> list:
    def value(name: str) -> str: return LaunchConfiguration(name).perform(context)
    if value('start_isaac') == 'true' or value('rviz') == 'true':
        raise RuntimeError('로봇 bringup은 Isaac/RViz를 시작하지 않습니다. '
                           'Isaac은 farm_sim_runtime isaac.launch.py, '
                           'RViz는 farm_bringup rviz.launch.py, '
                           '시뮬 전체 실행은 farm_sim_runtime all.launch.py를 사용하세요.')
    mode=value('mode');survey=value('survey')=='true'
    profile=None
    root=Path(value('project_root')).expanduser().resolve()
    environment=value('environment_config')
    if survey or environment or value('navigation')=='true':
        if not value('project_root'): raise RuntimeError('project_root에 farm_project 경로를 지정하세요.')
        environment=environment or ('sim/ros_ws/src/farm_sim_config/config/scout_runtime.yaml' if mode=='sim' else 'robot/config/environments/scout_real.yaml')
        environment=str(resolve_file(root,environment))
        profile=load_environment(environment,root,mode,require_survey=False)
        # 환경 선택 후 일부 지도만 따로 바뀌는 설정 혼합을 거절합니다.
        for argument,key in [('map','map_yaml'),('nav_params','nav_params'),('route_file','route_graph')]:
            if value(argument) and str(resolve_file(root,value(argument)))!=profile[key]:
                raise RuntimeError(f'{argument}를 환경 파일과 다르게 지정할 수 없습니다.')

    package='farm_sim_runtime' if mode=='sim' else 'farm_real_devices'
    device_launch=Path(get_package_share_directory(package))/'launch/scout_devices.launch.py'
    device_args={'cmd_vel_type':value('cmd_vel_type')}
    if mode=='sim':
        device_args['start_isaac']='false'
    elif value('project_root'):
        device_args['config_file']=str(resolve_file(root,'robot/config/robots/burger/devices.json'))
    if profile: device_args['config_file']=profile['device_config']
    actions=[IncludeLaunchDescription(PythonLaunchDescriptionSource(str(device_launch)),launch_arguments=device_args.items())]
    share=Path(get_package_share_directory('farm_bringup'))/'launch'
    if survey or value('navigation')=='true':
        if value('cmd_vel_type')!='twist': raise RuntimeError('현재 farm Nav2 구성은 cmd_vel_type:=twist를 사용합니다.')
        args={name:value(name) for name in ('mode','map','nav_params','route_file','rviz')}
        if profile: args.update(map=profile['map_yaml'],nav_params=profile['nav_params'],route_file=profile['route_graph'],robot_id=profile['robot_id'])
        actions.append(IncludeLaunchDescription(PythonLaunchDescriptionSource(str(share/'scout_navigation.launch.py')),launch_arguments=args.items()))
    if survey:
        args={name:value(name) for name in ('mode','vision_python','headless','device')}
        args.update(project_root=str(root),environment_config=environment)
        actions.append(IncludeLaunchDescription(PythonLaunchDescriptionSource(str(share/'scout_survey.launch.py')),launch_arguments=args.items()))
    return actions


def generate_launch_description() -> LaunchDescription:
    return LaunchDescription([
        DeclareLaunchArgument('mode',default_value='sim',choices=['sim','real']),
        DeclareLaunchArgument('project_root',default_value=''),
        DeclareLaunchArgument('environment_config',default_value=''),
        DeclareLaunchArgument('survey',default_value='true',choices=['true','false']),
        DeclareLaunchArgument('vision_python',default_value=os.environ.get('FARM_VISION_PYTHON','')),
        DeclareLaunchArgument('device',default_value='0'),
        DeclareLaunchArgument('assets_root',default_value=os.environ.get('FARM_ASSETS_ROOT','')),
        DeclareLaunchArgument('isaac_python',default_value=os.environ.get('FARM_ISAAC_PYTHON','')),
        DeclareLaunchArgument('start_isaac',default_value='false',choices=['true','false'],description='호환 인자. true는 별도 실행 안내 오류'),
        DeclareLaunchArgument('headless',default_value='false',choices=['true','false']),
        DeclareLaunchArgument('cmd_vel_type',default_value='twist',choices=['twist','twist_stamped']),
        DeclareLaunchArgument('navigation',default_value='true',choices=['true','false']),
        DeclareLaunchArgument('rviz',default_value='false',choices=['true','false'],description='호환 인자. RViz는 독립 실행'),
        DeclareLaunchArgument('map',default_value=''),DeclareLaunchArgument('nav_params',default_value=''),
        DeclareLaunchArgument('route_file',default_value=''),OpaqueFunction(function=select_mode)])
