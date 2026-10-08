"""실제4개 가중치를 CPU에서 실행해 loader·routing·명령 계약을 검사합니다."""
from __future__ import annotations

import contextlib
import copy
import importlib.util
import io
import unittest

import numpy as np

from test_teacher_state import HAS_TORCH, PROJECT, profile, sample

HAS_RSL = HAS_TORCH and importlib.util.find_spec('rsl_rl') is not None
if HAS_RSL:
    import torch
    from farm_sim_devices.teacher_policy import TeacherController


@unittest.skipUnless(HAS_RSL, '정책 검사는 PyTorch/RSL-RL 설치 환경에서 수행합니다.')
class TeacherPolicyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        with contextlib.redirect_stdout(io.StringIO()):
            cls.controller = TeacherController(profile(), project_root=PROJECT)
            cls.controller.start_target('initial', sample())

    def setUp(self) -> None:
        self.controller.start_target('target', sample())

    def test_entry_action_matches_loaded_official_actor_and_normalizer(self) -> None:
        controller = self.controller
        observation = controller.state.observation()
        before = controller.policy.grasp_expert.actor_obs_normalizer._mean.clone()
        with torch.inference_mode():
            expected = controller.policy.grasp_expert.act_inference(observation).clamp(-1., 1.)
        result = controller.tick(sample())
        np.testing.assert_allclose(result.diagnostics['action'], expected[0], atol=1e-7)
        torch.testing.assert_close(before, controller.policy.grasp_expert.actor_obs_normalizer._mean)
        self.assertEqual(result.stage, -1)
        self.assertEqual(result.status, 'RUNNING')

    def test_transport_ramp_preserves_gripper_and_scales_only_arm(self) -> None:
        controller = self.controller
        controller.policy.grasp_active[:] = False
        controller.policy.stage[:] = 1
        with torch.inference_mode():
            raw = controller.policy.experts[1].act_inference(controller.state.observation())
            expected = raw.clamp(-1., 1.)
            expected[:, :5] *= .25
        result = controller.tick(sample())
        np.testing.assert_allclose(result.diagnostics['action'], expected[0], atol=1e-7)
        self.assertEqual(result.stage, 1)

    def test_fixed_release_keeps_arm_target_and_opens_by_point009_rad(self) -> None:
        controller = self.controller
        controller.policy.grasp_active[:] = False
        controller.policy.stage[:] = 2
        before = controller.state.targets[0].numpy().copy()
        result = controller.tick(sample())
        np.testing.assert_allclose(result.joint_targets[:5], before[:5], atol=1e-7)
        self.assertAlmostEqual(result.joint_targets[5] - before[5], .009, places=6)
        np.testing.assert_allclose(result.diagnostics['action'], [0., 0., 0., 0., 0., .15], atol=1e-7)

    def test_routing_changes_only_after_grasp_and_retention_evidence(self) -> None:
        controller = self.controller
        controller.state.has_grasped[:] = True
        controller.state.grip[:] = True
        controller.state.valid_detach[:] = True
        controller.state.has_retained[:] = False
        result = controller.tick(sample())
        self.assertEqual(result.stage, 0)
        controller.start_target('second', sample())
        controller.state.has_grasped[:] = True
        controller.state.grip[:] = True
        controller.state.valid_detach[:] = True
        controller.state.has_retained[:] = True
        result = controller.tick(sample())
        self.assertEqual(result.stage, 1)

    def test_failure_holds_targets_and_new_target_resets_only_controller(self) -> None:
        controller = self.controller
        first = controller.tick(sample())
        s = sample(.05)
        s['fruit_position'][2] = .4
        s['attached'] = False
        source = copy.deepcopy(s)
        failed = controller.tick(s)
        self.assertEqual(failed.status, 'FAILED')
        np.testing.assert_array_equal(failed.joint_targets, first.joint_targets)
        steps = controller.policy.stage_steps.clone()
        controller.observe(dict(s, time_s=.1))
        torch.testing.assert_close(steps, controller.policy.stage_steps)
        np.testing.assert_array_equal(s['fruit_position'], source['fruit_position'])
        controller.start_target('after-failure', sample(1.))
        self.assertEqual(controller.tick(sample(1.)).stage, -1)
        self.assertEqual(controller.state.assignment_status, 'RUNNING')

    def test_observe_reports_physical_success_separately_after_teacher_failure(self) -> None:
        controller = self.controller
        controller.tick(sample())
        s = sample(.05)
        s['attached'] = False
        failed = controller.tick(s)
        self.assertEqual(failed.status, 'FAILED')
        for tick in range(2, 14):
            s.update(time_s=tick * .05, fruit_position=[.4, 0., .6], fruit_com_position=[.4, 0., .6])
            result = controller.observe(s)
        self.assertEqual(result.status, 'SUCCEEDED')
        self.assertEqual(result.diagnostics['teacher_status'], 'FAILED')
        self.assertFalse(result.diagnostics['teacher_strict_success'])

    def test_wrong_tick_period_or_sample_interval_rejected(self) -> None:
        controller = self.controller
        with self.assertRaises(ValueError):
            controller.tick(sample(), dt_s=.025)
        controller.tick(sample())
        with self.assertRaises(ValueError):
            controller.tick(sample(.025))

    def test_cancel_never_produces_another_action(self) -> None:
        controller = self.controller
        result = controller.tick(sample())
        controller.cancel()
        cancelled = controller.tick(sample(.05))
        self.assertEqual(cancelled.status, 'CANCELLED')
        np.testing.assert_array_equal(cancelled.joint_targets, result.joint_targets)

    def test_hash_mismatch_rejected_before_loading_weights(self) -> None:
        p = profile()
        p['checkpoints']['ENTRY_CKPT']['sha256'] = '0' * 64
        with self.assertRaisesRegex(ValueError, 'hash mismatch'):
            TeacherController(p, project_root=PROJECT)


if __name__ == '__main__':
    unittest.main()
