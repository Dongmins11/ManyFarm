import unittest
import torch
from harvest_rl.logic import release_intent_step
class ReleaseIntent(unittest.TestCase):
    def run_step(self,armed=True,age=0.,action=.15,still=True,lost=True):
        return release_intent_step(torch.tensor([armed]),torch.tensor([age]),torch.tensor([lost]),torch.tensor([action]),torch.tensor([still]),.05)
    def test_approved_only_after_arming(self):
        self.assertTrue(self.run_step()[2].item())
        self.assertFalse(self.run_step(armed=False)[2].item())
        self.assertFalse(self.run_step()[0].item())
    def test_cancel_motion_closing_and_expiry(self):
        for kw in [dict(still=False),dict(action=-.01),dict(age=1.5)]:
            result=self.run_step(**kw)
            self.assertFalse(result[2].item());self.assertFalse(result[0].item())
    def test_waiting_does_not_award_success(self):
        intent,age,approved=self.run_step(lost=False)
        self.assertTrue(intent.item());self.assertFalse(approved.item())
        self.assertAlmostEqual(age.item(),.05)

class PlacementOutcome(unittest.TestCase):
    def test_unapproved_release_can_settle_but_flight_cannot_succeed(self):
        from harvest_rl.logic import placement_outcome, dwell
        b=lambda x: torch.tensor([x])
        _,_,approved=release_intent_step(b(True),torch.tensor([0.]),b(True),torch.tensor([.15]),b(False),.05)
        self.assertFalse(approved.item())
        timer=torch.zeros(1)
        for inside in [False,True,True,False,True,True,True]:
            valid=placement_outcome(b(inside),b(False),b(False),b(True),b(True))
            timer=dwell(timer,valid,.05)
        self.assertAlmostEqual(timer.item(),.15)
    def test_contact_attachment_or_missing_harvest_history_blocks_placement(self):
        from harvest_rl.logic import placement_outcome
        b=lambda x: torch.tensor([x])
        for values in [(False,False,False,True,True),(True,True,False,True,True),
                       (True,False,True,True,True),(True,False,False,False,True),
                       (True,False,False,True,False)]:
            self.assertFalse(placement_outcome(*(b(v) for v in values)).item())
        self.assertTrue(placement_outcome(*(b(v) for v in (True,False,False,True,True))).item())
