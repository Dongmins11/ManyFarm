"""주변 과실 합집합과 전역 주기 전환의 시간·속도 계약을 Isaac 없이 검사합니다."""
from pathlib import Path
import sys
import unittest

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'sim/ros_ws/src/farm_sim_runtime'))
from farm_sim_runtime.harvest_regions import HarvestRegions, RegionSettings


class HarvestRegionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.regions = HarvestRegions(RegionSettings.from_mapping({}, 60))

    def hz(self, now: float, velocities: object = (), *, requested: bool = False,
           attached_active: bool = False) -> int:
        """분리 과실의 실제 동역학 유지 여부와 별도로 요청 주기만 확인합니다."""
        return self.regions.required_hz(now, requested=requested, attached_active=attached_active,
                                        detached_velocities=np.asarray(velocities, dtype=float))

    def test_two_harvesters_union_and_one_stopping_preserves_other(self) -> None:
        positions = np.array([[.4, 0., 0.], [3.6, 0., 0.], [2., 0., 0.], [4., .7, 0.]])
        centers = {'harvest_01': np.array([0., 0., 0.]), 'harvest_02': np.array([4., 0., 0.])}
        active = np.zeros(4, dtype=bool)
        selected = self.regions.select(positions, centers, active)
        np.testing.assert_array_equal(selected, [0, 1, 3])
        self.assertEqual(self.hz(0., requested=bool(centers)), 480)
        active[selected] = True
        del centers['harvest_01']
        np.testing.assert_array_equal(self.regions.select(positions, centers, active), [1, 3])
        self.assertEqual(self.hz(.1, requested=bool(centers)), 480)
        self.assertEqual(self.hz(.2, requested=False), 60)

    def test_activation_and_retention_boundaries_are_inclusive(self) -> None:
        positions = np.array([[x, 0., 0.] for x in (.799999, .8, .800001, .999999, 1., 1.000001)])
        active = np.array([False, False, False, True, True, True])
        np.testing.assert_array_equal(self.regions.select(positions, {'arm': np.zeros(3)}, active), [0, 1, 3, 4])

    def test_hysteresis_requires_inner_entry_then_outer_exit(self) -> None:
        positions = np.array([[.9, 0., 0.]])
        active = np.array([False])
        self.assertEqual(len(self.regions.select(positions, {'arm': np.zeros(3)}, active)), 0)
        selected = self.regions.select(positions, {'arm': np.array([.2, 0., 0.])}, active)
        np.testing.assert_array_equal(selected, [0])
        active[selected] = True
        np.testing.assert_array_equal(self.regions.select(positions, {'arm': np.zeros(3)}, active), [0])
        self.assertEqual(len(self.regions.select(positions, {'arm': np.array([-.11, 0., 0.])}, active)), 0)

    def test_selection_is_world_3d_and_does_not_modify_inputs(self) -> None:
        positions = np.array([[1., 2., 3.8], [1., 2., 3.81], [1., 2.9, 3.]])
        original = positions.copy()
        active = np.array([False, False, True])
        selected = self.regions.select(positions, {'arm': np.array([1., 2., 3.])}, active)
        np.testing.assert_array_equal(selected, [0, 2])
        np.testing.assert_array_equal(positions, original)
        np.testing.assert_array_equal(active, [False, False, True])

    def test_no_centers_selects_none_and_empty_idle_needs_no_dwell(self) -> None:
        positions = np.array([[0., 0., 0.], [1., 1., 1.]])
        self.assertEqual(len(self.regions.select(positions, {}, np.ones(2, dtype=bool))), 0)
        self.assertEqual(len(self.regions.select(np.empty((0, 3)), {}, np.empty(0, dtype=bool))), 0)
        self.assertEqual(self.hz(0.), 60)
        self.assertEqual(self.hz(1.), 60)

    def test_explicit_activity_is_high_even_with_no_nearby_fruit(self) -> None:
        self.assertEqual(self.hz(0., requested=True), 480)
        self.assertEqual(self.hz(.1, attached_active=True), 480)
        self.assertEqual(self.hz(.2), 60)

    def test_detached_translation_or_rotation_keeps_high_after_activity_stops(self) -> None:
        for velocity in ([.010001, 0, 0, 0, 0, 0], [0, 0, 0, .100001, 0, 0],
                         [.008, .008, 0, 0, 0, 0]):
            with self.subTest(velocity=velocity):
                self.regions = HarvestRegions(RegionSettings.from_mapping({}, 60))
                self.assertEqual(self.hz(0., [velocity], requested=False), 480)
                self.assertEqual(self.hz(3., [velocity], requested=False), 480)
                self.assertIsNone(self.regions.quiet_since)

    def test_all_detached_fruits_need_continuous_point_six_sim_seconds_quiet(self) -> None:
        still = np.array([[.01, 0, 0, .1, 0, 0], [0, 0, 0, 0, 0, 0]])
        self.assertEqual(self.hz(10., still), 480)
        self.assertEqual(self.hz(10.599999, still), 480)
        self.assertEqual(self.hz(10.6, still), 60)
        self.assertEqual(self.hz(100., still), 60)
        # 저주기 요청은 분리 과실을 kinematic으로 바꾸는 명령이 아닙니다.
        np.testing.assert_array_equal(still, [[.01, 0, 0, .1, 0, 0], [0, 0, 0, 0, 0, 0]])

    def test_one_moving_detached_fruit_resets_quiet_for_everyone(self) -> None:
        still = np.zeros((2, 6))
        moving = still.copy()
        moving[1, 3] = .2
        self.assertEqual(self.hz(0., still), 480)
        self.assertEqual(self.hz(.5, moving), 480)
        self.assertEqual(self.hz(.6, still), 480)
        self.assertEqual(self.hz(1.1, still), 480)
        self.assertEqual(self.hz(1.2, still), 60)

    def test_new_request_or_detached_motion_reawakens_high_rate(self) -> None:
        still = np.zeros((1, 6))
        self.assertEqual(self.hz(0., still), 480)
        self.assertEqual(self.hz(.6, still), 60)
        self.assertEqual(self.hz(.7, still, requested=True), 480)
        self.assertEqual(self.hz(.8, still), 480)
        self.assertEqual(self.hz(1.4, still), 60)
        self.assertEqual(self.hz(1.5, [[0, 0, -.5, 0, 0, 0]]), 480)

    def test_nonfinite_positions_centers_and_mismatched_shapes_are_rejected(self) -> None:
        for positions, centers, active in [
            ([[float('nan'), 0, 0]], {}, [False]),
            ([[0, 0]], {}, [False]),
            ([[0, 0, 0]], {}, [False, False]),
            ([[0, 0, 0]], {'arm': [0, float('inf'), 0]}, [False]),
            ([[0, 0, 0]], {'arm': [0, 0]}, [False]),
        ]:
            with self.subTest(positions=positions, centers=centers), self.assertRaises(ValueError):
                self.regions.select(positions, centers, active)

    def test_nonfinite_velocity_or_time_and_backwards_time_are_rejected(self) -> None:
        self.assertEqual(self.hz(2.), 60)
        for now, velocity in [(float('nan'), ()), (float('inf'), ()), (1.9, ()),
                              (3., [[0, 0, float('nan'), 0, 0, 0]]), (3., [[0, 0, 0]])]:
            with self.subTest(now=now, velocity=velocity), self.assertRaises(ValueError):
                self.hz(now, velocity)
        self.assertEqual(self.hz(2.), 60)
        self.assertEqual(self.hz(2.1), 60)


