"""실물 복귀 완료 검증: 공백은 누적하지 않고 정상 관측만 누적한다."""
import unittest
from farm_common.station_wall_control import ArrivalSettler

class ArrivalSettlerTests(unittest.TestCase):
    def ready(self):
        s=ArrivalSettler(.8,.5)
        for t in (0.,.2,.4):self.assertFalse(s.observe(t,t,True))
        return s
    def test_short_gap_preserves_without_counting(self):
        s=self.ready();s.pause(.5)
        self.assertFalse(s.observe(.7,.7,True));self.assertAlmostEqual(s.elapsed,.4)
        self.assertFalse(s.observe(.9,.9,True))
        self.assertTrue(s.observe(1.11,1.11,True))
    def test_repeated_pause_cannot_extend_grace(self):
        s=self.ready()
        for t in (.5,.7,1.):s.pause(t)
        self.assertEqual(s.elapsed,0.)
        self.assertFalse(s.observe(1.1,1.1,True))
    def test_unnoticed_long_gap_resets(self):
        s=self.ready();self.assertFalse(s.observe(2.,2.,True));self.assertEqual(s.elapsed,0.)
    def test_outside_tolerance_or_motion_resets(self):
        s=self.ready();self.assertFalse(s.observe(.6,.6,False));self.assertEqual(s.elapsed,0.)
    def test_duplicate_or_reverse_stamp_cannot_complete(self):
        for stamp in (.4,.3):
            s=self.ready();self.assertFalse(s.observe(stamp,.5,True));self.assertEqual(s.elapsed,0.)
    def test_continuous_observations_complete(self):
        s=self.ready();self.assertFalse(s.observe(.6,.6,True));self.assertTrue(s.observe(.81,.81,True))
    def test_clock_jump_cannot_complete(self):
        s=self.ready();self.assertFalse(s.observe(10.,.5,True));self.assertEqual(s.elapsed,0.)

if __name__=='__main__':unittest.main()
