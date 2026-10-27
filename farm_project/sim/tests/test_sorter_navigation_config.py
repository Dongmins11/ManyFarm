"""운송 원본 수치 보존·선별장 환경 정합·최종 cmd_vel 단일 출력 검사."""
import json
import math
import sys
import unittest
from pathlib import Path
import yaml
ROOT=Path(__file__).resolve().parents[2];CFG=ROOT/'sim/ros_ws/src/farm_sim_config/config'
sys.path.insert(0,str(ROOT/'robot/ros_ws/src/farm_navigation'))
from farm_navigation.route import RouteGraph

class SorterConfigTests(unittest.TestCase):
    def test_source_control_and_safety_numbers_preserved(self):
        source=yaml.safe_load((CFG/'transport_sources/waffle_nav2.yaml').read_text())
        current=yaml.safe_load((CFG/'nav2_transport.yaml').read_text())
        def check(a,b,path=''):
            self.assertEqual(type(a),type(b),path)
            if isinstance(a,dict):
                self.assertEqual(set(a),set(b),path)
                for key in a:check(a[key],b[key],path+'/'+key)
            elif isinstance(a,list):
                self.assertEqual(len(a),len(b))
                for i,(x,y) in enumerate(zip(a,b)):check(x,y,path+'/'+str(i))
            elif not (path.endswith(('use_sim_time','set_initial_pose')) or '/initial_pose/' in path):
                if not isinstance(a,str):self.assertEqual(a,b,path)
        check(source,current)
        self.assertEqual(current['velocity_smoother']['ros__parameters']['odom_topic'],'odom')
        self.assertEqual(current['amcl']['ros__parameters']['odom_frame_id'],'transport_01/odom')
    def test_sorter_and_task_and_graph_agree(self):
        task=yaml.safe_load((CFG/'task.yaml').read_text())
        graph=RouteGraph(CFG.parent/'maps/transport_graph.geojson')
        target=yaml.safe_load((CFG/'transport_destinations.yaml').read_text())['destinations']['SORT_01']
        s=task['stations']['sorting_station']
        self.assertEqual(tuple(s['xy_m']),graph.nodes[target['approach_node_id']])
        self.assertAlmostEqual(s['yaw_rad'],math.pi/2)
        self.assertEqual(target['approach_yaw_rad'],s['yaw_rad'])
        incoming={e.start for e in graph.edges if e.end==s['node_id']}
        self.assertEqual(incoming,{9001})
        self.assertGreater(graph.plan((2.,11.5),tuple(s['xy_m'])).distance_m,10.)
    def test_navigation_output_goes_through_existing_gate(self):
        # 실행 조립 파일 자체의 금지된 직접 출력도 확인한다.
        text=(ROOT/'sim/ros_ws/src/farm_sim_runtime/launch/transport_navigation.launch.py').read_text()
        self.assertIn("('cmd_vel_smoothed','motion/nav')",text)
        self.assertNotIn("('cmd_vel_smoothed','cmd_vel')",text)
        p=yaml.safe_load((CFG/'transport_runtime.yaml').read_text())
        self.assertTrue(p['precision_enabled'])
        self.assertFalse(p['navigation']['tf_recovery_enabled'])
        self.assertEqual(p['navigation']['collision_retry_count'],0)

if __name__=='__main__':unittest.main()
