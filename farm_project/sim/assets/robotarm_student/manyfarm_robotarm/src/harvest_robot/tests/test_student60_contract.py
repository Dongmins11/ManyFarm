import sys
from pathlib import Path
import unittest
import numpy as np

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from harvest_runtime.student60_contract import encode_targets,decode_targets,summarize_observations
from harvest_sensors.deployment import PhysicsCaptureClock


class ContractTests(unittest.TestCase):
    def test_executed_target_roundtrip_and_no_clipping(self):
        lower=np.array([-2,-1,-1,-2,-3,0.]);upper=np.array([2,2,2,2,3,1.7])
        target=np.array([.2,.1,-.2,.3,-.7,1.2])
        np.testing.assert_allclose(decode_targets(encode_targets(target,lower,upper),lower,upper),target,atol=2e-7)
        with self.assertRaises(ValueError):encode_targets(upper+.01,lower,upper)
        with self.assertRaises(ValueError):decode_targets(np.full(6,1.1),lower,upper)

    def test_camera60_physics30_capture20_control(self):
        clock=PhysicsCaptureClock(1/60)
        self.assertEqual(clock.stride,2)
        numbers=[];ages=[]
        for control in range(6):
            numbers.append(clock.sequence);ages.append(clock.time-clock.stamp)
            for _ in range(3):clock.advance(1/60)
        self.assertEqual(numbers,[0,1,3,4,6,7])
        np.testing.assert_allclose(ages,[0,1/60,0,1/60,0,1/60],atol=1e-12)
        clock.reset();self.assertEqual(clock.sequence,0)

    def test_stale_valid_is_not_fresh(self):
        rows=[dict(phase='approach',target=dict(valid=v,age_s=age),target_error_m=e)
              for v,age,e in [(True,.15,.03),(False,.3,None),(False,.3,None),(True,0.,.01)]]
        summary=summarize_observations(rows)['approach']
        self.assertEqual(summary['valid'],2);self.assertEqual(summary['fresh'],1)
        self.assertAlmostEqual(summary['max_invalid_s'],.1)


if __name__=='__main__':unittest.main()
