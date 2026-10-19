import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import torch
from harvest_rl.target_contract import TargetSession, TargetObservation, student_state
from harvest_rl.settings import TaskSettings


class TargetContractTests(unittest.TestCase):
    def setUp(self):
        self.session = TargetSession('arm_base', .3)
        self.session.assign('task-1', 'fruit-9')

    def observation(self, **kwargs):
        fields = dict(target_id='fruit-9',frame_id='arm_base',stamp_s=1.,position_m=(.3,.1,.2),valid=True)
        fields.update(kwargs)
        return TargetObservation(**fields)

    def test_identity_frame_and_time(self):
        for change in (dict(target_id='other'),dict(frame_id='camera'),dict(stamp_s=2.),dict(position_m=(float('nan'),0.,0.))):
            with self.assertRaises(ValueError):
                self.session.update(self.observation(**change),1.)
        self.session.update(self.observation(),1.)
        with self.assertRaises(ValueError):
            self.session.update(self.observation(stamp_s=.9),1.1)
        with self.assertRaises(RuntimeError):
            self.session.assign('another','fruit-9')

    def test_loss_is_not_success_or_id_change(self):
        self.session.update(self.observation(),1.)
        self.assertTrue(self.session.sample(1.1)[1])
        self.assertEqual(self.session.sample(1.5),((0.,0.,0.),False,.3))
        self.assertEqual(self.session.status,'RUNNING')
        self.assertEqual(self.session.target_id,'fruit-9')
        self.session.update(self.observation(stamp_s=1.6,valid=False),1.6)
        self.assertFalse(self.session.sample(1.6)[1])
        self.session.update(self.observation(stamp_s=1.7),1.7)
        self.assertTrue(self.session.sample(1.7)[1])

    def test_terminal_latched_and_explicit_reset(self):
        self.session.finish('CANCELLED','operator_cancel')
        with self.assertRaises(RuntimeError):
            self.session.finish('SUCCEEDED','late_message')
        with self.assertRaises(RuntimeError):
            self.session.assign('task-2','fruit-2')
        self.assertEqual(self.session.result()['reason'],'operator_cancel')
        self.session.reset()
        self.session.assign('task-2','fruit-2')

    def test_student_mask_and_coordinate_difference(self):
        p=torch.zeros(3,18);pos=torch.tensor([[.3,.1,.2]]).repeat(3,1)
        tcp=torch.tensor([[.1,0.,.1]]).repeat(3,1)
        state=student_state(p,pos,tcp,torch.tensor([True,False,True]),torch.tensor([.1,.1,.5]))
        self.assertEqual(state.shape,(3,23))
        torch.testing.assert_close(state[0,18:21],torch.tensor([.2,.1,.1]))
        self.assertEqual(state[1:,18:22].count_nonzero().item(),0)
        self.assertAlmostEqual(state[2,22].item(),.3)

    def test_single_external_legacy_reward_supported(self):
        TaskSettings(task='harvest',num_fruits=1,sequence=False,target_mode='external',reward_version=6).validate()
        with self.assertRaises(ValueError):
            TaskSettings(task='grasp',num_fruits=1,target_mode='external').validate()
        with self.assertRaises(ValueError):
            TaskSettings(num_fruits=3,target_mode='external').validate()
