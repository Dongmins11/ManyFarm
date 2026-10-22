"""실제 렌더 배열의 RGB 값·깊이 정렬 의미를 기존 전처리와 비교한다."""
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import numpy as np
from scipy.spatial.transform import Rotation

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'sim/ros_ws/src/farm_sim_devices'))
sys.path.insert(0, str(ROOT/'sim/assets/robotarm_student/manyfarm_robotarm/src/harvest_robot'))
from farm_sim_devices.student_camera import FarmD435Rig, align_depth_to_color
from harvest_rl.rgbd_geometry import align_depth_to_color as original_align
from harvest_sensors.student60_eval_camera_cache import centred_render_spec, remap_render


class CameraPreprocessingTest(unittest.TestCase):
    def rig(self):
        """SDK 밖에서 촬영 순서·물리 시각 계약만 검사한다."""
        spec = dict(width=4, height=2, intrinsics=dict(fx=3., fy=3., ppx=2., ppy=1.))
        w, h, k, *_ = centred_render_spec(spec)
        camera = SimpleNamespace(
            get_world_pose=lambda **kw: (np.zeros(3), np.array([1., 0., 0., 0.])),
            get_intrinsics_matrix=lambda: k,
            get_rgba=lambda: np.full((h, w, 4), 100, np.uint8),
            get_depth=lambda: np.full((h, w), .5, np.float32))
        streams = dict(rgb=spec, depth=spec, ir_right=spec)
        views = {name: dict(streams=streams, internal_calibration_verified=True,
                           mount_calibration_verified=False) for name in ('right', 'rear')}
        rig = FarmD435Rig.__new__(FarmD435Rig)
        rig.world = SimpleNamespace(current_time=2/60, render=Mock())
        rig.active, rig.start_time, rig.sequence, rig.max_fk_error = True, 0., 0, 0.
        rig.last, rig.frame_timings, rig._prepared_capture = {}, {}, None
        rig.cameras = {name: {key: camera for key in streams} for name in views}
        rig.config = dict(views=views, depth_min_m=.28, depth_max_m=3., sim_ir_model='luminance')
        expected = {name: {key: np.eye(4) for key in streams} for name in views}
        rig.update_poses = Mock(return_value=(np.zeros(6), expected))
        rig.align_depth = align_depth_to_color
        return rig

    def test_resume_preserves_counters_and_acquires_fresh_frame(self):
        rig = self.rig()
        stream = SimpleNamespace(resume=Mock(), pause=Mock(),
            _render_product=SimpleNamespace(hydra_texture=SimpleNamespace(set_updates_enabled=Mock())))
        rig.cameras = {'rear': {'rgb': stream}}
        rig.sequence, rig.max_fk_error = 42, .001
        rig.last = {'rear': {'stamp_s': 0.}}
        rig.acquire = Mock()
        rig.set_active(False, reset_capture=False)
        self.assertFalse(rig.active)
        stream.pause.assert_called_once()
        rig.set_active(True, reset_capture=False)
        self.assertTrue(rig.active)
        self.assertEqual(rig.sequence, 42)
        self.assertEqual(rig.max_fk_error, .001)
        self.assertEqual(rig.start_time, 0.)
        self.assertEqual(rig.last, {})
        rig.acquire.assert_called_once_with(rig.world.current_time)
        stream.resume.assert_called_once()

    def test_current_pose_regular_render_counts_as_first_of_two_passes(self):
        rig = self.rig()
        now = rig.world.current_time
        rig.prepare_capture(now)
        rig.world.render()  # scheduler가 물리 직후 현재 pose로 실행한 렌더
        rig.after_frame(now)
        self.assertEqual(rig.world.render.call_count, 2)
        self.assertEqual(rig.update_poses.call_count, 1)
        self.assertEqual(rig.frame_timings['camera_reused_render_passes'], 1)
        self.assertEqual(rig.last['rear']['stamp_s'], now)
        rig.after_frame(now)
        self.assertEqual(rig.world.render.call_count, 2)  # 같은 촬영 시각 중복 없음
        self.assertFalse(rig.capture_due(now+1/60))
        self.assertTrue(rig.capture_due(now+2/60))

    def test_old_pose_render_cannot_be_reused_at_a_new_physics_time(self):
        rig = self.rig()
        rig.prepare_capture(rig.world.current_time)
        rig.world.render()
        rig.world.current_time += 2/60
        rig.after_frame(rig.world.current_time)
        self.assertEqual(rig.world.render.call_count, 3)
        self.assertEqual(rig.update_poses.call_count, 2)
        self.assertEqual(rig.frame_timings['camera_reused_render_passes'], 0)

    def test_without_regular_render_original_two_passes_are_preserved(self):
        rig = self.rig()
        rig.after_frame(rig.world.current_time)
        self.assertEqual(rig.world.render.call_count, 2)
        self.assertEqual(rig.frame_timings['camera_reused_render_passes'], 0)

    def test_rgb_remap_preserves_values_with_rgba_input(self):
        """SDK의 RGBA stride 입력과 비중앙 주점/서로 다른 초점거리를 비교한다."""
        spec = dict(width=128, height=72, intrinsics=dict(
            fx=103.7, fy=102.2, ppx=62.3, ppy=35.8))
        w, h, *_ = centred_render_spec(spec)
        rgba = np.random.default_rng(42).integers(0, 256, (h, w, 4), dtype=np.uint8)
        expected = remap_render(rgba[:, :, :3], spec)
        actual = np.ascontiguousarray(remap_render(rgba, spec)[:, :, :3])
        np.testing.assert_array_equal(actual, expected)
        self.assertTrue(actual.flags.c_contiguous)

    def test_native_processor_is_opt_in_and_default_remains_original(self):
        from harvest_runtime.student60_mission_session import MissionCameraSession
        session = MissionCameraSession.__new__(MissionCameraSession)
        session.arm_from_world = np.eye(4)
        session.contract = dict(centre_offset_m=.025)
        session.roi, session.target = [[-1.]*3, [1.]*3], None
        session.detector = object()
        capture = {'rear': dict(rgb=np.zeros((2, 4, 3), np.uint8),
            aligned_depth_m=np.ones((2, 4), np.float32), intrinsics=dict(rgb=np.eye(3)),
            world_from_optical=dict(rgb=np.eye(4)), stamp_s=1., pose_stamp_s=1.)}
        with patch('harvest_sensors.student60_native_fast.process_native', return_value=([], None)) as original:
            session.native_processor = None
            session.observe(capture, 1.)
            original.assert_called_once()
            session.native_processor = Mock(return_value=([{'label': 'Red'}], None))
            _, detections = session.observe(capture, 1.)
            session.native_processor.assert_called_once()
            self.assertEqual(original.call_count, 1)
            self.assertEqual(detections, [{'label': 'Red'}])

    def test_alignment_preserves_holes_occlusion_and_calibration(self):
        """유효하지 않은 깊이·영상 밖·카메라 뒤·다중 투영의 z-buffer를 보존한다."""
        rng = np.random.default_rng(3)
        kd = np.array([[52.3, 0, 41.1], [0, 51.7, 23.8], [0, 0, 1]])
        kc = np.array([[77.4, 0, 62.3], [0, 76.8, 35.5], [0, 0, 1]])
        for index in range(30):
            depth = rng.uniform(.28, 3., (48, 84)).astype(np.float32)
            depth.ravel()[::7] = 0
            depth.ravel()[1::17] = np.nan
            depth.ravel()[2::31] = np.inf
            t = np.eye(4)
            t[:3, :3] = Rotation.from_rotvec(rng.normal(0, .03, 3)).as_matrix()
            t[:3, 3] = [.015, -.0001, -4. if index == 0 else .0005]
            expected = original_align(depth, kd, kc, t, (72, 128))
            actual = align_depth_to_color(depth, kd, kc, t, (72, 128))
            np.testing.assert_array_equal(actual, expected)
            self.assertEqual(actual.dtype, np.float32)

    def test_empty_depth_remains_empty(self):
        k = np.eye(3)
        np.testing.assert_array_equal(
            align_depth_to_color(np.zeros((2, 3), np.float32), k, k, np.eye(4), (4, 5)),
            np.zeros((4, 5), np.float32))


if __name__ == '__main__':
    unittest.main()
