import sys
from pathlib import Path
import unittest
import math
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from harvest_rl.settings import TaskSettings
from harvest_rl.behavior_contract import apply_behavior_mode

class BehaviorTests(unittest.TestCase):
    def test_checkpoint_preserved(self):
        s=TaskSettings(reward_version=6,grasp_orientation='free')
        before=s.as_dict();apply_behavior_mode(s,'checkpoint')
        self.assertEqual(before,s.as_dict())

    def test_strict_requires_both_behaviors(self):
        s=TaskSettings(reward_version=6,grasp_orientation='free',attachment_version=2)
        apply_behavior_mode(s,'strict');s.validate()
        self.assertEqual(s.grasp_orientation,'horizontal')
        self.assertGreaterEqual(s.reward_version,7)
        self.assertLessEqual(s.grasp_angle_tolerance,math.radians(25))
        self.assertGreaterEqual(s.release_stop_s,.3)
        self.assertLessEqual(s.release_speed,.05)
        self.assertEqual(s.attachment_version,2)

    def test_horizontal_preserves_release_and_reward(self):
        s=TaskSettings(reward_version=6,grasp_orientation='free')
        before=s.as_dict()
        apply_behavior_mode(s,'horizontal');s.validate()
        self.assertEqual(s.grasp_orientation,'horizontal')
        self.assertLessEqual(s.grasp_angle_tolerance,math.radians(25))
        for key in ('reward_version','release_stop_s','release_speed','attachment_version'):
            self.assertEqual(s.as_dict()[key],before[key])

    def test_unknown_mode_rejected(self):
        with self.assertRaises(ValueError):apply_behavior_mode(TaskSettings(),'unknown')

    def test_bottom_margin_does_not_relax_side_walls_or_velocity(self):
        import torch
        from harvest_rl.logic import settled_in_box
        s=TaskSettings();apply_behavior_mode(s,'strict')
        p=torch.tensor([[.4,0,.535],[.50,0,.535],[.4,0,.48],[.4,0,.535]])
        q=torch.tensor([[1.,0,0,0]]).repeat(4,1)
        v=torch.zeros_like(p);v[-1,0]=1
        self.assertEqual(settled_in_box(p,q,v,s).tolist(),[True,False,False,False])
