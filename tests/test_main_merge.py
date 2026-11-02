"""main/실물 통합 경계 회귀 검사. 노드 실행·모터 출력을 만들지 않는다."""
import ast
import importlib.util
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import patch
import unittest
import math
import os
import tempfile
import yaml
from farm_navigation.navigation_types import NavigationSettings
from farm_navigation.nav2_client import Nav2Client
from farm_navigation.route import RouteGraph
from farm_common.station_return import load_station
from launch import LaunchContext

ROOT=Path(__file__).resolve().parents[1]
PROJECT=ROOT/'farm_project'
SRC=PROJECT/'robot/ros_ws/src'

class MergeBoundaries(unittest.TestCase):
    def setUp(self):
        folder=tempfile.TemporaryDirectory(prefix="fleet_merge_launch_")
        self.addCleanup(folder.cleanup)
        env=patch.dict(os.environ,{"ROS_LOG_DIR":folder.name})
        env.start();self.addCleanup(env.stop)

    def test_no_duplicate_methods_in_merged_control(self):
        for pkg in ['farm_navigation','farm_common','scout_robot','transport_robot','farm_docking']:
            for p in (SRC/pkg).rglob('*.py'):
                for node in ast.walk(ast.parse(p.read_text())):
                    if isinstance(node,(ast.ClassDef,ast.Module)):
                        names=[x.name for x in node.body if isinstance(x,(ast.FunctionDef,ast.AsyncFunctionDef))]
                        self.assertEqual(len(names),len(set(names)),str(p))

    def test_main_transfer_custom_clock_keeps_original_budget(self):
        client=Nav2Client.__new__(Nav2Client)
        client._settings=NavigationSettings(goal_timeout_s=20.)
        client._pause_clock_factory=lambda:None
        client._nominal_linear_speed_mps=.1
        self.assertEqual(client._execution_timeout(NS(poses=[])),20.)

    def test_optional_real_features_not_enabled_by_default(self):
        cfg=NavigationSettings()
        self.assertFalse(cfg.tf_dedicated_executor)
        self.assertFalse(cfg.tf_recovery_wait_forever)
        self.assertFalse(cfg.require_active_nav2)

    def test_scout_station_uses_its_own_graph(self):
        profile=yaml.safe_load((PROJECT/'robot/config/environments/scout_real.yaml').read_text())
        graph=RouteGraph(PROJECT/profile['route_graph'])
        station=load_station(PROJECT,profile,graph)
        self.assertLess(math.dist(station.xy,graph.nodes[19]),1e-9)
        self.assertAlmostEqual(station.yaw,math.pi/2)
        self.assertEqual(station.options['strategy'],'forward_wall_then_turn')

    def navigation_launch(self,deferred):
        path=SRC/'farm_bringup/launch/scout_navigation.launch.py'
        spec=importlib.util.spec_from_file_location('merge_nav_launch',path)
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        context=LaunchContext()
        context.launch_configurations.update(dict(mode='real',project_root=str(PROJECT),robot_id='scout_01',
            map=str(PROJECT/'robot/config/maps/scout_real/many_farm.yaml'),
            nav_params=str(PROJECT/'robot/config/robots/burger/nav2.yaml'),
            route_file=str(PROJECT/'robot/config/maps/scout_real/graph.geojson'),
            tag_scan_sync='false',tag_map_id='',rviz='false',controller_output='cmd_vel_nav',
            wait_for_localization=str(deferred).lower(),route_preview='false'))
        return module.setup(context)

    def test_deferred_start_is_explicit_not_common_default(self):
        from launch_ros.actions import Node
        def names(actions):return [a.node_executable for a in actions if isinstance(a,Node)]
        self.assertNotIn('scout_navigation_start',names(self.navigation_launch(False)))
        self.assertIn('scout_navigation_start',names(self.navigation_launch(True)))

    def test_lifecycle_clients_destroyed(self):
        from unittest.mock import Mock
        c=Nav2Client.__new__(Nav2Client);c._node=Mock();c._navigate=Mock();c._follow=Mock()
        c._parameters=object();c._lifecycle_clients=[object(),object()];c._stop_publishers=[]
        c.close()
        self.assertEqual(c._node.destroy_client.call_count,3)

if __name__=='__main__':unittest.main()
