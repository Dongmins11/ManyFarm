import unittest
import torch
from harvest_rl.settings import TaskSettings
from harvest_rl.logic import transport_stage_mask

class TransportContract(unittest.TestCase):
    def test_legacy_defaults_and_roundtrip(self):
        old=TaskSettings()
        self.assertFalse(old.transport_adaptive_grip)
        self.assertFalse(old.transport_pose_stop)
        old.transport_adaptive_grip=old.transport_pose_stop=True
        new=TaskSettings(**old.as_dict())
        self.assertTrue(new.transport_adaptive_grip and new.transport_pose_stop)

    def test_stage_scope(self):
        ref=torch.zeros(3,dtype=torch.bool)
        self.assertTrue(transport_stage_mask('transport',None,ref).all())
        for task in ('pull','place','harvest'):
            self.assertFalse(transport_stage_mask(task,None,ref).any())
        torch.testing.assert_close(transport_stage_mask('harvest',torch.tensor([0,1,2]),ref),torch.tensor([False,True,False]))
