import math,time,threading,unittest
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import patch
import numpy as np,yaml
from farm_common.station_smooth_runtime import StationSmoothWallRuntime
from farm_common.station_wall_control import ArrivalSettler
class RuntimeTests(unittest.TestCase):
    def runtime(self):
        x=StationSmoothWallRuntime.__new__(StationSmoothWallRuntime)
        x.c=yaml.safe_load((Path(__file__).resolve().parents[4]/'config/stations/scout_real.yaml').read_text())['stations']['scout_01']['return_motion']['wall_reverse']
        x.settings=NS(base_frame='base_footprint',stopped_linear_mps=.005,stopped_angular_rps=.02)
        x.lock=threading.Lock();x.active=True;x.worker=None;x.worker_stop=threading.Event()
        x.done=False;x.error=None;x.last_tick=9.95;x.supervisor_at=10.;x.max_tick_gap=0
        x.scan=NS(header=NS(frame_id='base_scan',stamp=NS(sec=10,nanosec=0)))
        x.odom=NS(header=NS(frame_id='odom',stamp=NS(sec=10,nanosec=0)),child_frame_id='base_footprint',
           twist=NS(twist=NS(linear=NS(x=0.,y=0.),angular=NS(z=0.))))
        x.scan_at=x.odom_at=10.;x._fresh=lambda *a:True;x._matrix=lambda m:np.eye(4)
        x.transform=np.eye(4);x.scan_frame='base_scan';x.origin=np.eye(4);x.previous=np.zeros(2)
        x.travel=0.;x.nominal=.4;x.safety_stamp=10.;x.scan_clear=True;x.blend=1.;x.command=(-.05,0.)
        x.cache={};x.analysis_stamp=None;x.analysis=dict(stamp=10.,at=10.,pose=np.eye(4),walls={})
        x.settler=ArrivalSettler(.8,2.,3);x.sent=[];x.pub=NS(publish=lambda m:x.sent.append((m.linear.x,m.angular.z)))
        return x
    def test_no_wall_yet_moves_with_heading(self):
        x=self.runtime();x._control(10);self.assertLess(x.sent[-1][0],0)
    def test_stale_sensor_stops(self):
        x=self.runtime();x._fresh=lambda *a:False;x._control(10)
        self.assertEqual(x.sent[-1],(0,0));self.assertFalse(x.done)
    def test_control_gap_stops(self):
        x=self.runtime();x.last_tick=9.;x._control(10);self.assertEqual(x.state,'WAIT_CONTROL_GAP');self.assertEqual(x.sent[-1],(0,0))
    def test_obstacle_stops(self):
        x=self.runtime();x.scan_clear=False;x._control(10);self.assertEqual(x.sent[-1],(0,0))
    def test_wall_missing_bridges_then_expires(self):
        x=self.runtime();wall=dict(normal_xy=[-1,0],distance_m=.8,angle=0)
        side=dict(normal_xy=[0,1],distance_m=.25,angle=0)
        x.cache={'rear':(wall,np.eye(4),9.4),'left':(side,np.eye(4),9.4)}
        x._control(10);self.assertGreater(x.sent[-1][0],-.05);self.assertLess(x.sent[-1][0],0)
        x.cache={k:(w,p,8.) for k,(w,p,a) in x.cache.items()};x.last_tick=9.95;x._control(10)
        self.assertEqual(x.sent[-1],(0,0))
    def test_predicted_arrival_never_completes(self):
        x=self.runtime();x.cache={'rear':(dict(normal_xy=[-1,0],distance_m=.58,angle=0),np.eye(4),9.8),
          'left':(dict(normal_xy=[0,1],distance_m=.25,angle=0),np.eye(4),9.8)}
        x._control(10);self.assertEqual(x.sent[-1],(0,0));self.assertFalse(x.done);self.assertEqual(x.settler.samples,0)
    def test_fresh_arrival_needs_distinct_samples(self):
        x=self.runtime()
        walls={'rear':dict(normal_xy=[-1,0],distance_m=.58,angle=0),'left':dict(normal_xy=[0,1],distance_m=.25,angle=0)}
        for now in (10.,10.45,10.9):
            x.last_tick=now-.05;x.supervisor_at=now;x.analysis=dict(stamp=now,at=now,pose=np.eye(4),walls=walls)
            x._control(now)
        self.assertTrue(x.done);self.assertEqual(x.sent[-1],(0,0))
    def test_stop_disables_and_zeroes(self):
        x=self.runtime();x.stop();self.assertFalse(x.active);self.assertEqual(x.sent[-1],(0,0));x._tick();self.assertEqual(len(x.sent),1)
