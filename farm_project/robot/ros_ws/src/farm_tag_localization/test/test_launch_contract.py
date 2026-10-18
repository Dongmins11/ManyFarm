"""Launch 조립 계약 검사. 실제 ROS launch 실행 시험은 아니다."""
import importlib.util
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace as NS
from unittest.mock import patch
import unittest
ROOT=Path(__file__).resolve().parents[5]

class LaunchContract(unittest.TestCase):
    def setup_launch(self, enabled, *, camera="auto", folder="/capture/current", devices="false", mode="real", staged=False, navigation="true", movement_mode="route_then_pose", approach_planner="route_server", scan_sync=False):
        class Action:
            def __init__(self,*args,**kwargs):self.args=args;self.kwargs=kwargs
        class Config:
            def __init__(self,key):self.key=key
            def perform(self,context):return context[self.key]
        profile=dict(robot_id='harvest_01',map_id='m',harvest_config='robot/h.yaml',device_config=str(ROOT/'robot/d.yaml'),map_yaml=str(ROOT/'robot/m.yaml'),nav_params=str(ROOT/'robot/n.yaml'),route_graph=str(ROOT/'robot/g.json'),tag_localization_config='robot/t.yaml',tag_capture_config='robot/camera.yaml')
        profile.update(navigation={'map_frame':'map','base_frame':'base_footprint'}, route_server_params='robot/route.yaml')
        if mode == 'sim':
            profile = {k: (v.replace('/robot/','/sim/').replace('robot/','sim/',1) if isinstance(v,str) and 'robot/' in v else v) for k,v in profile.items()}
        modules={}
        def stub(name,**attrs):
            m=ModuleType(name);m.__dict__.update(attrs);modules[name]=m
        stub('ament_index_python');stub('ament_index_python.packages',get_package_share_directory=lambda p:'/share/'+p)
        stub('launch',LaunchDescription=Action)
        stub('launch.actions',DeclareLaunchArgument=Action,IncludeLaunchDescription=Action,OpaqueFunction=Action)
        stub('launch.launch_description_sources',PythonLaunchDescriptionSource=Action)
        stub('launch.substitutions',LaunchConfiguration=Config)
        stub('launch_ros');stub('launch_ros.actions',Node=Action)
        stub('launch_ros.descriptions',ParameterFile=Action)
        stub('nav2_common');stub('nav2_common.launch',RewrittenYaml=Action)
        stub('farm_navigation');stub('farm_navigation.configuration',load_environment=lambda *a,**k:profile,resolve_file=lambda r,p:r/p,read_mapping=lambda p:({'correction_transport':'scan_sync'} if scan_sync and str(p).endswith('/t.yaml') else ({'movement_mode':movement_mode,'approach_planner':approach_planner} if staged else {})))
        stub('harvest_robot.configuration',transfer_parameters=lambda c: {'transfer_enabled':False},load_harvest_config=lambda *a:({'movement_mode':movement_mode,'approach_planner':approach_planner} if staged else {}))
        calls=[]
        stub('farm_tag_localization.runtime',validate_binding=lambda *a:calls.append(a))
        with patch.dict(sys.modules,modules):
            spec=importlib.util.spec_from_file_location('harvest_launch_contract',ROOT/'robot/ros_ws/src/farm_bringup/launch/harvest.launch.py')
            module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
            actions=module.setup(dict(mode=mode,devices=devices,navigation=navigation,project_root=str(ROOT),environment_config=('sim/e.yaml' if mode == 'sim' else 'robot/e.yaml'),tag_correction=str(enabled).lower(),capture_directory=folder,tag_camera=camera))
        return actions,calls

    def test_scan_sync_selected_by_explicit_transport_in_both_modes(self):
        for mode,enabled,expected in [('real',True,'true'),('real',False,'false'),('sim',True,'true'),('sim',False,'false')]:
            actions,_=self.setup_launch(enabled,mode=mode,scan_sync=True)
            args=dict(actions[0].kwargs['launch_arguments'])
            self.assertEqual(args['tag_scan_sync'],expected)
            self.assertEqual(args['tag_map_id'],'m' if expected=='true' else '')

    def test_graph_approach_does_not_launch_unused_route_server(self):
        actions,_=self.setup_launch(True,staged=True,movement_mode='route_then_follow',approach_planner='graph')
        executables=[a.kwargs.get('executable') for a in actions]
        self.assertNotIn('route_server',executables)
        self.assertNotIn('lifecycle_manager',executables)
        self.assertIn('harvest_node',executables)
        self.assertIn('tag_amcl_adapter',executables)

    def test_invalid_approach_rejected(self):
        with self.assertRaises(ValueError):
            self.setup_launch(False,staged=True,approach_planner='typo')

    def test_follow_work_keeps_single_route_server(self):
        actions,_=self.setup_launch(False,staged=True,movement_mode='route_then_follow')
        servers=[a.kwargs for a in actions if a.kwargs.get('executable')=='route_server']
        self.assertEqual(len(servers),1)
        self.assertEqual(servers[0]['namespace'],'harvest_01')
        self.assertIn(('/tf','/harvest_01/tf'),servers[0]['remappings'])

    def test_follow_work_external_navigation_does_not_duplicate_server(self):
        actions,_=self.setup_launch(False,staged=True,navigation='false',movement_mode='route_then_follow')
        self.assertFalse(any(a.kwargs.get('executable')=='route_server' for a in actions))
        self.assertEqual(actions[-1].kwargs['package'],'harvest_robot')

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


    def test_real_single_launch_owns_devices_camera_and_adapter_session(self):
        actions,calls=self.setup_launch(True,folder='',devices='true')
        self.assertEqual(len(actions),4)
        self.assertIn('farm_real_devices',str(actions[0].args[0].args))
        capture=actions[-1].kwargs
        self.assertEqual(capture['executable'],'tag_capture_session')
        self.assertIn('--correction-config',capture['arguments'])
        self.assertNotIn('on_exit',capture)

    def test_off_can_collect_without_correction(self):
        actions,calls=self.setup_launch(False,camera='true',folder='')
        self.assertFalse(calls)
        self.assertNotIn('--correction-config',actions[-1].kwargs['arguments'])
        self.assertFalse(actions[-2].kwargs['parameters'][0]['tag_correction'])

    def test_double_capture_rejected(self):
        with self.assertRaises(ValueError):self.setup_launch(True,camera='true')

    def test_real_usb_capture_never_started_in_sim(self):
        with self.assertRaises(ValueError):self.setup_launch(True,camera='true',folder='',mode='sim')

    def test_sim_off_keeps_sim_devices_and_no_capture(self):
        actions,calls=self.setup_launch(False,devices='true',mode='sim',folder='')
        self.assertEqual(len(actions),3)
        self.assertIn('farm_sim_runtime',str(actions[0].args[0].args))
        self.assertEqual(actions[-1].kwargs['remappings'],[])

    def test_sim_external_capture_keeps_tf_mapping(self):
        actions,calls=self.setup_launch(True,mode='sim')
        self.assertEqual(actions[-1].kwargs['executable'],'tag_amcl_adapter')
        self.assertEqual(actions[-1].kwargs['remappings'],[])

    def test_staged_launch_has_route_server_with_same_graph_tf(self):
        actions,_=self.setup_launch(False,staged=True)
        server=next(a.kwargs for a in actions if a.kwargs.get('executable')=='route_server')
        self.assertEqual(server['namespace'],'harvest_01')
        self.assertEqual(server['parameters'][1]['graph_filepath'],str(ROOT/'robot/g.json'))
        self.assertIn(('/tf','/harvest_01/tf'),server['remappings'])
        lifecycle=next(a.kwargs for a in actions if a.kwargs.get('name')=='route_lifecycle_manager')
        self.assertEqual(lifecycle['parameters'][0]['node_names'],['route_server'])

    def test_external_navigation_does_not_duplicate_route_server(self):
        actions,_=self.setup_launch(False,staged=True,navigation='false')
        self.assertFalse(any(a.kwargs.get('executable')=='route_server' for a in actions))
