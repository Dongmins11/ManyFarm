import unittest
import torch
from harvest_rl.entry_grasp import entry_gate,entry_cost
class EntryGrasp(unittest.TestCase):
    def test_open_entry_then_close_and_leave(self):
        local=torch.zeros(1,3);w=torch.tensor([.035]);q=torch.tensor([1.2]);no=torch.tensor([False])
        yes,gap=entry_gate(local,w,q,no,.07)
        self.assertTrue(yes.item());self.assertGreater(gap.item(),.07)
        self.assertTrue(entry_gate(local,w,torch.tensor([.8]),yes,.07)[0].item())
        self.assertFalse(entry_gate(local,w,torch.tensor([.8]),no,.07)[0].item())
        local[:,2]=.025
        self.assertFalse(entry_gate(local,w,q,yes,.07)[0].item())
    def test_width_and_offset_reject(self):
        no=torch.tensor([False]);q=torch.tensor([1.2])
        self.assertFalse(entry_gate(torch.zeros(1,3),torch.tensor([.05]),q,no,.07)[0].item())
        self.assertFalse(entry_gate(torch.tensor([[0.,.025,0.]]),torch.tensor([.035]),q,no,.07)[0].item())
    def test_normal_squeeze_not_penalized(self):
        t=lambda x:torch.tensor([x])
        args=[t(True),t(.02),t(2.),t(2.),t(1.),t(.03),t(.06),.07,.05]
        self.assertEqual(entry_cost(t(True),*args).item(),0.)
        self.assertGreater(entry_cost(t(False),*args).item(),0.)
