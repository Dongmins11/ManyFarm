import unittest
import torch
from harvest_rl.logic import retain_detached_grip_target
class GripHold(unittest.TestCase):
    def test_open_attached_and_inactive_unchanged(self):
        p=torch.ones(5);q=torch.zeros(5);yes=torch.ones(5,dtype=torch.bool)
        detached=torch.tensor([True,True,False,True,True])
        active=torch.tensor([True,True,True,False,True])
        confirmed=torch.tensor([True,True,True,True,False])
        actions=torch.tensor([-1.,1.,-1.,-1.,-1.])
        out=retain_detached_grip_target(p,q,detached,confirmed,active,actions)
        torch.testing.assert_close(out,torch.tensor([1.,0.,0.,0.,0.]))
