"""기존 장치 시작점 유지. survey:=true일 때 환경 설정 하나로 전체 예찰을 연결합니다."""
import os
from pathlib import Path
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription, OpaqueFunction
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from farm_navigation.configuration import load_environment, resolve_file


def select_mode(context):
    def value(name): return LaunchConfiguration(name).perform(context)
    mode=value('mode');survey=value('survey')=='true'
    profile=None
    root=Path(value('project_root')).expanduser().resolve()
    environment=value('environment_config')
    if survey or environment or (mode=='real' and value('navigation')=='true'):
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
        device_args.update({name:value(name) for name in ('assets_root','isaac_python','start_isaac','headless')})
    elif value('project_root'):
        device_args['config_file']=str(resolve_file(root,'robot/config/robots/burger/devices.json'))
    if profile: device_args['config_file']=profile['device_config']
    if profile and mode=='sim' and not device_args['assets_root']:
        device_args['assets_root']=str(root/'sim/assets')
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


def generate_launch_description():
    return LaunchDescription([
        DeclareLaunchArgument('mode',default_value='sim',choices=['sim','real']),
        DeclareLaunchArgument('project_root',default_value=''),
        DeclareLaunchArgument('environment_config',default_value=''),
        DeclareLaunchArgument('survey',default_value='false',choices=['true','false']),
        DeclareLaunchArgument('vision_python',default_value=os.environ.get('FARM_VISION_PYTHON','')),
        DeclareLaunchArgument('device',default_value='0'),
        DeclareLaunchArgument('assets_root',default_value=os.environ.get('FARM_ASSETS_ROOT','')),
        DeclareLaunchArgument('isaac_python',default_value=os.environ.get('FARM_ISAAC_PYTHON','')),
        DeclareLaunchArgument('start_isaac',default_value='true',choices=['true','false']),
        DeclareLaunchArgument('headless',default_value='false',choices=['true','false']),
        DeclareLaunchArgument('cmd_vel_type',default_value='twist',choices=['twist','twist_stamped']),
        DeclareLaunchArgument('navigation',default_value='false',choices=['true','false']),
        DeclareLaunchArgument('rviz',default_value='true',choices=['true','false']),
        DeclareLaunchArgument('map',default_value=''),DeclareLaunchArgument('nav_params',default_value=''),
        DeclareLaunchArgument('route_file',default_value=''),OpaqueFunction(function=select_mode)])
