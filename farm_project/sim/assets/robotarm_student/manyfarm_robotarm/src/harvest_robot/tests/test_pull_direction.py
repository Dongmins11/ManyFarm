import unittest
import torch
from harvest_rl.logic import pull_direction_cost

class DirectionCost(unittest.TestCase):
    def test_outward_pull_free_lateral_and_push_cost(self):
        delta=torch.tensor([[-.03,0.,0.],[0.,.02,0.],[.012,0.,0.]])
        yes=torch.ones(3,dtype=torch.bool)
        torch.testing.assert_close(pull_direction_cost(delta,[-1.,0.,0.],yes,yes,.05),torch.tensor([0.,.1,.1]))
    def test_no_pregrasp_or_detached_cost_and_bounded(self):
        d=torch.ones(3,3)*10
        r=pull_direction_cost(d,[-1.,0.,0.],torch.tensor([False,True,True]),torch.tensor([True,False,True]),.05)
        torch.testing.assert_close(r,torch.tensor([0.,0.,.4]))
    def test_time_scaling_and_axis_normalization(self):
        d=torch.tensor([[0.,.02,0.]])
        yes=torch.ones(1,dtype=torch.bool)
        a=pull_direction_cost(d,[-1.,0.,0.],yes,yes,.05)
        b=pull_direction_cost(d,[-2.,0.,0.],yes,yes,.025)
        torch.testing.assert_close(a,2*b)
