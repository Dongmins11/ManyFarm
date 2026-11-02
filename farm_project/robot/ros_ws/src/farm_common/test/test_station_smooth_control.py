import math
import unittest
import numpy as np
from farm_common.station_smooth_control import predict_wall,continuation_scale,ramp_command
class SmoothTests(unittest.TestCase):
    def test_reverse_updates_rear_distance(self):
        old=np.eye(4);now=np.eye(4);now[0,3]=-.1
        w=predict_wall(dict(normal_xy=[-1,0],distance_m=.7),old,now,'rear')
        self.assertAlmostEqual(w['distance_m'],.6);self.assertAlmostEqual(w['angle'],0)
    def test_yaw_and_lateral_are_transformed(self):
        now=np.eye(4);a=.1;now[:2,:2]=[[math.cos(a),-math.sin(a)],[math.sin(a),math.cos(a)]];now[1,3]=.02
        w=predict_wall(dict(normal_xy=[0,1],distance_m=.25),np.eye(4),now,'left')
        self.assertAlmostEqual(w['distance_m'],.23);self.assertAlmostEqual(w['angle'],-.1)
    def test_continuation_expires(self):
        self.assertEqual(continuation_scale(.2,.25,1),1)
        self.assertAlmostEqual(continuation_scale(.625,.25,1),.5)
        self.assertEqual(continuation_scale(1.1,.25,1),0)
    def test_ramp_limits_acceleration_and_late_ticks(self):
        v,w=ramp_command((0,0),(-.05,.12),.05,.03,.08,.3)
        self.assertAlmostEqual(v,-.0015);self.assertAlmostEqual(w,.015)
        v,w=ramp_command((-.05,.12),(0,0),10,.03,.08,.3)
        self.assertAlmostEqual(v,-.042);self.assertAlmostEqual(w,.09)
