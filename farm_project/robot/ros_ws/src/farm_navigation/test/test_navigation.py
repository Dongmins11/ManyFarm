"""주행 장치 없이 그래프·환경·경로 변환 및 종료 계약을 검증합니다."""
from pathlib import Path
import json
import math
import tempfile
import unittest
from types import SimpleNamespace as NS
import numpy as np
from builtin_interfaces.msg import Time
from farm_navigation.route import RouteGraph
from farm_navigation.path_builder import build_path
from farm_navigation.navigation_types import NavigationSettings
from farm_navigation.navigator import Navigator


def graph_data(nodes, edges, multi=False):
    features=[{'geometry':{'type':'Point','coordinates':xy},'properties':{'id':n,'frame':'map'}} for n,xy in nodes.items()]
    for index,(a,b) in enumerate(edges):
        line=[nodes[a],nodes[b]]
        features.append({'geometry':{'type':'MultiLineString' if multi else 'LineString','coordinates':[line] if multi else line},'properties':{'id':index,'startid':a,'endid':b}})
    return {'type':'FeatureCollection','features':features}


class GraphTests(unittest.TestCase):
    def load(self, data):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup)
        path=Path(temp.name)/'graph.geojson';path.write_text(json.dumps(data))
        return RouteGraph(path)

    def test_different_ids_coordinates_formats_same_logic(self):
        for ids,offset,multi in [([1,2,3],0,False),(['a','b','c'],17,True)]:
            nodes={ids[0]:[offset,0],ids[1]:[offset+4,0],ids[2]:[offset+4,3]}
            graph=self.load(graph_data(nodes,list(zip(ids,ids[1:])),multi))
            plan=graph.plan((offset+1,0),(offset+4,2))
            self.assertEqual(plan.points,((offset+1,0),(offset+4,0),(offset+4,2)))
            self.assertEqual(plan.distance_m,5)
            self.assertEqual(plan.edge_ids,('0','1'))

    def test_reverse_rejected_and_direct_edge_supported(self):
        graph=self.load(graph_data({1:[0,0],2:[4,0]},[(1,2)]))
        self.assertEqual(graph.plan((1,0),(2,0)).distance_m,1)
        with self.assertRaisesRegex(ValueError,'방향 경로'):graph.plan((2,0),(1,0))

    def test_disconnected_and_off_graph_rejected(self):
        graph=self.load(graph_data({1:[0,0],2:[4,0],3:[0,2],4:[4,2]},[(1,2),(3,4)]))
        with self.assertRaises(ValueError):graph.plan((1,0),(2,2))
        with self.assertRaises(ValueError):graph.plan((1,.5),(2,0))
        with self.assertRaises(ValueError):graph.plan((1,0),(2,.1))

    def test_nearest_parallel_lane_not_snapped_across(self):
        graph=self.load(graph_data({1:[0,0],2:[4,0],3:[0,.05],4:[4,.05]},[(1,2),(3,4)]))
        with self.assertRaises(ValueError):graph.plan((1,.001),(2,.05))

    def test_zero_length_and_unknown_endpoint_rejected(self):
        for nodes in ({1:[0,0],2:[0,0]}, {1:[0,0]}):
            data=graph_data({1:[0,0],2:[1,0]},[(1,2)])
            data['features'][:2]=[{'geometry':{'type':'Point','coordinates':xy},'properties':{'id':n}} for n,xy in nodes.items()]
            with self.assertRaises(ValueError):self.load(data)

    def test_shortest_branch(self):
        graph=self.load(graph_data({0:[-1,0],1:[0,0],2:[1,1],3:[1,0],4:[2,0],5:[3,0]},[(0,1),(1,2),(2,4),(1,3),(3,4),(4,5)]))
        plan=graph.plan((-.5,0),(2.5,0))
        self.assertEqual(plan.edge_ids,('0','3','4','5'))
        self.assertAlmostEqual(plan.distance_m,3)

    def test_path_spacing_and_final_heading(self):
        graph=self.load(graph_data({1:[0,0],2:[1,0],3:[1,1]},[(1,2),(2,3)]))
        plan=graph.plan((.2,0),(1,.5));path=build_path(plan,math.pi,Time(sec=42),.04)
        points=[(p.pose.position.x,p.pose.position.y) for p in path.poses]
        self.assertLessEqual(max(math.dist(a,b) for a,b in zip(points,points[1:])),.0400001)
        self.assertEqual(points[-1],(1,.5));self.assertEqual(path.header.stamp.sec,42)
        self.assertAlmostEqual(path.poses[-1].pose.orientation.z,1)

    def test_settings_reject_nan_unknown_and_invalid_mode(self):
        for data in ({'goal_timeout_s':float('nan')},{'mode':'demo'},{'unknown':1},{'settle_s':30}):
            with self.assertRaises(ValueError):NavigationSettings.from_mapping(data)

    def test_interrupted_motion_requires_confirmed_stop(self):
        class Client:
            has_goal=False
            def execute(self,*args):self.has_goal=True;raise RuntimeError('interrupted')
            def cancel(self):self.has_goal=False
        count=[]
        def stopped(check):count.append(1);raise RuntimeError('stale odom')
        navigator=Navigator(NS(),NavigationSettings(),Client(),NS(),NS(wait_stopped=stopped),lambda:None)
        with self.assertRaisesRegex(RuntimeError,'interrupted'):navigator.navigate((1,0),0)
        with self.assertRaisesRegex(RuntimeError,'종료'):navigator.navigate((2,0),0)
        with self.assertRaisesRegex(RuntimeError,'stale'):navigator.cancel_nav()
        with self.assertRaisesRegex(RuntimeError,'종료'):navigator.navigate((2,0),0)
        self.assertEqual(len(count),1)

    def test_result_includes_request_and_settled_pose(self):
        client=NS(has_goal=False,execute=lambda *args:4)
        tf=np.eye(4);tf[0,3]=1
        poses=NS(lookup=lambda *args:tf)
        navigator=Navigator(NS(),NavigationSettings(),client,poses,NS(wait_stopped=lambda check:123),lambda:None)
        result=navigator.navigate((1,0),0)
        self.assertEqual(result.stamp_ns,123)
        self.assertTrue(result.request_id)
        self.assertEqual(navigator.status.phase,'ARRIVED')
        self.assertEqual(result.measurement['position_error_m'],0)


if __name__=='__main__':unittest.main(verbosity=2)
