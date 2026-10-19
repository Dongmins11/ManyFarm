"""Directional connector regression, independent of Isaac Sim."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import torch
from harvest_rl.settings import TaskSettings
from harvest_rl.logic import attachment_wrench, valid_pull


class AttachmentV4Tests(unittest.TestCase):
    def evaluate(self, displacement, velocity=(0., 0., 0.), steps=60, cfg=None):
        cfg = cfg or TaskSettings(attachment_version=4, stem_response_version=1)
        attached = torch.ones(1, dtype=torch.bool)
        timer = torch.zeros(1)
        for _ in range(steps):
            result = attachment_wrench(torch.tensor([displacement]), torch.tensor([velocity]),
                torch.zeros(1, 3), cfg, attached, timer, cfg.physics_dt, torch.tensor([2.5]))
            force, torque, attached, timer, load = result
        return result

    def test_sustained_axial_pull_breaks_without_grasp_gate(self):
        force, torque, attached, timer, load = self.evaluate((-.03, 0., 0.), steps=29)
        self.assertFalse(attached.item())
        self.assertGreaterEqual(timer.item(), .12)
        self.assertAlmostEqual(load.item(), 3.6, places=5)
        self.assertEqual(force.abs().sum().item(), 0.)
        self.assertEqual(torque.abs().sum().item(), 0.)

    def test_short_overload_does_not_break(self):
        self.assertTrue(self.evaluate((-.03, 0., 0.), steps=6)[2].item())

    def test_subthreshold_pull_compression_and_lateral_contact_stay_attached(self):
        for position in ((-.015, 0., 0.), (.04, 0., 0.), (0., .08, 0.)):
            self.assertTrue(self.evaluate(position)[2].item(), position)

    def test_velocity_spike_without_extension_does_not_break(self):
        self.assertTrue(self.evaluate((-.001, 0., 0.), (-10., 0., 0.))[2].item())

    def test_interrupted_overload_restarts_timer(self):
        cfg = TaskSettings(attachment_version=4, stem_response_version=1)
        attached, timer = torch.ones(1, dtype=torch.bool), torch.zeros(1)
        for x in [-.03]*20 + [0.] + [-.03]*20:
            _, _, attached, timer, _ = attachment_wrench(torch.tensor([[x, 0., 0.]]),
                torch.zeros(1, 3), torch.zeros(1, 3), cfg, attached, timer,
                cfg.physics_dt, torch.tensor([2.5]))
        self.assertTrue(attached.item())
        self.assertLess(timer.item(), .12)

    def test_axis_rotation_and_valid_pull_agree(self):
        cfg = TaskSettings(attachment_version=4, stem_response_version=1, tension_axis=(0., 2., 0.))
        self.assertFalse(self.evaluate((0., .03, 0.), cfg=cfg)[2].item())
        self.assertTrue(valid_pull(torch.tensor([[0., .03, 0.]]), cfg).item())
        self.assertFalse(valid_pull(torch.tensor([[-.03, 0., 0.]]), cfg).item())

    def test_invalid_parameters_rejected(self):
        for fields in ({'tension_axis': (0., 0., 0.)}, {'tension_axis': (float('nan'), 0., 1.)},
                       {'tension_hold_s': 0.}, {'lateral_stiffness_ratio': 0.}):
            with self.assertRaises(ValueError):
                TaskSettings(attachment_version=4, stem_response_version=1, **fields).validate()

    def test_lateral_stiffness_and_rest_gravity_support(self):
        force, _, attached, _, tension = self.evaluate((0., .02, 0.))
        self.assertAlmostEqual(force[0, 1].item(), -.6, places=5)
        self.assertEqual(tension.item(), 0.)
        force, torque, *_ = self.evaluate((0., 0., 0.))
        self.assertAlmostEqual(force[0, 2].item(), .035*9.81, places=5)
        self.assertEqual(torque.abs().sum().item(), 0.)

if __name__ == '__main__':
    unittest.main()