class RegionSettingsTests(unittest.TestCase):
    def test_supported_rates_and_default_geometry(self) -> None:
        defaults = RegionSettings.from_mapping({}, 60)
        self.assertEqual((defaults.idle_hz, defaults.harvest_hz), (60, 480))
        self.assertEqual((defaults.activation_radius_m, defaults.retention_radius_m), (.8, 1.))
        for rate in (60, 120, 240, 480):
            settings = RegionSettings.from_mapping(dict(harvest_hz=rate), 60)
            self.assertEqual(settings.harvest_hz, rate)

    def test_invalid_values_rates_and_reversed_thresholds_are_rejected(self) -> None:
        for changes in [dict(idle_hz=30), dict(harvest_hz=90), dict(idle_hz=480, harvest_hz=240),
                        dict(activation_radius_m=1.1), dict(settled_seconds=0),
                        dict(settled_linear_m_s=-1), dict(settled_angular_rad_s=float('nan')),
                        dict(harvest_hz=True), dict(retention_radius_m='1')]:
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                RegionSettings.from_mapping(changes, 60)

    def test_invalid_render_rate_is_rejected_with_value_error(self) -> None:
        for render_hz in (0, -60, True, '60', float('nan'), float('inf'), 90, 960):
            with self.subTest(render_hz=render_hz), self.assertRaises(ValueError):
                RegionSettings.from_mapping({}, render_hz)


if __name__ == '__main__':
    unittest.main()
