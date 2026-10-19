import unittest
from harvest_rl.settings import TaskSettings
from harvest_rl.behavior_contract import apply_short_hook,prepare_harvest_transfer

class HarvestTransfer(unittest.TestCase):
    def test_preserves_hook_and_grip(self):
        s=TaskSettings(task='pull');apply_short_hook(s)
        s.pull_progress_reward=True;s.pull_recovery_shaping=True;s.pull_squeeze_rearm=True
        before=(s.spring_k,s.spring_d,s.stem_max_extension,s.gripper_effort)
        prepare_harvest_transfer(s);s.validate()
        self.assertEqual((s.task,s.reward_version,s.stem_response_version),('harvest',8,5))
        self.assertEqual(before,(s.spring_k,s.spring_d,s.stem_max_extension,s.gripper_effort))
        self.assertTrue(s.pull_squeeze_rearm)
        self.assertFalse(s.pull_progress_reward or s.pull_recovery_shaping)
        self.assertEqual(s.grasp_orientation,'horizontal')
    def test_grasp_checkpoint_rejected(self):
        s=TaskSettings(task='grasp');apply_short_hook(s)
        with self.assertRaises(ValueError):prepare_harvest_transfer(s)

class SingleBankValidation(unittest.TestCase):
    def test_single_transport_place_bank_allowed(self):
        for task in ('transport','place'):
            s=TaskSettings(task='pull');apply_short_hook(s);prepare_harvest_transfer(s)
            s.task=task;s.target_mode='random';s.start_bank='physical.pt';s.num_fruits=1;s.sequence=False
            s.validate()
    def test_random_single_grasp_still_rejected(self):
        s=TaskSettings(task='grasp',target_mode='random',num_fruits=1,sequence=False)
        with self.assertRaises(ValueError):s.validate()
