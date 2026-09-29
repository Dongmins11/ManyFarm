"""ROS adapter와 Isaac Sim 1개를 함께 실행합니다."""
import os
from pathlib import Path
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument,ExecuteProcess,OpaqueFunction,RegisterEventHandler,EmitEvent
from launch.event_handlers import OnProcessExit
from launch.events import Shutdown
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def setup(context):
    import farm_common,farm_sim_devices,farm_sim_runtime
    value=lambda name:LaunchConfiguration(name).perform(context)
    config=Path(get_package_share_directory('farm_sim_config'))/'config/scout.json'
    import json
    cfg=json.loads(config.read_text())
    adapter=Node(package='farm_sim_devices',executable='ros_adapter',namespace=cfg['robot_id'],
                 parameters=[{'config_file':str(config),'cmd_vel_type':value('cmd_vel_type'),'use_sim_time':True}],output='screen')
    actions=[RegisterEventHandler(OnProcessExit(target_action=adapter,
             on_exit=[EmitEvent(event=Shutdown(reason='ROS 장치 연결 종료'))])),adapter]
    if value('start_isaac')=='true':
        executable=Path(value('isaac_python')).expanduser()
        if not value('isaac_python') or not executable.is_file() or not os.access(executable,os.X_OK):
            raise RuntimeError('isaac_python에 env_isaaclab의 Python 실행 파일 경로를 지정하세요.')
        if not value('assets_root'):raise RuntimeError('assets_root에 sim/assets 경로를 지정하세요.')
        # venv python symlink를 resolve하면 venv 밖 interpreter가 될 수 있어 유지합니다.
        executable=executable.absolute()
        runner=Path(farm_sim_runtime.__file__).resolve().parent/'run_sim.py'
        cmd=[str(executable),str(runner),'--config',str(config),'--assets-root',value('assets_root')]
        for module in (farm_common,farm_sim_devices,farm_sim_runtime):
            cmd+=['--module-path',str(Path(module.__file__).resolve().parent.parent)]
        if value('headless')=='true':cmd+=['--headless']
        env=dict(os.environ)
        # ROS Python 3.12/site-packages와 공유 라이브러리를 Isaac Python으로 전파하지 않습니다.
        for name in ('PYTHONPATH','PYTHONHOME','LD_LIBRARY_PATH','AMENT_PREFIX_PATH','CMAKE_PREFIX_PATH','COLCON_PREFIX_PATH'):
            env.pop(name,None)
        env['VIRTUAL_ENV']=str(executable.parent.parent)
        env['PYTHONUNBUFFERED']='1'
        process=ExecuteProcess(cmd=cmd,env=env,output='screen',sigterm_timeout='15',sigkill_timeout='15')
        actions=[RegisterEventHandler(OnProcessExit(target_action=process,
                 on_exit=[EmitEvent(event=Shutdown(reason='Isaac Sim 종료'))])),*actions,process]
    return actions


def generate_launch_description():
    return LaunchDescription([
        DeclareLaunchArgument('assets_root',default_value=''),
        DeclareLaunchArgument('isaac_python',default_value=''),
        DeclareLaunchArgument('start_isaac',default_value='true'),
        DeclareLaunchArgument('headless',default_value='false'),
        DeclareLaunchArgument('cmd_vel_type',default_value='twist'),
        OpaqueFunction(function=setup),
    ])
