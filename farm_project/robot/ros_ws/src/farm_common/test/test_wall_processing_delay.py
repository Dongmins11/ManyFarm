import unittest
import numpy as np
from farm_common.station_wall_control import StableWalls,ArrivalSettler

class DelayTests(unittest.TestCase):
    def tracker(self):
        return StableWalls(dict(walls={"rear": {}},max_age_s=.5,tracking_gap_s=2.,stable_frames=3,plane_angle_jump_rad=.17,plane_jump_m=.06))
    def test_slow_processing_can_acquire(self):
        t=self.tracker();w={'rear':dict(normal_xy=[-1.,0.],distance_m=.58)}
        self.assertFalse(t.update(w,np.eye(4),1))
        self.assertFalse(t.update(w,np.eye(4),1.7))
        self.assertIn('rear',t.update(w,np.eye(4),2.4))
        self.assertNotIn('rear',t.update(w,np.eye(4),5))
    def test_plane_jump_still_rejected(self):
        t=self.tracker();w={'rear':dict(normal_xy=[-1.,0.],distance_m=.58)}
        for s in (1,1.7,2.4):t.update(w,np.eye(4),s)
        w['rear']['distance_m']=1.
        self.assertFalse(t.update(w,np.eye(4),3))
    def test_delayed_valid_samples_need_three(self):
        s=ArrivalSettler(.8,2.,3)
        self.assertFalse(s.observe(1,1,True))
        self.assertFalse(s.observe(2,2,True))
        self.assertTrue(s.observe(3,3,True))
    def test_pause_not_counted_and_long_gap_resets(self):
        s=ArrivalSettler(.8,2.,3)
        s.observe(1,1,True);s.observe(1.4,1.4,True);s.pause(2)
        self.assertFalse(s.observe(2.5,2.5,True));self.assertAlmostEqual(s.elapsed,.4)
        self.assertTrue(s.observe(3,3,True))
        s.pause(6);self.assertEqual(s.elapsed,0)
    def test_invalid_and_repeated_scan_after_pause_reset(self):
        s=ArrivalSettler(.8,2.,3);s.observe(1,1,True);s.pause(1.1)
        self.assertFalse(s.observe(1,1.2,True));self.assertEqual(s.samples,0)
        s.observe(2,2,True);self.assertFalse(s.observe(3,3,False));self.assertEqual(s.samples,0)
