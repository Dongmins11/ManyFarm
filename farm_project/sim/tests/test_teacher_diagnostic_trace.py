"""실제 JIT 호출/최종 명령 계측은 출력에 영향을 주지 않는다."""
import unittest
import numpy as np
from test_teacher_state import HAS_TORCH, PROJECT, profile, sample
if HAS_TORCH:
    from farm_sim_devices.teacher_policy import TeacherController


@unittest.skipUnless(HAS_TORCH, 'PyTorch 필요')
class DiagnosticTests(unittest.TestCase):
    def test_trace_records_raw_input_output_and_held_observation(self):
        c = TeacherController(profile(), project_root=PROJECT)
        c.start_target('plain', sample()); expected = c.tick(sample())
        c.enable_diagnostic_trace(); c.start_target('trace', sample())
        actual = c.tick(sample()); trace = actual.diagnostics['diagnostic_trace']
        np.testing.assert_array_equal(actual.joint_targets, expected.joint_targets)
        self.assertEqual(len(trace['expert_calls']['grasp']['observation_raw']), 82)
        self.assertEqual(len(trace['expert_calls']['pull']['actor_output']), 6)
        self.assertEqual(trace['expert_calls']['grasp']['normalization'], 'embedded_in_torchscript')
        self.assertEqual(trace['joint_targets'], actual.joint_targets)
        self.assertNotIn('diagnostic_trace', c.observe(sample(.05)).diagnostics)
