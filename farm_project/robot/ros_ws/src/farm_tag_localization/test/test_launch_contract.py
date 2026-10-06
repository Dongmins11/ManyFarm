"""Launch 조립 계약 검사. 실제 ROS launch 실행 시험은 아니다."""
import importlib.util
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace as NS
from unittest.mock import patch
import unittest
ROOT=Path(__file__).resolve().parents[5]

class LaunchContract(unittest.TestCase):
    def setup_launch(self, enabled):
        class Action:
            def __init__(self,*args,**kwargs):self.args=args;self.kwargs=kwargs
        class Config:
            def __init__(self,key):self.key=key
            def perform(self,context):return context[self.key]
        profile=dict(robot_id='harvest_01',map_id='m',harvest_config='robot/h.yaml',device_config=str(ROOT/'robot/d.yaml'),map_yaml=str(ROOT/'robot/m.yaml'),nav_params=str(ROOT/'robot/n.yaml'),route_graph=str(ROOT/'robot/g.json'),tag_localization_config='robot/t.yaml')
        modules={}
        def stub(name,**attrs):
            m=ModuleType(name);m.__dict__.update(attrs);modules[name]=m
        stub('ament_index_python');stub('ament_index_python.packages',get_package_share_directory=lambda p:'/share/'+p)
        stub('launch',LaunchDescription=Action)
        stub('launch.actions',DeclareLaunchArgument=Action,IncludeLaunchDescription=Action,OpaqueFunction=Action)
        stub('launch.launch_description_sources',PythonLaunchDescriptionSource=Action)
        stub('launch.substitutions',LaunchConfiguration=Config)
        stub('launch_ros');stub('launch_ros.actions',Node=Action)
        stub('farm_navigation');stub('farm_navigation.configuration',load_environment=lambda *a,**k:profile,resolve_file=lambda r,p:r/p,read_mapping=lambda p:{})
        calls=[]
        stub('farm_tag_localization.runtime',validate_binding=lambda *a:calls.append(a))
        with patch.dict(sys.modules,modules):
            spec=importlib.util.spec_from_file_location('harvest_launch_contract',ROOT/'robot/ros_ws/src/farm_bringup/launch/harvest.launch.py')
            module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
            actions=module.setup(dict(mode='real',devices='false',navigation='true',project_root=str(ROOT),environment_config='robot/e.yaml',tag_correction=str(enabled).lower(),capture_directory='/capture/current'))
        return actions,calls

    def test_off_preserves_navigation_without_adapter(self):
        actions,calls=self.setup_launch(False)
        self.assertEqual(len(actions),2);self.assertFalse(calls)
        node=actions[-1].kwargs
        self.assertEqual(node['package'],'harvest_robot')
        self.assertFalse(node['parameters'][0]['tag_correction'])
        self.assertIn(('/tf','/harvest_01/tf'),node['remappings'])

    def test_on_adds_independent_adapter_and_matching_tf(self):
        actions,calls=self.setup_launch(True)
        self.assertEqual(len(actions),3);self.assertEqual(len(calls),1)
        harvest,adapter=actions[-2].kwargs,actions[-1].kwargs
        self.assertEqual(adapter['package'],'farm_tag_localization')
        self.assertEqual(harvest['remappings'],adapter['remappings'])
        self.assertEqual(adapter['parameters'][0]['capture_directory'],'/capture/current')
        self.assertTrue(harvest['parameters'][0]['tag_correction'])
        self.assertNotIn('on_exit',adapter)
