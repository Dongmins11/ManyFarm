import unittest
import torch
from types import SimpleNamespace
from harvest_rl.exploration import initialize_place_gripper
class PlaceTransfer(unittest.TestCase):
    def test_preserves_arm_and_shared_features(self):
        actor=torch.nn.Sequential(torch.nn.Linear(82,16),torch.nn.Tanh(),torch.nn.Linear(16,6))
        before={k:v.clone() for k,v in actor.state_dict().items()}
        initialize_place_gripper(SimpleNamespace(actor=actor))
        torch.testing.assert_close(actor[0].weight,before['0.weight'])
        torch.testing.assert_close(actor[0].bias,before['0.bias'])
        torch.testing.assert_close(actor[2].weight[:5],before['2.weight'][:5])
        torch.testing.assert_close(actor[2].bias[:5],before['2.bias'][:5])
        self.assertEqual(actor[2].weight[5].count_nonzero(),0)
        self.assertEqual(actor[2].bias[5],0)
