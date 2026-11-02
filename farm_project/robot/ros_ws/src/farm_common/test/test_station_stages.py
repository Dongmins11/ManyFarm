"""실제 그래프와 가짜 구동기로 단계·오차·취소 경계를 검증한다."""
import math
from pathlib import Path
from types import SimpleNamespace as NS
import unittest
import numpy as np
from farm_navigation.route import RouteGraph
from farm_navigation.navigation_types import NavigationSettings
from farm_common.station_stages import staged_geometry, run_stages

ROOT=Path(__file__).resolve().parents[4]
class StationStages(unittest.TestCase):
    def setUp(self):
        self.graph=RouteGraph(ROOT/'config/maps/scout_real/graph.geojson')
        self.opts=dict(strategy='forward_then_reverse',approach_node_id=1,tag_alignment={'enabled':False})
        self.station=self.graph.nodes[19]
    def test_geometry(self):
        a,yaw,p=staged_geometry(self.graph,self.opts,self.station)
        self.assertEqual(p.points[0],a)
        self.assertEqual(p.points[-1],self.station)
        self.assertAlmostEqual(yaw,math.pi/2)
        self.assertAlmostEqual(math.dist(a,self.station),.4)
    def test_tag_enable_not_silent_success(self):
        self.opts['tag_alignment']['enabled']=True
        with self.assertRaises(ValueError):staged_geometry(self.graph,self.opts,self.station)
    def run_case(self, bad_spin=False, cancel=False, drift=False):
        events=[];pose=np.eye(4)
        if drift:self.opts['approach_retry_count']=2
        def update(xy,yaw):
            pose[0,3],pose[1,3]=xy
            pose[:2,:2]=[[math.cos(yaw),-math.sin(yaw)],[math.sin(yaw),math.cos(yaw)]]
        def move(xy,yaw,**kw):
            events.append('reverse' if kw.get('reverse') else 'forward');update(xy,yaw)
        def spin(delta,allowance,check):
            events.append('spin')
            if cancel:raise RuntimeError('cancel')
            if not bad_spin:update(self.graph.nodes[1],math.pi/2)
            if drift and events.count('spin')==1:pose[0,3]+=.1
        forward=NS(plan=lambda xy:self.graph.plan(self.graph.nodes[0],xy,.1,.1),navigate=move)
        args=dict(graph=self.graph,options=self.opts,station_xy=self.station,forward=forward,
                  backward=NS(navigate=move),spin=NS(execute=spin),poses=NS(current=lambda check:pose),
                  motion=NS(wait_stopped=lambda check:events.append('stop')),settings=NavigationSettings(),
                  check=lambda:None,phase=lambda x:None)
        if bad_spin or cancel:
            with self.assertRaises(RuntimeError):run_stages(**args)
            self.assertNotIn('reverse',events)
        else:
            run_stages(**args)
            self.assertLess(events.index('forward'),events.index('spin'))
            self.assertLess(events.index('spin'),events.index('reverse'))
            self.assertEqual(events[-1],'stop')
            if drift:self.assertEqual(events.count('forward'),2)
    def test_order(self):self.run_case()
    def test_spin_drift_reapproaches_before_reverse(self):self.run_case(drift=True)
    def test_rotation_failure_blocks_reverse(self):self.run_case(bad_spin=True)
    def test_cancel_blocks_reverse(self):self.run_case(cancel=True)

    def test_reapproach_before_spin_and_exhaustion(self):
        for misses in (1, 3):
            events=[]; pose=np.eye(4); attempts=[0]
            self.opts['approach_retry_count']=2
            def move(xy,yaw,**kw):
                reverse=kw.get('reverse',False)
                events.append('reverse' if reverse else 'forward')
                if not reverse: attempts[0]+=1
                pose[0,3]=xy[0]+(.085 if not reverse and attempts[0]<=misses else 0)
                pose[1,3]=xy[1]
                pose[:2,:2]=[[math.cos(yaw),-math.sin(yaw)],[math.sin(yaw),math.cos(yaw)]]
            def spin(*args):
                events.append('spin')
                pose[:2,:2]=[[0,-1],[1,0]]
            args=dict(graph=self.graph,options=self.opts,station_xy=self.station,
                forward=NS(plan=lambda xy:self.graph.plan(self.graph.nodes[0],xy,.1,.1),navigate=move),
                backward=NS(navigate=move),spin=NS(execute=spin),poses=NS(current=lambda check:pose),
                motion=NS(wait_stopped=lambda check:None),settings=NavigationSettings(arrival_tolerance_m=.03),
                check=lambda:None,phase=lambda x:None)
            if misses==1:
                run_stages(**args)
                self.assertEqual(events[:3],['forward','forward','spin'])
                self.assertEqual(attempts[0],2)
            else:
                with self.assertRaisesRegex(RuntimeError,'재접근 소진'):run_stages(**args)
                self.assertEqual(events,['forward']*3)

    def test_wall_mode_realigns_without_position_reapproach(self):
        from farm_common.station_stages import align_entry
        pose=np.eye(4);calls=[]
        self.opts['wall_reverse']={'alignment_timeout_s':10.}
        def turn(delta,timeout,check):
            calls.append(delta)
            angle=math.pi/2-(.2 if len(calls)==1 else 0)
            pose[:2,:2]=[[math.cos(angle),-math.sin(angle)],[math.sin(angle),math.cos(angle)]]
            pose[0,3]+=.1  # map 좌표 변경을 별도 위치 재접근으로 처리하지 않는다.
        align_entry(math.pi/2,self.opts,NS(execute=turn),NS(current=lambda c:pose),
                    NS(wait_stopped=lambda c:None),NavigationSettings(heading_tolerance_rad=.0873),lambda:None,lambda s:None)
        self.assertEqual(len(calls),2)

if __name__=='__main__':unittest.main()
