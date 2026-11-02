"""관측·후진 부호·정지 판정·벽 교체 방지 회귀 시험."""
import math
from pathlib import Path
import unittest
import numpy as np
import yaml
from farm_common.station_wall_control import observe_walls, StableWalls, reverse_command, arrival_matches

ROOT=Path(__file__).resolve().parents[4]
class WallControlTests(unittest.TestCase):
    def setUp(self):
        self.c=yaml.safe_load((ROOT/'config/stations/scout_real.yaml').read_text())['stations']['scout_01']['return_motion']['wall_reverse']
    def points(self,rear=.5748):
        x=np.linspace(-.5,.15,90);y=np.linspace(-.2472,.2493,90)
        return np.vstack([np.c_[x,np.full_like(x,.2493)],np.c_[x,np.full_like(x,-.2472)],np.c_[np.full_like(y,-rear),y]])
    def test_observe_three_walls_and_arrival(self):
        w=observe_walls(self.points(),self.c)
        self.assertEqual(set(w),{'left','right','rear'})
        self.assertTrue(arrival_matches(self.c,w))
        self.assertEqual(reverse_command(self.c,w,0,1)[:2],(0.,0.))
    def test_no_wall_keeps_odom_heading(self):
        v,w,state=reverse_command(self.c,{},.05,0)
        self.assertEqual(v,-.05);self.assertGreater(w,0);self.assertEqual(state,'REVERSE_ODOM')
        self.assertFalse(arrival_matches(self.c,{}))
    def test_reverse_lateral_sign_and_angular_limit(self):
        walls=observe_walls(self.points(.9),self.c)
        walls['left']['distance_m']-=.06;walls['right']['distance_m']+=.06
        v,w,_=reverse_command(self.c,walls,0,1)
        self.assertLess(v,0);self.assertGreater(w,0);self.assertLessEqual(abs(w),self.c['max_angular_rps'])
    def test_deceleration_and_no_forward_overshoot(self):
        walls=observe_walls(self.points(.615),self.c)
        v,_,_=reverse_command(self.c,walls,0,1)
        self.assertGreater(v,-.05)
        walls['rear']['distance_m']=.5
        self.assertEqual(reverse_command(self.c,walls,0,1)[:2],(0.,0.))
        self.assertFalse(arrival_matches(self.c,walls))
    def test_independent_scans_and_plane_continuity(self):
        w=observe_walls(self.points(),self.c);t=StableWalls(self.c);m=np.eye(4)
        self.assertFalse(t.update(w,m,1.))
        self.assertFalse(t.update(w,m,1.))
        self.assertFalse(t.update(w,m,1.1))
        self.assertEqual(set(t.update(w,m,1.2)),set(w))
        w['rear']['distance_m']+=.2
        self.assertNotIn('rear',t.update(w,m,1.3))
    def test_odom_translation_preserves_plane(self):
        w=observe_walls(self.points(.7),self.c);t=StableWalls(self.c);m=np.eye(4)
        t.update(w,m,1.)
        m[0,3]=-.02;w=observe_walls(self.points(.68),self.c)
        t.update(w,m,1.1)
        self.assertIn('rear',t.update(w,m,1.2))

if __name__=='__main__':unittest.main()
