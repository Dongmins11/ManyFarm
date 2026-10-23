"""같은 시각·구간 복수 태그의 기하, 보수적 불확실성 및 fallback 회귀."""
from copy import deepcopy
from pathlib import Path
import sys
import unittest
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from farm_tag_localization.runtime import load_observer
from farm_tag_localization.geometry import inverse, pose6
from farm_tag_localization.pixel_bias import compensate

ROOT = Path(__file__).resolve().parents[5]


class MultiTag(unittest.TestCase):
    def setUp(self) -> None:
        _, self.observer = load_observer('sim/ros_ws/src/farm_sim_config/config/tag_localization/scout.yaml', str(ROOT), 'test')
        o = self.observer
        tags = sorted(o.section_landmarks['SEC01'].values(), key=lambda t:t.tag_id)
        self.tags = tags[6:9]
        # 등록 태그 앞의 카메라를 구성하고 실제 장착값으로 차체를 역산한다.
        camera_tag = np.eye(4)
        camera_tag[:3,:3] = np.diag([1.,-1.,-1.])
        camera_tag[2,3] = 1.1
        self.base = self.tags[1].t_map_tag @ inverse(camera_tag) @ inverse(o.t_base_camera)
        # 이 기하 시험의 기준 자세를 품질검사 기준으로 사용한다.
        from dataclasses import replace
        p = pose6(self.base)
        o.quality = replace(o.quality, base_z_m=p[2], max_roll_rad=3.15, max_pitch_rad=3.15)
        c = o.context
        self.frame = dict(stamp_ns=1, camera_info_stamp_ns=1, optical_frame=o.camera.optical_frame,
            image_size=[1280,720], calibration_version=o.camera.version, rectified=True,
            session_id=c.session_id, epoch=c.epoch, image_uid='test', section_id='SEC01', capture_time_model_valid=True)
        self.detections = [dict(family=t.family, tag_id=t.tag_id, corners=o.project_map_base(self.base,t).tolist(),
            corner_convention='ippe_square_v1', decision_margin=100., hamming=0) for t in self.tags]

    def result(self, detections=None) -> dict:
        return self.observer.observe(self.frame, self.detections if detections is None else detections)

    def test_joint_recovers_pose_and_preserves_covariance(self) -> None:
        result = self.result()
        self.assertEqual(result['multi_tag']['reason'], 'selected', result)
        selected = result['selected']
        self.assertEqual(selected['observation_kind'], 'multi_tag')
        np.testing.assert_allclose(selected['usable_candidates'][0]['t_map_base'], self.base, atol=1e-6)
        np.testing.assert_allclose(selected['usable_candidates'][0]['p6'], result['all_packets'][0]['usable_candidates'][0]['p6'])
        self.assertEqual(self.observer.estimator_event(selected)['model_id'], self.observer.multi_model_id)
        reverse = self.result(list(reversed(self.detections)))
        np.testing.assert_allclose(reverse['selected']['usable_candidates'][0]['q'], selected['usable_candidates'][0]['q'], atol=1e-10)

    def test_one_tag_or_unvalidated_model_uses_single(self) -> None:
        self.assertNotEqual(self.result(self.detections[:1])['selected'].get('observation_kind'), 'multi_tag')
        self.observer.multi_model_id = None
        self.assertEqual(self.result()['multi_tag']['reason'], 'disabled')

    def test_duplicates_and_bad_corners_are_not_grouped(self) -> None:
        bad = deepcopy(self.detections)
        bad[1]['corners'] = [[-1.,0.]]*4
        result = self.result(bad + [deepcopy(bad[0])])
        self.assertEqual(result['multi_tag']['reason'], 'insufficient_usable_tags')
        self.assertNotEqual(result['selected'].get('observation_kind'), 'multi_tag')

    def test_missing_section_and_invalid_capture_do_not_publish(self) -> None:
        self.frame['section_id'] = 'unknown'
        self.assertIsNone(self.result()['selected'])
        self.frame['section_id'] = 'SEC01'
        self.frame['capture_time_model_valid'] = False
        self.assertIsNone(self.result()['selected'])

    def test_corrupt_joint_falls_back_without_hiding_candidates(self) -> None:
        original = self.observer.camera.solve_group
        def corrupt(points: np.ndarray, corners: np.ndarray) -> list:
            pair = original(points, corners)
            for solution in pair:
                solution['tag_rms_px'][0] = 100.
            return pair
        self.observer.camera.solve_group = corrupt
        result = self.result()
        self.assertEqual(result['multi_tag']['reason'], 'quality_rejected')
        self.assertNotEqual(result['selected'].get('observation_kind'), 'multi_tag')
        self.assertTrue(result['all_packets'][-1]['candidates'])

    def test_joint_checks_distance_for_every_tag(self) -> None:
        original = self.observer.uncertainty_model
        def reject_group(observer: object, packet: dict, solution: dict, transform: np.ndarray) -> np.ndarray:
            if solution.get('solver', '').startswith('multi_'):
                raise ValueError('outside_tag_distance')
            return original(observer, packet, solution, transform)
        self.observer.uncertainty_model = reject_group
        result = self.result()
        self.assertEqual(result['multi_tag']['reason'], 'quality_rejected')
        self.assertNotEqual(result['selected'].get('observation_kind'), 'multi_tag')
        self.assertIn('outside_tag_distance', result['all_packets'][-1]['candidates'][0]['reasons'][0])

    def test_real_and_harvest_profiles_remain_single_tag(self) -> None:
        for config in ('robot/config/localization/harvest_real.yaml',
                       'sim/ros_ws/src/farm_sim_config/config/tag_localization/harvest.yaml'):
            _, observer = load_observer(config, str(ROOT), 'test')
            self.assertIsNone(observer.multi_model_id)

    def test_ambiguous_joint_preserves_both_and_uses_single(self) -> None:
        original = self.observer.camera.solve_group
        def ambiguous(points: np.ndarray, corners: np.ndarray) -> list:
            candidate = deepcopy(original(points, corners)[0])
            other = deepcopy(candidate)
            other['candidate_id'] = 1
            other['t_camera_tag'][0,3] += .01
            return [candidate, other]
        self.observer.camera.solve_group = ambiguous
        result = self.result()
        self.assertEqual(result['multi_tag']['reason'], 'ambiguous')
        self.assertEqual(len(result['all_packets'][-1]['usable_candidates']), 2)
        self.assertNotEqual(result['selected'].get('observation_kind'), 'multi_tag')

    def test_non_coplanar_or_coincident_registration_falls_back(self) -> None:
        landmarks = self.observer.section_landmarks['SEC01']
        tag = landmarks[(self.tags[0].family, self.tags[0].tag_id)]
        tag.t_map_tag = tag.t_map_tag.copy()
        tag.t_map_tag[:3,3] += tag.t_map_tag[:3,2]*.01
        self.assertEqual(self.result()['multi_tag']['reason'], 'noncoplanar_registration')
        for item in landmarks.values():
            item.t_map_tag = self.tags[1].t_map_tag.copy()
        self.assertEqual(self.result()['multi_tag']['reason'], 'insufficient_tag_separation')

    def test_registered_in_plane_rotation_preserves_corner_identity(self) -> None:
        tag = self.observer.section_landmarks['SEC01'][(self.tags[0].family, self.tags[0].tag_id)]
        rotate = np.eye(4)
        rotate[:2,:2] = [[0.,-1.],[1.,0.]]
        tag.t_map_tag = tag.t_map_tag @ rotate
        self.detections[0]['corners'] = self.observer.project_map_base(self.base, tag).tolist()
        selected = self.result()['selected']
        self.assertEqual(selected.get('observation_kind'), 'multi_tag')
        np.testing.assert_allclose(selected['usable_candidates'][0]['t_map_base'], self.base, atol=1e-6)

    def test_single_tag_bias_is_never_applied_to_group(self) -> None:
        candidate = self.result()['selected']['usable_candidates'][0]
        adjusted, audit = compensate(candidate, {'invalid_single_profile':True})
        np.testing.assert_array_equal(adjusted, candidate['q'])
        self.assertFalse(audit['enabled'])


if __name__ == '__main__':
    unittest.main()
