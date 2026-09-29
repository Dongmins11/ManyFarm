"""Start the ScoutArea server. Motion begins only upon a goal."""
from pathlib import Path
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument,OpaqueFunction
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def setup(context):
    def value(key):return LaunchConfiguration(key).perform(context)
    root=Path(value('project_root')).expanduser().resolve()
    sim=value('mode')=='sim'
    config=value('survey_config')
    if not config and sim:config=str(root/'sim/ros_ws/src/farm_sim_config/config/scout_survey.json')
    if not config and not sim:config=str(root/'robot/config/scout_survey_real.json')
    if not Path(config).is_file():raise RuntimeError(f'Valid survey_config is required: {config}. real 설정은 실물 베드/센서 정보로 작성하세요.')
    python=Path(value('vision_python')).expanduser()
    if not python.is_file():raise RuntimeError('vision_python에 YOLO 환경의 실제 Python 경로를 지정하세요.')
    if not (root/'scripts/run_scout_survey_worker.py').is_file():raise RuntimeError('project_root must point to farm_project')
    return [Node(package='scout_robot',executable='survey_server',namespace='scout_01',output='screen',
        sigterm_timeout='35',sigkill_timeout='5',parameters=[{'use_sim_time':sim,'project_root':str(root),
        'survey_config':str(Path(config).resolve()),'vision_python':str(python),
        'device':value('device'),'headless':value('headless').lower()=='true'}])]


def generate_launch_description():
    return LaunchDescription([
        DeclareLaunchArgument('mode',default_value='sim',choices=['sim','real']),
        DeclareLaunchArgument('project_root'),DeclareLaunchArgument('vision_python'),
        DeclareLaunchArgument('survey_config',default_value=''),
        DeclareLaunchArgument('device',default_value='0'),
        DeclareLaunchArgument('headless',default_value='false'),OpaqueFunction(function=setup)])
