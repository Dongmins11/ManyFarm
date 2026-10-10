"""공유 launch의 기본 AMCL 선택과 수확 전용 선택만 검사한다."""
from pathlib import Path
from types import ModuleType
from unittest.mock import patch
import importlib.util
import sys
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[5]

class Action:
    def __init__(self,*args,**kwargs):self.args=args;self.kwargs=kwargs

class Config:
    def __init__(self,name):self.name=name
    def perform(self,context):return context[self.name]

def launch(path: Path, folder: str, selected: bool=False, mode: str='real') -> list:
    modules={}
    def module(name: str, **attrs: object) -> None:
        m=ModuleType(name);m.__dict__.update(attrs);modules[name]=m
    module('ament_index_python');module('ament_index_python.packages',get_package_share_directory=lambda _:folder)
    module('launch',LaunchDescription=Action)
    module('launch.actions',DeclareLaunchArgument=Action,OpaqueFunction=Action,LogInfo=Action)
    module('launch.substitutions',LaunchConfiguration=Config)
    module('launch_ros');module('launch_ros.actions',Node=Action)
    module('launch_ros.descriptions',ParameterFile=Action)
    module('nav2_common');module('nav2_common.launch',RewrittenYaml=Action)
    with patch.dict(sys.modules,modules):
        spec=importlib.util.spec_from_file_location('navigation_launch_check',path)
        m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
        return m.setup(dict(mode=mode,robot_id='harvest_01',map=folder+'/data',nav_params=folder+'/data',
                            route_file=folder+'/data',rviz='false',tag_scan_sync=str(selected).lower(),tag_map_id='m'))

class ScanSyncLaunch(unittest.TestCase):
    def test_default_is_stock_amcl(self):
        with tempfile.TemporaryDirectory() as folder:
            Path(folder,'data').write_text('x')
            actions=launch(ROOT/'robot/ros_ws/src/farm_bringup/launch/scout_navigation.launch.py',folder)
            amcl=next(a.kwargs for a in actions if a.kwargs.get('name')=='amcl')
            self.assertEqual(amcl['package'],'nav2_amcl')
            self.assertEqual(len(amcl['parameters']),1)

    def test_explicit_receiver_has_same_namespace_tf_and_lifecycle_name(self):
        with tempfile.TemporaryDirectory() as folder:
            Path(folder,'data').write_text('x')
            actions=launch(ROOT/'robot/ros_ws/src/farm_bringup/launch/scout_navigation.launch.py',folder,True)
            amcl=next(a.kwargs for a in actions if a.kwargs.get('name')=='amcl')
            self.assertEqual(amcl['package'],'farm_tag_amcl')
            self.assertEqual(amcl['namespace'],'harvest_01')
            self.assertIn(('/tf','/harvest_01/tf'),amcl['remappings'])
            self.assertEqual(amcl['parameters'][1],dict(tag_robot_id='harvest_01',tag_map_id='m'))
            manager=next(a.kwargs for a in actions if a.kwargs.get('name')=='lifecycle_manager_navigation')
            self.assertEqual(manager['parameters'][0]['node_names'].count('amcl'),1)
            with self.assertRaises(ValueError):
                launch(ROOT/'robot/ros_ws/src/farm_bringup/launch/scout_navigation.launch.py',folder,True,'sim')

if __name__=='__main__':unittest.main()
