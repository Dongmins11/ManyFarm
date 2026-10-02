"""예찰 서버만 실행. 통합 실행은 scout.launch.py의 survey:=true를 사용합니다."""
from pathlib import Path
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, OpaqueFunction
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from farm_navigation.configuration import load_environment, resolve_file, read_mapping


def setup(context):
    def value(key): return LaunchConfiguration(key).perform(context)
    root=Path(value('project_root')).expanduser().resolve()
    mode=value('mode');sim=mode=='sim'
    environment=value('environment_config')
    if environment:
        if value('executable') != 'scout_node':
            raise RuntimeError('환경별 공통 주행은 scout_node를 사용하세요. survey_server는 이전 직접 설정 실행용입니다.')
        environment=str(resolve_file(root,environment))
        profile=load_environment(environment,root,mode,require_survey=False)
        config=str(root / profile['survey_config'])
        if value('survey_config') and str(resolve_file(root,value('survey_config')))!=config:
            raise RuntimeError('환경 파일과 다른 survey_config를 함께 지정할 수 없습니다.')
    else:
        config=value('survey_config') or ('sim/ros_ws/src/farm_sim_config/config/scout_survey.json' if sim else 'robot/config/survey/scout_real.json')
        config=str(resolve_file(root,config))
    cfg=profile if environment else read_mapping(config)
    python=Path(value('vision_python')).expanduser()
    # 영상 준비가 안 된 경우에도 통신 노드는 대기하고 작업 수락 시 거절합니다.
    resolve_file(root,'scripts/run_scout_survey_worker.py')
    return [Node(package='scout_robot',executable=value('executable'),namespace=cfg['robot_id'],output='screen',
        sigterm_timeout='60',sigkill_timeout='5',
        remappings=[] if sim else [('/tf','tf'),('/tf_static','tf_static')],parameters=[{'use_sim_time':sim,'project_root':str(root),
        'survey_config':config,'environment_config':environment,'mode':mode,'vision_python':str(python) if value('vision_python') else '',
        'device':value('device'),'headless':value('headless').lower()=='true'}])]


def generate_launch_description():
    return LaunchDescription([
        DeclareLaunchArgument('mode',default_value='sim',choices=['sim','real']),
        DeclareLaunchArgument('executable',default_value='scout_node',choices=['scout_node','survey_server']),
        DeclareLaunchArgument('project_root'),DeclareLaunchArgument('vision_python',default_value=''),
        DeclareLaunchArgument('environment_config',default_value=''),
        DeclareLaunchArgument('survey_config',default_value=''),
        DeclareLaunchArgument('device',default_value='0'),
        DeclareLaunchArgument('headless',default_value='false'),OpaqueFunction(function=setup)])
