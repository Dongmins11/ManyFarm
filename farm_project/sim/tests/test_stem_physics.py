"""short-hook 물리 회귀: 힘/시간/좌표 불변성. Isaac 접촉 검증은 별도입니다."""
import math
from pathlib import Path
import sys
import unittest

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'sim/ros_ws/src/farm_sim_devices'))
from farm_sim_devices.stem_physics import StemSettings, quaternion_matrix, stem_step


def inputs(count: int = 1) -> dict:
    """COM=꼭지인 단순 fixture. 비대칭 관성으로 회전 변환도 검사합니다."""
    return dict(displacement=np.zeros((count, 3)), tip_velocity=np.zeros((count, 3)),
                lever=np.zeros((count, 3)), inverse_inertia_world=np.tile(np.diag([10000., 20000., 30000.]), (count, 1, 1)),
                tension_axis_world=np.tile([-1., 0., 0.], (count, 1)),
                orientation_wxyz=np.tile([1., 0., 0., 0.], (count, 1)),
                rest_orientation_wxyz=np.tile([1., 0., 0., 0.], (count, 1)),
                angular_velocity=np.zeros((count, 3)), attached=np.ones(count, dtype=bool),
                timer=np.zeros(count), thresholds=np.full(count, 2.5), dt_s=1/480)


class StemPhysicsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.settings = StemSettings.from_mapping({})

    def test_zero_load_has_no_gravity_feedforward(self) -> None:
        result = stem_step(self.settings, **inputs())
        np.testing.assert_array_equal(result.force, [[0., 0., 0.]])
        np.testing.assert_array_equal(result.torque, [[0., 0., 0.]])
        self.assertTrue(result.attached[0])

    def test_implicit_axial_force_matches_scalar_mass_system(self) -> None:
        # 1자유도 implicit Euler: F = -(k*x + (d+dt*k)*v)/(1+dt*(d+dt*k)/m).
        case = inputs()
        case['displacement'][0, 0] = -.01
        case['tip_velocity'][0, 0] = -.02
        result = stem_step(self.settings, **case)
        dt, mass, k, damping = 1/480, .009, 60., 4.2
        expected = (k*.01+(damping+dt*k)*.02)/(1+dt*(damping+dt*k)/mass)
        self.assertAlmostEqual(result.force[0, 0], expected, places=13)
        self.assertEqual(result.timer[0], 0.)

    def test_short_hook_requires_continuous_40ms_and_stays_detached(self) -> None:
        case = inputs(2)
        case['displacement'][0, 0] = -.025
        case['displacement'][1, 0] = -.0249
        for _ in range(19):
            result = stem_step(self.settings, **case)
            case.update(attached=result.attached, timer=result.timer)
        self.assertTrue(result.attached.all())
        self.assertAlmostEqual(result.timer[0], 19/480)
        result = stem_step(self.settings, **case)
        self.assertFalse(result.attached[0])
        self.assertTrue(result.attached[1])
        self.assertAlmostEqual(result.timer[0], 20/480)
        np.testing.assert_array_equal(result.force[0], [0., 0., 0.])
        case.update(attached=result.attached, timer=result.timer)
        case['displacement'].fill(0.)
        result = stem_step(self.settings, **case)
        self.assertFalse(result.attached[0])
        self.assertEqual(result.timer[0], 0.)

    def test_interrupted_pull_clears_dwell_and_lateral_escape_detaches(self) -> None:
        case = inputs()
        case['displacement'][0, 1] = .04
        for _ in range(10):
            result = stem_step(self.settings, **case)
            case.update(attached=result.attached, timer=result.timer)
        case['displacement'][0, 1] = .039
        result = stem_step(self.settings, **case)
        self.assertEqual(result.timer[0], 0.)
        case.update(attached=result.attached, timer=result.timer)
        case['displacement'][0, 1] = .04
        for _ in range(20):
            result = stem_step(self.settings, **case)
            case.update(attached=result.attached, timer=result.timer)
        self.assertFalse(result.attached[0])

    def test_force_condition_does_not_bypass_minimum_extension(self) -> None:
        case = inputs(2)
        case['thresholds'].fill(.1)
        case['displacement'][:, 0] = [-.012, -.013]
        result = stem_step(self.settings, **case)
        self.assertEqual(result.timer[0], 0.)
        self.assertGreater(result.timer[1], 0.)
        np.testing.assert_allclose(np.linalg.norm(result.force, axis=-1), [.1, .1])

    def test_yaw_rotation_preserves_forces_torques_and_timer(self) -> None:
        case = inputs()
        case['displacement'][0] = [-.03, .006, -.003]
        case['tip_velocity'][0] = [.02, -.01, .03]
        case['lever'][0] = [.01753, .012588, .0375]
        case['angular_velocity'][0] = [.1, -.2, .3]
        angle = .15
        case['orientation_wxyz'][0] = [math.cos(angle/2), math.sin(angle/2), 0., 0.]
        original = stem_step(self.settings, **case)
        yaw = 1.1
        q = np.array([[math.cos(yaw/2), 0., 0., math.sin(yaw/2)]])
        rotation = quaternion_matrix(q)[0]
        changed = dict(case)
        for key in ('displacement', 'tip_velocity', 'lever', 'angular_velocity', 'tension_axis_world'):
            changed[key] = case[key] @ rotation.T
        changed['inverse_inertia_world'] = rotation @ case['inverse_inertia_world'] @ rotation.T
        changed['rest_orientation_wxyz'] = q
        # yaw quaternion * 초기 roll quaternion. 좌표계 전체의 동일 회전입니다.
        a, b = angle/2, yaw/2
        changed['orientation_wxyz'] = np.array([[math.cos(b)*math.cos(a), math.cos(b)*math.sin(a),
                                               math.sin(b)*math.sin(a), math.sin(b)*math.cos(a)]])
        rotated = stem_step(self.settings, **changed)
        np.testing.assert_allclose(rotated.force, original.force @ rotation.T, atol=1e-12)
        np.testing.assert_allclose(rotated.torque, original.torque @ rotation.T, atol=1e-12)
        np.testing.assert_allclose(rotated.timer, original.timer)

    def test_diagnostics_distinguish_force_threshold_from_geometric_escape(self) -> None:
        """같은 분리 타이머라도 힘 초과와 거리 이탈 원인을 서로 구분해야 합니다."""
        case = inputs(3)
        case['displacement'][0, 0] = -.013
        case['tip_velocity'][0, 0] = -2.
        case['displacement'][1, 0] = -.025
        case['displacement'][2, 1] = .040
        result = stem_step(self.settings, **case)
        np.testing.assert_array_equal(result.force_exceeded, [True, False, False])
        np.testing.assert_array_equal(result.hook_opened, [False, True, False])
        np.testing.assert_array_equal(result.max_extension_exceeded, [False, False, True])
        self.assertGreater(result.raw_tension[0], 2.5)
        self.assertEqual(result.tension[0], 2.5)
        self.assertLess(result.raw_tension[1], 2.5)
        np.testing.assert_allclose(result.timer, np.full(3, 1/480))
        self.assertTrue(result.attached.all())

    def test_quaternion_sign_does_not_change_restoring_torque(self) -> None:
        case = inputs()
        case['orientation_wxyz'][0] = [math.cos(.2), 0., math.sin(.2), 0.]
        first = stem_step(self.settings, **case)
        case['orientation_wxyz'] *= -1
        second = stem_step(self.settings, **case)
        np.testing.assert_allclose(first.torque, second.torque)
        self.assertLess(first.torque[0, 1], 0.)

    def test_invalid_values_rejected_before_force_application(self) -> None:
        for key, value in (('mass', 0), ('tension_hold_s', -1), ('spring_d', float('nan')),
                           ('attachment_version', 3)):
            with self.subTest(key=key), self.assertRaises(ValueError):
                StemSettings.from_mapping({key: value})
        for key, value in (('dt_s', 0.), ('thresholds', [0.]), ('tip_velocity', [[float('nan'), 0., 0.]]),
                           ('orientation_wxyz', [[0., 0., 0., 0.]])):
            case = inputs()
            case[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                stem_step(self.settings, **case)


if __name__ == '__main__':
    unittest.main()
