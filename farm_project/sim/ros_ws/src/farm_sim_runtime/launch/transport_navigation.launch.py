"""공통 운송 Node와 FollowPath/AMCL을 조립한다. 최종 cmd_vel은 motion_gate만 발행한다."""
from pathlib import Path
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument,OpaqueFunction
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from launch_ros.descriptions import ParameterFile
from nav2_common.launch import RewrittenYaml
from transport_robot.configuration import load_profile


def setup(context) -> list:
    def value(name):return LaunchConfiguration(name).perform(context)
    root=Path(value('project_root')).resolve()
    profile=load_profile(root,value('environment_config'),'sim');ns=profile['robot_id']
    params=ParameterFile(RewrittenYaml(source_file=profile['nav_params'],root_key=ns,
        param_rewrites={'use_sim_time':'true'},convert_types=True),allow_substs=False)
    # FollowPath 시험에 필요한 실제 Nav2 서버만 사용. 별도 주행 제어기를 만들지 않는다.
    servers=[('nav2_map_server','map_server'),('nav2_amcl','amcl'),
             ('nav2_controller','controller_server'),('nav2_velocity_smoother','velocity_smoother')]
    actions=[]
    for package,name in servers:
        remaps=[]
        if name=='controller_server':remaps=[('cmd_vel','cmd_vel_nav')]
        if name=='velocity_smoother':remaps=[('cmd_vel','cmd_vel_nav'),('cmd_vel_smoothed','motion/nav')]
        extra=[{'yaml_filename':profile['map_yaml']}] if name=='map_server' else []
        actions.append(Node(package=package,executable=name,name=name,namespace=ns,output='screen',
            parameters=[params,*extra],remappings=remaps))
    actions.append(Node(package='nav2_lifecycle_manager',executable='lifecycle_manager',name='transport_lifecycle_manager',
        namespace=ns,output='screen',parameters=[dict(use_sim_time=True,autostart=True,
            node_names=[name for _,name in servers],bond_timeout=10.)]))
    actions.append(Node(package='transport_robot',executable='transport_node',namespace=ns,output='screen',
        parameters=[dict(project_root=str(root),environment_config=value('environment_config'),mode='sim',use_sim_time=True,
            allow_route_checks=True,journal_dir=value('journal_dir'))],sigterm_timeout='20',sigkill_timeout='5'))
    return actions


def generate_launch_description():
    return LaunchDescription([DeclareLaunchArgument('project_root'),
        DeclareLaunchArgument('environment_config',default_value='sim/ros_ws/src/farm_sim_config/config/transport_runtime.yaml'),
        DeclareLaunchArgument('journal_dir',default_value=''),OpaqueFunction(function=setup)])
