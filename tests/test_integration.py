"""운송 추가 연결의 오프라인 계약 검증. ROS 노드/하드웨어를 실행하지 않는다."""
from pathlib import Path
import sys, unittest, math, yaml
ROOT=Path(__file__).resolve().parents[1]/'farm_project'
SRC=ROOT/'robot/ros_ws/src'
for name in ('farm_docking','transport_robot','farm_navigation'):
    sys.path.insert(0,str(SRC/name))
from farm_docking.initial_marker_recovery import InitialMarkerRecovery
from transport_robot.configuration import load_profile, destination
from transport_robot.route_policy import apply_route_policy
from farm_navigation.route import RouteGraph

class Integration(unittest.TestCase):
    def setUp(self):
        self.p=load_profile(ROOT,'robot/config/environments/transport_docking_trial.yaml','real')
        self.c=self.p['precision_registry']['profiles']['sort_01_distance_trial']['initial_marker_recovery']
    def test_config_and_map_identity(self):
        self.assertEqual(self.p['map_id'],'farm_map_v1')
        self.assertFalse(self.p['navigation']['tf_recovery_enabled'])
        self.assertEqual(self.p['navigation']['collision_retry_count'],0)
    def test_branch_routes_and_restriction(self):
        g=RouteGraph(self.p['route_graph']);apply_route_policy(g,self.p['route_policy'])
        self.assertFalse(any({e.start,e.end}=={5,12} for e in g.edges))
        for a,b in ((20,17),(17,3),(10,11)):
            self.assertTrue(g.plan(g.nodes[a],g.nodes[b],.15,.02).points)
        xy,yaw=destination(self.p,g,'SORT_01')
        self.assertEqual(xy,g.nodes[17]);self.assertAlmostEqual(yaw,0.)
        xy,yaw=destination(self.p,g,'STATION_TRANSPORT_01')
        self.assertEqual(xy,g.nodes[3]);self.assertAlmostEqual(yaw,-math.pi/2)
    def test_restored_transport_graph(self):
        g=RouteGraph(self.p['route_graph'])
        for node,xy in {5:(2.181,-.72),12:(2.181,-.035),15:(2.181,-1.333),17:(2.981,-1.333),20:(1.446,-1.12)}.items():
            for actual,expected in zip(g.nodes[node],xy):self.assertAlmostEqual(actual,expected)
        def check(value):
            if isinstance(value,dict):
                for k,v in value.items():
                    if k=='graph_file':self.assertEqual((ROOT/'robot/config/docking'/v).resolve(),Path(self.p['route_graph']))
                    else:check(v)
            elif isinstance(value,list):
                for v in value:check(v)
        check(self.p['precision_registry'])
        for env in ('harvest_handoff_real','scout_real'):
            data=yaml.safe_load((ROOT/f'robot/config/environments/{env}.yaml').read_text())
            self.assertEqual(data['route_graph'],'robot/config/maps/many_farm/graph.geojson')

    def test_only_initial_approaches_opt_in(self):
        profiles=self.p['precision_registry']['profiles']
        self.assertEqual({k for k,v in profiles.items() if v.get('initial_marker_recovery',{}).get('enabled')},
                         {'harvest_approach_42','sort_01_distance_trial'})
        self.assertEqual(profiles['harvest_dock_41']['lidar_approach']['target_distance_m'],.2)
        self.assertEqual(profiles['sort_01_distance_trial']['lidar_approach']['target_distance_m'],.17)
        self.assertEqual(profiles['harvest_dock_41']['distance_heading_trial']['heading_source'],'odom_current')
    def test_wait_reverse_search_sequence(self):
        p=InitialMarkerRecovery(self.c,0.)
        self.assertEqual(p.step(1.,(0,0,0),True,False)[3],'WAIT_INITIAL_MARKER')
        self.assertLess(p.step(3.,(0,0,0),True,False)[0],0)
        self.assertEqual(p.step(6.,(-.06,0,0),False,False)[3],'VERIFY_SEARCH_STOP')
        self.assertGreater(p.step(6.1,(-.06,0,0),True,False)[1],0)
        self.assertLess(p.step(8.,(-.06,0,self.c['search_angle_rad']),True,False)[1],0)
        self.assertGreater(p.step(12.,(-.06,0,-self.c['search_angle_rad']),True,False)[1],0)
        with self.assertRaises(TimeoutError):p.step(15.,(-.06,0,0),True,False)
    def test_marker_during_motion_stops_before_release(self):
        p=InitialMarkerRecovery(self.c,0.)
        self.assertEqual(p.step(4.,(0,0,0),False,True)[:3],(0.,0.,False))
        self.assertTrue(p.step(4.5,(0,0,0),True,True,True)[2])
        self.assertTrue(p.step(5.,(0,0,0),True,False)[2])
    def test_timeout_and_invalid_config(self):
        p=InitialMarkerRecovery(self.c,0.)
        with self.assertRaises(TimeoutError):p.step(31.,(0,0,0),True,False)
        with self.assertRaises(ValueError):InitialMarkerRecovery(dict(self.c,reverse_distance_m=-1.),0.)
    def test_existing_operational_policies(self):
        self.assertEqual(self.p['pickup_workflow']['initial_marker_id'],42)
        self.assertEqual(self.p['pickup_workflow']['final_marker_id'],41)
        self.assertEqual(self.p['pickup_workflow']['ready_timeout_s'],300.)
        self.assertTrue(self.p['unload_workflows']['SORT_01']['auto_clear'])
        self.assertFalse(self.p['unload_workflows']['SORT_01']['assume_unload_ready'])
        self.assertEqual(self.p['precision_registry']['profiles']['station_transport_01']['parking']['next_mission'],'direct')
if __name__=='__main__':unittest.main()
