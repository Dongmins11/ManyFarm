import unittest
import torch
from harvest_rl.logic import early_detach_check

class EarlyDetachTest(unittest.TestCase):
    def step(self,pending,contact,grip,elapsed=0.,age=0.,distance=.005,slip=0.):
        t=lambda x:torch.tensor([x])
        return early_detach_check(t(pending),t(contact),t(grip),t(distance),t(slip),
            t(elapsed),t(age),.05,.25,.01,.02)
    def test_wait_for_strict_grip(self):
        p,elapsed,age,ok,bad=self.step(True,True,False)
        self.assertTrue(p.item());self.assertFalse(ok.item());self.assertFalse(bad.item())
        self.assertEqual(elapsed.item(),0.)
    def test_continuous_confirmation(self):
        p,t,a,ok,bad=self.step(True,True,True,elapsed=.20,age=.20)
        self.assertTrue(ok.item());self.assertFalse(p.item());self.assertFalse(bad.item())
    def test_loss_or_slip_rejects(self):
        for kw in [dict(contact=False),dict(contact=True,slip=.021),dict(contact=True,distance=.02),dict(contact=True,age=.61)]:
            p,t,a,ok,bad=self.step(True,grip=True,**kw)
            self.assertTrue(bad.item());self.assertFalse(ok.item())
    def test_later_catch_does_not_reenter(self):
        p,t,a,ok,bad=self.step(False,True,True,elapsed=.25)
        self.assertFalse(ok.item());self.assertFalse(p.item())

    def test_capture_orientation_is_independent_only_when_enabled(self):
        from harvest_rl.logic import pending_capture_grip
        contact=torch.tensor([True,True,False,False])
        aligned=torch.tensor([True,False,True,False])
        self.assertEqual(pending_capture_grip(contact,aligned).tolist(),[True,False,False,False])
        self.assertEqual(pending_capture_grip(contact,aligned,True).tolist(),[True,True,False,False])
    def test_capture_still_needs_dwell(self):
        p,t,a,ok,bad=self.step(True,True,True,elapsed=0.)
        self.assertTrue(p.item());self.assertFalse(ok.item())

    def test_confirmed_capture_fallback_is_opt_in_and_requires_contact(self):
        from harvest_rl.logic import captured_break_candidate as candidate
        yes=torch.ones(4,dtype=torch.bool)
        valid=torch.tensor([False,False,True,False]);contact=torch.tensor([True,True,True,False])
        confirmed=torch.tensor([False,True,True,True])
        self.assertEqual(candidate(yes,valid,contact,confirmed).tolist(),[True,False,False,False])
        self.assertEqual(candidate(yes,valid,contact,confirmed,True).tolist(),[True,True,False,False])
