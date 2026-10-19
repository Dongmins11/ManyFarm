import unittest
import torch
from harvest_rl.entry_aux import entry_truth,EntryDecision,EntryAuxModel

class EntryAuxTests(unittest.TestCase):
    def test_entry_requires_depth_alignment_and_open_gap(self):
        local=torch.tensor([[0.,0.,0.],[0.,0.,-.04],[0.,0.,0.]])
        self.assertEqual(entry_truth(local,torch.full((3,),.035),torch.tensor([1.5,1.5,.2]),.07).tolist(),[True,False,False])
    def test_unknown_and_target_change_reset_dwell(self):
        d=EntryDecision()
        self.assertEqual([d.update(.99,'a',True) for _ in range(3)],['OUTSIDE','OUTSIDE','INSIDE'])
        self.assertEqual(d.update(.99,'b',True),'OUTSIDE')
        self.assertEqual(d.update(.99,'b',False),'UNKNOWN')
        self.assertEqual(d.update(float('nan'),'b',True),'UNKNOWN')
        self.assertEqual(d.update(.99,'b',True),'OUTSIDE')
    def test_geometry_veto_resets_dwell(self):
        d=EntryDecision()
        for _ in range(3):d.update(.999,'a',True)
        self.assertEqual(d.update(.999,'a',True,False),'OUTSIDE')
        self.assertEqual(d.update(.999,'a',True,True),'OUTSIDE')
    def test_logits_and_gradient(self):
        torch.set_num_threads(2);m=EntryAuxModel()
        y=m(torch.zeros((1,3,2,90,160,3),dtype=torch.uint8),torch.ones((1,3,2,90,160)),torch.ones((1,3,2),dtype=torch.bool),torch.zeros((1,3,23)))
        self.assertEqual(tuple(y.shape),(1,2));torch.nn.functional.cross_entropy(y,torch.tensor([1])).backward()
        self.assertTrue(torch.isfinite(m.actor[-1].weight.grad).all())
if __name__=='__main__':unittest.main()
