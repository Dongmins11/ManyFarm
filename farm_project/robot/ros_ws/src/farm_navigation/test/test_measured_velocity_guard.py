"""실패 odom 재생 및 비정상 입력. 실제 ROS/물리 정지 검증과 구분한다."""
from pathlib import Path
import json
import unittest
from farm_navigation.measured_velocity_guard import MeasuredVelocityGuard,MeasuredVelocityLimits

class GuardTest(unittest.TestCase):
    def make(self):return MeasuredVelocityGuard(MeasuredVelocityLimits(.025,.005,.18,.20,.10,.5))
    def sample(self,g,t,w=.1,v=-.01):g.observe(1000000000+int(t*1e9),v,w)
    def test_failure_record(self):
        data=json.loads((Path(__file__).parent/'data/arc_odom_failure_20261020.json').read_text())
        self.assertEqual(sum(v>.005 or abs(v)>.025 or abs(w)>.18 for _,v,_,w in data),2)
        g=self.make()
        for t,v,y,w in data:g.observe(t,v,w)
        self.assertFalse(g.error);self.assertEqual(len(g.events),2)
    def test_sustained(self):
        g=self.make();self.sample(g,0,.19);self.sample(g,.05,.19)
        with self.assertRaisesRegex(RuntimeError,'지속'):self.sample(g,.10,.19)
    def test_hard(self):
        with self.assertRaisesRegex(RuntimeError,'순간'):self.sample(self.make(),0,.201)
    def test_exact_hard_still_duration_limited(self):
        g=self.make();self.sample(g,0,.20)
        with self.assertRaises(RuntimeError):self.sample(g,.1,.20)
    def test_soft_boundary(self):
        g=self.make()
        for i in range(30):self.sample(g,i*.03,.18)
        self.assertFalse(g.events)
    def test_reset_short_excursion(self):
        g=self.make();self.sample(g,0,.19);self.sample(g,.05,.1);self.sample(g,.1,.19);self.sample(g,.15,.1)
        self.assertFalse(g.error)
    def test_forward(self):
        with self.assertRaises(RuntimeError):self.sample(self.make(),0,v=.006)
    def test_reverse_fast(self):
        with self.assertRaises(RuntimeError):self.sample(self.make(),0,v=-.026)
    def test_negative_hard(self):
        with self.assertRaises(RuntimeError):self.sample(self.make(),0,w=-.201)
    def test_nan(self):
        with self.assertRaises(RuntimeError):self.sample(self.make(),0,w=float('nan'))
    def test_infinite_linear(self):
        with self.assertRaises(RuntimeError):self.sample(self.make(),0,v=float('inf'))
    def test_latched(self):
        g=self.make()
        with self.assertRaises(RuntimeError):self.sample(g,0,.3)
        with self.assertRaises(RuntimeError):self.sample(g,.1,.1)
    def test_duplicate(self):
        g=self.make();self.sample(g,0)
        with self.assertRaises(RuntimeError):self.sample(g,0)
    def test_reversed_time(self):
        g=self.make();self.sample(g,.2)
        with self.assertRaises(RuntimeError):self.sample(g,.1)
    def test_gap(self):
        g=self.make();self.sample(g,0)
        with self.assertRaises(RuntimeError):self.sample(g,.51)
    def test_invalid_policy(self):
        with self.assertRaises(ValueError):MeasuredVelocityLimits(.025,.005,.2,.18,.1,.5)

if __name__=='__main__':unittest.main()
