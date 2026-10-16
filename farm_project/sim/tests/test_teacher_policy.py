"""60Hz JIT·단계 실행과 잘못된 구성/주기 거부를 검사한다."""
import copy
import unittest
import numpy as np
from test_teacher_state import HAS_TORCH, PROJECT, profile, sample
if HAS_TORCH:
    import torch
    from farm_sim_devices.teacher_policy import TeacherController


@unittest.skipUnless(HAS_TORCH, 'PyTorch 필요')
class TeacherPolicyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.controller = TeacherController(profile(), project_root=PROJECT)

    def setUp(self):
        self.controller.start_target('target', sample())

    def test_embedded_normalization_matches_direct_jit_and_keeps_input(self):
        c = self.controller
        raw = c.state.observation()['policy'].clone()
        expected = c.actors['grasp'](raw).clamp(-1, 1)[0].detach().numpy()
        result = c.tick(sample())
        np.testing.assert_allclose(result.diagnostics['action'], expected, atol=1e-6)
        self.assertEqual(result.stage, -1)
        self.assertEqual(result.status, 'RUNNING')

    def test_physical_failure_and_reset_are_per_target(self):
        c = self.controller
        c.tick(sample())
        value = sample(.05); value['fruit_position'][2] = .4; value['attached'] = False
        self.assertEqual(c.tick(value).status, 'FAILED')
        actors = c.actors
        c.start_target('next', sample(10.))
        self.assertIs(c.actors, actors)
        self.assertFalse(c.state.pull_active[0])
        self.assertFalse(c.state.deposit_active[0])
        self.assertEqual(c.tick(sample(10.)).status, 'RUNNING')

    def test_cancel_generates_no_new_command(self):
        c = self.controller
        before = c.tick(sample()).joint_targets
        c.cancel()
        result = c.tick(sample(.05))
        self.assertEqual(result.status, 'CANCELLED')
        np.testing.assert_array_equal(result.joint_targets, before)

    def test_timing_and_deployment_mismatch_rejected(self):
        c = self.controller
        with self.assertRaises(ValueError): c.tick(sample(), 1/60)
        c.tick(sample())
        with self.assertRaises(ValueError): c.tick(sample(.1))
        p = copy.deepcopy(profile()); p['runtime']['stem_response_version'] = 5
        with self.assertRaises(ValueError): TeacherController(p, project_root=PROJECT)

    def test_release_is_measured_and_rate_limited(self):
        c = self.controller; e = c.state
        e.deposit_active[:] = True; e.deposit_first_command[:] = True
        e.deposit_arm_targets[:] = e.targets[:, :5]
        initial = e.targets[0].numpy().copy()
        result = c.tick(sample())
        self.assertEqual(result.stage, 2)
        np.testing.assert_allclose(result.joint_targets[:5], initial[:5], atol=1e-7)
        self.assertAlmostEqual(result.joint_targets[-1]-initial[-1], .3*.05, places=6)
