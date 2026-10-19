import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import torch
from harvest_rl.logic import horizontal_grasp_alignment, centered_grasp_shaping
from harvest_rl.settings import TaskSettings

class HorizontalGraspTests(unittest.TestCase):
    def test_yaw_and_finger_order_free_vertical_rejected(self):
        q=torch.tensor([[1.,0,0,0],[.70710678,0,0,.70710678],[0.,0,0,1.],[.70710678,0,.70710678,0]])
        fruit=torch.tensor([[1.,0,0,0]]).repeat(4,1)
        error,ok=horizontal_grasp_alignment(q,fruit,.436332313)
        self.assertEqual(ok.tolist(),[True,True,True,False])
        self.assertAlmostEqual(error[-1].item(),1.,places=5)

    def test_cannot_cheat_by_tilting_fruit_to_vertical_jaws(self):
        tilt=torch.tensor([[.70710678,0,.70710678,0]])
        _,ok=horizontal_grasp_alignment(tilt,tilt,.436332313)
        self.assertFalse(ok.item())

    def test_fruit_axis_also_matters(self):
        hand=torch.tensor([[1.,0,0,0]])
        fruit=torch.tensor([[.70710678,0,.70710678,0]])
        self.assertFalse(horizontal_grasp_alignment(hand,fruit,.436332313)[1].item())

    def test_bad_orientation_has_no_closing_or_hold_bonus(self):
        cfg=TaskSettings(grasp_orientation='horizontal')
        args=(torch.tensor([.005]),torch.tensor([.005]),torch.tensor([1.]),torch.tensor([.95]),
              torch.tensor([True]),torch.tensor([.2]),.05,cfg)
        self.assertGreater(centered_grasp_shaping(*args).item(),0.)
        self.assertEqual(centered_grasp_shaping(*args,torch.tensor([False])).item(),0.)

    def test_invalid_mode_or_tolerance(self):
        for kw in ({'grasp_orientation':'bad'},{'grasp_angle_tolerance':0.},{'grasp_angle_tolerance':2.}):
            with self.assertRaises(ValueError):TaskSettings(**kw).validate()
