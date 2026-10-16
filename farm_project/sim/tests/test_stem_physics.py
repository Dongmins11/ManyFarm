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
                timer=np.zeros(count), thresholds=np.full(count, 2.5), dt_s=1/60)


class StemPhysicsTests(unittest.TestCase):
    def test_response6_matches_original_coupled_wrench_including_gyro(self):
        import torch
        from types import SimpleNamespace
        from farm_sim_devices._teacher_vendor.attachment_60hz import coupled_wrench
        from farm_sim_devices.stem_physics import _quaternion_error
        rng = np.random.default_rng(60); n = 64; cfg = StemSettings()
        data = inputs(n)
        for name, scale in [('displacement', .02), ('tip_velocity', .2), ('lever', .03), ('angular_velocity', 2.)]:
            data[name] = rng.normal(size=(n,3))*scale
        for name in ('orientation_wxyz', 'rest_orientation_wxyz'):
            q = rng.normal(size=(n,4)); data[name] = q/np.linalg.norm(q,axis=-1,keepdims=True)
        data['timer'] = rng.uniform(0,.04,n)
        data['attached'] = rng.random(n)>.2
        scalar, vector = _quaternion_error(data['orientation_wxyz'],data['rest_orientation_wxyz'])
        config = SimpleNamespace(**cfg.__dict__, tension_axis=(-1.,0.,0.))
        def t(value): return torch.as_tensor(value)
        for gyro in (False, True):
            result = stem_step(cfg, **data, gyroscopic_forces=gyro)
            oracle = coupled_wrench(t(data['displacement']),t(data['tip_velocity']),t(data['lever']),
                t(data['angular_velocity']),t(2*vector*np.sign(scalar)[:,None]),t(data['inverse_inertia_world']),
                config,t(data['attached']),t(data['timer']),1/60,t(data['thresholds']),gyroscopic_forces=gyro)
            for actual, expected in zip((result.force,result.torque,result.attached,result.timer,result.tension),oracle):
                np.testing.assert_allclose(actual,expected.numpy(),atol=1e-12,rtol=1e-10)

    def test_three_consecutive_ticks_and_no_reattachment(self):
        data = inputs(); data['displacement'][0,0] = -.026
        for index in range(3):
            result = stem_step(StemSettings(), **data)
            self.assertEqual(bool(result.attached[0]), index<2)
            data['attached'], data['timer'] = result.attached,result.timer
        self.assertAlmostEqual(result.timer[0], .05)
        data['displacement'][:] = 0
        result = stem_step(StemSettings(), **data)
        self.assertFalse(result.attached[0])
        np.testing.assert_array_equal(result.force, 0.)
        np.testing.assert_array_equal(result.torque, 0.)

    def test_sideways_break_remains_documented_limitation(self):
        data = inputs(); data['displacement'][0,1] = .041
        for _ in range(3):
            result = stem_step(StemSettings(), **data)
            data['attached'], data['timer'] = result.attached,result.timer
        self.assertFalse(result.attached[0])
        self.assertFalse(result.hook_opened[0])
        self.assertTrue(result.max_extension_exceeded[0])

    def test_no_480hz_or_response5_fallback(self):
        with self.assertRaises(ValueError): StemSettings.from_mapping({'stem_response_version':5})
        data = inputs(); data['dt_s']=1/480
        with self.assertRaises(ValueError): stem_step(StemSettings(), **data)

    def test_yaw_rotation_preserves_force_and_torque(self):
        data = inputs(); data['displacement'][0] = [-.01,.003,-.002]
        data['lever'][0] = [.02,.01,.03]
        original = stem_step(StemSettings(),**data)
        angle=.9; q=np.array([math.cos(angle/2),0,0,math.sin(angle/2)])
        r=quaternion_matrix(q)
        for name in ('displacement','tip_velocity','lever','angular_velocity','tension_axis_world'):
            data[name]=data[name]@r.T
        data['inverse_inertia_world']=r@data['inverse_inertia_world']@r.T
        data['orientation_wxyz'][:]=q; data['rest_orientation_wxyz'][:]=q
        rotated=stem_step(StemSettings(),**data)
        np.testing.assert_allclose(rotated.force,original.force@r.T,atol=1e-12)
        np.testing.assert_allclose(rotated.torque,original.torque@r.T,atol=1e-12)
