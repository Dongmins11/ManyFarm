"""실험 보상의 방향·경계·기존 전송 계약을 검증한다. 실제 주행 시험은 아니다."""
import copy
import tempfile
import json
import math
from pathlib import Path
import sys
import unittest
import numpy as np
import yaml

PKG = Path(__file__).resolve().parents[1]
ROOT = PKG.parents[3]
sys.path.insert(0, str(PKG))
from farm_tag_localization.pixel_bias import load_profile, compensate
from farm_tag_localization.tag_adapter import transported


class PixelBiasTests(unittest.TestCase):
    def setUp(self) -> None:
        self.cfg = yaml.safe_load((ROOT/'robot/config/localization/harvest_real.yaml').read_text())
        self.cfg['pixel_bias_profile'] = 'robot/config/localization/bias_trial_20261010/profile.json'
        # 녹화 프레임/학습 샘플은 10/10 지도 기준이다. 운영 새 지도와 분리한다.
        reference = json.loads((ROOT/self.cfg['pixel_bias_profile']).read_text())
        self.cfg['assets_file'] = 'robot/config/localization/reference_20261007/assets.candidate.json'
        for key in ('map_yaml_sha256', 'map_image_sha256'):
            self.cfg[key] = reference[key]
        self.reference_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.reference_dir.cleanup)
        self.reference_config = Path(self.reference_dir.name)/'recorded_config.yaml'
        self.reference_config.write_text(yaml.safe_dump(self.cfg))
        self.profile = load_profile(self.cfg, ROOT)
        self.candidate = dict(q=[1.18, -2., -math.pi/2], p=np.eye(3),
            _bias_tag=['tag36h11', 102], _bias_corners=[[630, 200], [650, 200], [650, 400], [630, 400]])

    def test_default_off_is_identical(self) -> None:
        del self.cfg['pixel_bias_profile']
        self.assertIsNone(load_profile(self.cfg, ROOT))
        q, audit = compensate(dict(q=self.candidate['q']), None)
        np.testing.assert_array_equal(q, self.candidate['q'])
        self.assertFalse(audit['enabled'])

    def test_direction_units_and_no_mutation(self) -> None:
        original = copy.deepcopy(self.candidate)
        q, audit = compensate(self.candidate, self.profile)
        self.assertAlmostEqual(q[0], 1.18 + self.profile['distance_bias_m'][0])
        self.assertEqual(q[1], -2.)
        self.assertAlmostEqual(q[2], -math.pi/2 - self.profile['yaw_bias_rad'][0])
        np.testing.assert_array_equal(self.candidate['q'], original['q'])
        np.testing.assert_array_equal(self.candidate['p'], original['p'])
        self.assertTrue(audit['enabled'])

    def test_wrong_identity_and_changed_assets_rejected(self) -> None:
        for key, value in [('robot_id', 'scout'), ('map_id', 'other'), ('map_yaml_sha256', 'wrong'), ('assets_file', self.cfg['model_file']), ('assets_file', self.cfg['model_file'])]:
            cfg = dict(self.cfg, **{key: value})
            with self.assertRaises(ValueError): load_profile(cfg, ROOT)

    def test_no_pixel_extrapolation_or_unknown_tag(self) -> None:
        for u in (0., 1000., float('nan')):
            c = dict(self.candidate, _bias_corners=[[u, 0]]*4)
            with self.assertRaises(ValueError): compensate(c, self.profile)
        with self.assertRaises(ValueError):
            compensate(dict(self.candidate, _bias_tag=['tag36h11', 106]), self.profile)

    def test_heading_and_nonfinite_are_not_silently_used(self) -> None:
        for q in ([1., 0., 0.], [float('nan'), 0., -math.pi/2]):
            with self.assertRaises(ValueError): compensate(dict(self.candidate, q=q), self.profile)

    def test_bias_is_applied_before_motion_transport(self) -> None:
        q, _ = compensate(self.candidate, self.profile)
        result = transported(q, [0., 0., 0.], [.1, 0., 0.])
        np.testing.assert_allclose(result[:2], q[:2] + .1*np.array([math.cos(q[2]), math.sin(q[2])]))

    def test_production_send_and_skip_preserve_motion_contract(self) -> None:
        from test_ros_contract import SendTests
        fixture = SendTests(); fixture.setUp()
        a = fixture.adapter
        a._bias_profile = self.profile
        # 실제 _send를 실행한다. ROS 객체만 시험 대체이며 주행 취소 API는 없다.
        candidate = dict(self.candidate, q=[0., 0., -math.pi/2])
        # 현재 pose도 같은 방향으로 바꾸어 기존 30도 관측 차이 검사를 만족시킨다.
        original = a._buffer.lookup_transform
        def transform(target, source, t):
            r = original(target, source, t)
            if target == 'map':
                r.transform.rotation.z = math.sin(-math.pi/4)
                r.transform.rotation.w = math.cos(-math.pi/4)
            return r
        a._buffer.lookup_transform = transform
        a._send(candidate, fixture.record, 'task', .01)
        self.assertEqual(len(fixture.sent), 1)
        self.assertTrue(fixture.logs[-1][1]['pixel_bias']['enabled'])
        a._send(dict(candidate, _bias_tag=['tag36h11', 106]), fixture.record, 'task', .01)
        self.assertEqual(len(fixture.sent), 1)
        self.assertEqual(fixture.logs[-1][0], 'pixel_bias_skip')

    def test_recorded_frame_through_production_solve(self) -> None:
        from test_ros_contract import load_node
        from farm_tag_localization.runtime import load_observer
        record = json.loads((ROOT/'robot/config/localization/bias_trial_20261010/replay_record.json').read_text())
        cls = load_node().TagAdapter
        adapter = cls.__new__(cls)
        _, adapter._observer = load_observer(str(self.reference_config), str(ROOT), 'bias-replay')
        candidate, result, _ = adapter._solve(record)
        np.testing.assert_allclose(candidate['q'], [1.15290566427, -1.00271721870, -1.56404565931], atol=2e-6, rtol=0.)
        adjusted, audit = compensate(candidate, self.profile)
        self.assertEqual(list(audit['tag']), ['tag36h11', 100])
        self.assertGreater(adjusted[0], candidate['q'][0])
        self.assertLess(adjusted[2], candidate['q'][2])
        np.testing.assert_array_equal(result['selected']['usable_candidates'][0]['q'], candidate['q'])

    def test_fit_and_leave_one_tag_out(self) -> None:
        rows = json.loads((ROOT/'robot/config/localization/bias_trial_20261010/fit_samples.json').read_text())
        x = np.array([[1., (r['u']-640)/640] for r in rows])
        y = np.array([[r['distance_error_cm']/100, math.radians(r['yaw_error_deg'])] for r in rows])
        coefficient = np.linalg.lstsq(x, y, rcond=None)[0]
        np.testing.assert_allclose(coefficient[:, 0], self.profile['distance_bias_m'], atol=1e-12)
        np.testing.assert_allclose(coefficient[:, 1], self.profile['yaw_bias_rad'], atol=1e-12)
        for tag in self.profile['tag_ids']:
            held = np.array([r['id'] == tag for r in rows])
            fitted = np.linalg.lstsq(x[~held], y[~held], rcond=None)[0]
            before = np.sqrt(np.mean(y[held]**2, axis=0))
            after = np.sqrt(np.mean((y[held]-x[held]@fitted)**2, axis=0))
            self.assertTrue(np.all(after < before), (tag, before, after))


if __name__ == '__main__': unittest.main()
