"""세 bool 광축의 통과·중복·취소와 자산 배치 수식을 검증한다."""
from pathlib import Path
import sys
import unittest
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'ros_ws/src/farm_sim_devices'))
from farm_sim_devices.basket_laser import PassageCounter, beam_segments


class PassageTests(unittest.TestCase):
    def setUp(self) -> None:
        self.counter = PassageCounter(.05, 2.)
        self.now = 0.

    def samples(self, bits=(False, False, False), steps: int = 1) -> list[dict]:
        events = []
        for _ in range(steps):
            self.now += 1/60
            event = self.counter.update(bits, self.now)
            if event is not None: events.append(event)
        return events

    def ready(self) -> None:
        self.counter.arm(); self.samples(steps=5)
        self.assertEqual(self.counter.state, 'READY')

    def passage(self, bits=(True, False, False)) -> list[dict]:
        self.samples(bits, 2)
        return self.samples(steps=5)

    def test_each_single_beam_can_count(self) -> None:
        for i in range(3):
            self.ready()
            events = self.passage(tuple(j == i for j in range(3)))
            self.assertEqual(len(events), 1)
            self.assertEqual(events[0]['beams_seen'], [i+1])
            self.assertFalse(events[0]['identity_confirmed'])
            self.assertFalse(events[0]['direction_confirmed'])
            self.assertNotIn('target_id', events[0])
        self.assertEqual(self.counter.total, 3)

    def test_all_three_beams_count_only_once(self) -> None:
        self.ready()
        events = self.passage((True, True, True))
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]['beams_seen'], [1,2,3])
        self.assertEqual(self.counter.total, 1)

    def test_cross_beam_chatter_merges_until_all_clear_50ms(self) -> None:
        self.ready(); self.samples((True, False, False)); self.samples(steps=2)
        self.samples((False, False, True)); self.samples(steps=3)
        self.assertEqual(self.counter.total, 0)
        event = self.samples(steps=2)[0]
        self.assertEqual(event['beams_seen'], [1,3])
        self.assertEqual(self.counter.total, 1)

    def test_initial_block_requires_clear_then_new_block(self) -> None:
        self.counter.arm(); self.samples((True, True, True), 10); self.samples(steps=5)
        self.assertEqual(self.counter.total, 0)
        self.assertEqual(len(self.passage()), 1)

    def test_disarmed_and_canceled_passage_cannot_count(self) -> None:
        self.assertEqual(self.passage(), [])
        self.ready(); self.samples((True, False, False)); self.counter.disarm()
        self.assertEqual(self.samples(steps=10), [])
        self.assertEqual(self.counter.total, 0)

    def test_timeout_is_not_a_success(self) -> None:
        self.ready(); self.samples((True, False, False), 130); self.samples(steps=10)
        self.assertEqual(self.counter.state, 'REJECTED')
        self.assertEqual(self.counter.total, 0)

    def test_bounce_and_repeat_require_next_explicit_attempt(self) -> None:
        self.ready(); self.passage(); self.passage((True, True, True))
        self.assertEqual(self.counter.total, 1)
        self.ready(); self.passage()
        self.assertEqual(self.counter.total, 2)

    def test_empty_basket_is_not_success(self) -> None:
        self.ready(); self.samples(steps=200)
        self.assertEqual(self.counter.total, 0)

    def test_invalid_and_replayed_input_fails(self) -> None:
        for bits, now in [([1,False,False],1.), ([True,False],1.), ([False]*3,float('nan'))]:
            with self.assertRaises(ValueError): self.counter.update(bits, now)
        self.counter.update([False]*3, 1.)
        with self.assertRaises(ValueError): self.counter.update([False]*3, 1.)

    def test_layout_190mm_opening(self) -> None:
        settings = dict(x_fractions=[.25,.5,.75], height_offset_m=-.005, end_inset_m=.007)
        starts, ends = beam_segments([-.095,-.095,.005], [.095,.095,.2], settings)
        np.testing.assert_allclose(starts[:,0], [-.0475,0,.0475])
        np.testing.assert_allclose(starts[:,1:], [[-.088,.195]]*3)
        np.testing.assert_allclose(ends[:,1:], [[.088,.195]]*3)
        for change in [dict(x_fractions=[.25,.5,.5]), dict(height_offset_m=.005), dict(end_inset_m=.1)]:
            with self.assertRaises(ValueError): beam_segments([-.095]*3,[.095]*3,dict(settings, **change))


if __name__ == '__main__': unittest.main()
