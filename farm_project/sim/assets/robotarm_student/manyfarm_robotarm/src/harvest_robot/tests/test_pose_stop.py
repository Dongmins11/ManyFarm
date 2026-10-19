import unittest
import math
import torch
from harvest_rl.logic import orientation_speed
class PoseStop(unittest.TestCase):
    def test_stationary_sign_and_moving(self):
        old=torch.tensor([[1.,0.,0.,0.]]*3)
        new=torch.tensor([[1.,0.,0.,0.],[-1.,0.,0.,0.],[math.cos(.05),0.,0.,math.sin(.05)]])
        torch.testing.assert_close(orientation_speed(old,new,.05),torch.tensor([0.,0.,2.]),atol=1e-4,rtol=1e-4)
    def test_normalized_input(self):
        old=torch.tensor([[2.,0.,0.,0.]])
        self.assertEqual(orientation_speed(old,old,.05).item(),0.)
