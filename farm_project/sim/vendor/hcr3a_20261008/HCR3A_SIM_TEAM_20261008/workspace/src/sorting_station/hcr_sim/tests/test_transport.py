import unittest
import math
import numpy as np
from types import SimpleNamespace
from hcr_sim.model import load_config
from hcr_sim.transport import Transport
from hcr_sim.transport_asset import geometry


class TransportRecoveryTests(unittest.TestCase):
    def make_transport(self):
        t = Transport.__new__(Transport)
        t.cfg = load_config()
        t.c = dict(t.cfg['transport'], tip_deg=45, rock_cycles=1,
                   rock_min_deg=5, rock_seconds=3)
        t.geometry = geometry()
        t.phase, t.since, t.rock_remaining = 'SETTLE', 0, 1
        t.x, t.angle, t.gate = .695, math.radians(45), math.pi/2
        t.error, t.events, t.fruits, t.dump_snapshot = '', [], [], None
        t.asset = {'set_pose': lambda *pose: self.assertTrue(
            0 <= pose[1] <= t.geometry['limits']['box_tilt_joint'])}
        t.all_on_intake = lambda: False
        return t

    def test_rocking_is_bounded_and_ready_requires_complete_dump(self):
        t = self.make_transport()
        t.tick(3)
        self.assertEqual(t.phase, 'ROCK_DOWN')
        self.assertFalse(t.ready)
        t.tick(4.5)
        self.assertAlmostEqual(math.degrees(t.angle), 25)
        t.tick(6)
        self.assertEqual(t.phase, 'ROCK_UP')
        t.tick(7.5)
        self.assertAlmostEqual(math.degrees(t.angle), 25)
        t.tick(9)
        self.assertEqual(t.phase, 'DUMP')
        t.tick(15)
        self.assertEqual(t.phase, 'SETTLE')
        self.assertEqual(t.rock_remaining, 0)
        self.assertFalse(t.ready)
        t.all_on_intake = lambda: True
        t.tick(18)
        self.assertTrue(t.ready)
        self.assertTrue(t.dump_snapshot['all_on_intake'])

    def test_exhausted_rocking_preserves_dump_failure(self):
        t = self.make_transport()
        t.rock_remaining = 0
        t.tick(t.c['timeout_seconds'])
        self.assertEqual(t.phase, 'ERROR')
        self.assertIn('TRANSPORT_DUMP_INCOMPLETE', t.error)
        self.assertIsNone(t.dump_snapshot)

    def test_start_waits_for_inside_and_settled_loading(self):
        t = self.make_transport()
        t.phase = 'LOADING'
        t.start_requested, t.loading_stable_since, t.loading_snapshot = False, None, None
        t.loading_status = lambda: dict(all_inside=False, settled=False, bodies=[])
        t.start(0)
        self.assertTrue(t.start_requested)
        t.tick(4)
        self.assertEqual(t.phase, 'LOADING')
        t.loading_status = lambda: dict(all_inside=True, settled=False, bodies=[])
        t.tick(4.5)
        self.assertEqual(t.phase, 'LOADING')
        t.loading_status = lambda: dict(all_inside=True, settled=True, bodies=[])
        t.tick(5)
        self.assertEqual(t.phase, 'LOADING')
        t.tick(5.5)
        self.assertEqual(t.phase, 'APPROACH')
        self.assertTrue(t.loading_snapshot['all_inside'])

    def test_loading_failure_does_not_start_transport(self):
        t = self.make_transport()
        t.phase = 'LOADING'
        t.start_requested, t.loading_stable_since, t.loading_snapshot = True, None, None
        t.loading_status = lambda: dict(all_inside=False, settled=True, bodies=[])
        t.tick(12)
        self.assertEqual(t.phase, 'ERROR')
        self.assertIn('TRANSPORT_LOADING_FAILED', t.error)

    def test_near_intake_but_still_inside_box_does_not_count_as_dumped(self):
        class Value:
            def __init__(self, value): self.value = np.asarray(value)
            def cpu(self): return self
            def numpy(self): return self.value
        t = self.make_transport()
        from hcr_sim.model import ramp_surface_z
        t.fruits = [dict(loading_points=np.array([[-.01, -.01, -.01], [.01, .01, .01]]),
            object=SimpleNamespace(data=SimpleNamespace(
                root_pos_w=[Value([.705, .0625, ramp_surface_z(t.cfg, .705)+.04])],
                root_quat_w=[Value([1, 0, 0, 0])])))]
        # This root satisfies the old intake-range-only check, but its body
        # has not crossed the original box front plane.
        del t.all_on_intake  # Use the real method instead of the recovery fixture.
        self.assertFalse(t.all_on_intake())
        t.fruits[0]['object'].data.root_pos_w = [Value([.35, .0625, ramp_surface_z(t.cfg, .35)+.04])]
        self.assertTrue(t.all_on_intake())


if __name__ == '__main__':
    unittest.main()
