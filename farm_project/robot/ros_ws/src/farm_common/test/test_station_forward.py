"""전진 조향 부호, 실측 완료, 경로→접근→회전 순서를 무주행 검증한다."""
import math, unittest
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import Mock
import numpy as np, yaml
from farm_common.station_wall_control import forward_command, forward_arrival_matches, observe_walls
from farm_common.station_forward_stages import forward_geometry, run_forward_stages
from farm_common.station_smooth_control import predict_wall
from farm_navigation.route import RouteGraph
ROOT=Path(__file__).resolve().parents[4]
class ForwardTests(unittest.TestCase):
    def setUp(self):
        self.options=yaml.safe_load((ROOT/'config/stations/scout_real.yaml').read_text())['stations']['scout_01']['return_motion']
        self.c=self.options['wall_forward'];self.graph=RouteGraph(ROOT/'config/maps/scout_real/graph.geojson')
    def walls(self):
        return {n:dict(distance_m=c['target_m'],angle=c['target_angle_rad']) for n,c in self.c['walls'].items()}
    def test_forward_steers_toward_left_when_too_far_from_left(self):
        w=self.walls();w.pop('right');w['left']['distance_m']+=.05;w['front']['distance_m']+=.2
        v,a,s=forward_command(self.c,w,0,1);self.assertGreater(v,0);self.assertGreater(a,0)
    def test_forward_steers_right_when_too_close_to_left(self):
        w=self.walls();w.pop('right');w['left']['distance_m']-=.05;w['front']['distance_m']+=.2
        v,a,s=forward_command(self.c,w,0,1);self.assertGreater(v,0);self.assertLess(a,0)
    def test_front_stop_and_angles(self):
        w=self.walls();self.assertEqual(forward_command(self.c,w,0,1)[:2],(0,0));self.assertTrue(forward_arrival_matches(self.c,w))
        w['front']['angle']+=.2;self.assertFalse(forward_arrival_matches(self.c,w))
    def test_missing_front_not_complete(self):
        w=self.walls();del w['front'];self.assertFalse(forward_arrival_matches(self.c,w))
    def test_front_prediction(self):
        p=np.eye(4);p[0,3]=.1
        w=predict_wall(dict(normal_xy=[1,0],distance_m=.5),np.eye(4),p,'front')
        self.assertAlmostEqual(w['distance_m'],.4);self.assertAlmostEqual(w['angle'],0)
    def test_fit_front_plane(self):
        points=np.array([[.36,y] for y in np.linspace(-.2,.2,60)])
        w=observe_walls(points,self.c);self.assertIn('front',w);self.assertNotIn('rear',w)
    def test_geometry(self):
        point,entry,exit=forward_geometry(self.graph,self.options,self.graph.nodes[19])
        self.assertEqual(point,self.graph.nodes[19]);self.assertAlmostEqual(entry,-math.pi/2);self.assertAlmostEqual(exit,math.pi/2)
    def run_stages_case(self,fail=False):
        events=[];pose=np.eye(4)
        def heading(yaw):pose[:2,:2]=[[math.cos(yaw),-math.sin(yaw)],[math.sin(yaw),math.cos(yaw)]]
        def navigate(xy,yaw,**kw):events.append('route');pose[:2,3]=xy;heading(yaw)
        def turn(delta,*args):events.append('turn');heading(math.atan2(pose[1,0],pose[0,0])+delta)
        def dock(*args):
            events.append('wall')
            if fail:raise RuntimeError('sensor failure')
        wall=NS(execute=dock,stop=lambda:events.append('wall_stop'))
        args=dict(graph=self.graph,options=self.options,station_xy=self.graph.nodes[19],
            forward=NS(plan=lambda p:NS(points=[self.graph.nodes[1],p]),navigate=navigate),
            spin=NS(execute=turn),poses=NS(current=lambda c:pose),motion=NS(wait_stopped=lambda c:events.append('stop')),
            settings=NS(arrival_tolerance_m=.03,heading_tolerance_rad=math.radians(5)),check=lambda:None,phase=lambda s:events.append(s),wall_runtime=wall)
        if fail:
            with self.assertRaises(RuntimeError):run_forward_stages(**args)
            self.assertNotIn('turn',events)
        else:
            run_forward_stages(**args)
            self.assertLess(events.index('route'),events.index('wall'));self.assertLess(events.index('wall_stop'),events.index('turn'))
            self.assertEqual(events[-1],'STATION_DOCKED_EXIT_ALIGNED')
            self.assertAlmostEqual(math.atan2(pose[1,0],pose[0,0]),math.pi/2)
    def test_sequence(self):self.run_stages_case()
    def test_approach_failure_no_final_turn(self):self.run_stages_case(True)

class ForwardRuntimeTests(unittest.TestCase):
    def runtime(self):
        from test_station_smooth_runtime import RuntimeTests
        x=RuntimeTests().runtime()
        x.c=yaml.safe_load((ROOT/'config/stations/scout_real.yaml').read_text())['stations']['scout_01']['return_motion']['wall_forward']
        x.command=(.05,0.)
        return x
    def test_runtime_publishes_positive_linear(self):
        x=self.runtime();x._control(10);self.assertGreater(x.sent[-1][0],0)
    def test_front_prediction_cannot_complete(self):
        x=self.runtime()
        x.cache={'front':(dict(normal_xy=[1,0],distance_m=.36,angle=0),np.eye(4),9.8),
                 'left':(dict(normal_xy=[0,1],distance_m=.244,angle=0),np.eye(4),9.8)}
        x._control(10);self.assertEqual(x.sent[-1],(0,0));self.assertFalse(x.done)
    def test_fresh_front_samples_complete(self):
        x=self.runtime()
        walls={n:dict(normal_xy=([1,0] if n=='front' else [0,1]),distance_m=v['target_m'],angle=v['target_angle_rad']) for n,v in x.c['walls'].items() if n!='right'}
        for now in (10.,10.45,10.9):
            x.last_tick=now-.05;x.supervisor_at=now;x.analysis=dict(stamp=now,at=now,pose=np.eye(4),walls=walls)
            x._control(now)
        self.assertTrue(x.done);self.assertEqual(x.sent[-1],(0,0))
