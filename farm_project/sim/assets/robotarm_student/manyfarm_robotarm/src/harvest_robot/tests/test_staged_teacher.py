import unittest
import torch
from harvest_runtime.staged_teacher import next_stage
class StageTests(unittest.TestCase):
    def test_order_and_no_fallback(self):
        stage=torch.tensor([0,0,1,2]);yes=torch.ones(4,dtype=torch.bool)
        result=next_stage(stage,yes,torch.tensor([False,True,True,False]),yes,torch.tensor([False,False,True,False]))
        torch.testing.assert_close(result,torch.tensor([0,1,2,2]))
    def test_loss_does_not_advance(self):
        torch.testing.assert_close(next_stage(torch.tensor([0,1]),torch.tensor([True,True]),torch.tensor([True,True]),torch.tensor([False,False]),torch.tensor([True,True])),torch.tensor([0,1]))

class ExpertClockTest(unittest.TestCase):
    def test_transition_resets_local_clock_without_changing_input(self):
        from types import SimpleNamespace
        from harvest_runtime.staged_teacher import StagedTeacher
        class Expert:
            def act_inference(self,obs):
                self.seen=obs['policy'].clone()
                return torch.zeros(2,6)
        router=StagedTeacher.__new__(StagedTeacher)
        router.env=SimpleNamespace(num_envs=2,device='cpu',max_episode_length=400,
            valid_detach=torch.tensor([True,False]),has_retained=torch.tensor([True,False]),
            grip=torch.tensor([True,True]),release_armed=torch.tensor([False,False]))
        router.stage=torch.zeros(2,dtype=torch.long);router.active=torch.ones(2,dtype=torch.bool)
        router.stage_steps=torch.tensor([200.,200.]);router.experts=[Expert(),Expert(),Expert()]
        obs={'policy':torch.zeros(2,82)};obs['policy'][:,42]=.5
        router(obs)
        torch.testing.assert_close(router.experts[1].seen[:,42],torch.tensor([1.,.5]))
        torch.testing.assert_close(obs['policy'][:,42],torch.tensor([.5,.5]))

class FixedReleaseTest(unittest.TestCase):
    def test_only_place_stage_actions_are_replaced(self):
        from types import SimpleNamespace
        from harvest_runtime.staged_teacher import StagedTeacher
        class Expert:
            def act_inference(self,obs):return torch.ones(2,6)*.4
        r=StagedTeacher.__new__(StagedTeacher)
        r.env=SimpleNamespace(num_envs=2,device='cpu',max_episode_length=400,
            valid_detach=torch.ones(2,dtype=torch.bool),has_retained=torch.ones(2,dtype=torch.bool),
            grip=torch.ones(2,dtype=torch.bool),release_armed=torch.tensor([False,True]))
        r.stage=torch.ones(2,dtype=torch.long);r.active=torch.ones(2,dtype=torch.bool)
        r.stage_steps=torch.zeros(2);r.experts=[Expert(),Expert(),Expert()];r.release_mode='fixed'
        out=r({'policy':torch.zeros(2,82)})
        torch.testing.assert_close(out[0],torch.ones(6)*.4)
        torch.testing.assert_close(out[1],torch.tensor([0.,0.,0.,0.,0.,.15]))

        r.diagnostic_transport_scale=.25
        r.stage=torch.tensor([1,2])
        out=r({'policy':torch.zeros(2,82)})
        torch.testing.assert_close(out[0],torch.tensor([.1,.1,.1,.1,.1,.4]))
        torch.testing.assert_close(out[1],torch.tensor([0.,0.,0.,0.,0.,.15]))
        r.diagnostic_transport_scale=1.
        r.block_transport_opening=True
        r.stage=torch.tensor([1,2])
        out=r({'policy':torch.zeros(2,82)})
        torch.testing.assert_close(out[0],torch.tensor([.4,.4,.4,.4,.4,0.]))
        torch.testing.assert_close(out[1],torch.tensor([0.,0.,0.,0.,0.,.15]))

class TargetResetTest(unittest.TestCase):
    def test_new_target_resets_routing_not_world(self):
        from types import SimpleNamespace
        from harvest_runtime.staged_teacher import StagedTeacher
        r=StagedTeacher.__new__(StagedTeacher)
        r.env=SimpleNamespace(collected=torch.tensor([[True,False]]))
        r.stage=torch.tensor([2]);r.stage_steps=torch.tensor([90.]);r.active=torch.tensor([False]);r.experts=[]
        r.recovery=SimpleNamespace(targets={0:'old target'})
        r.reset()
        self.assertEqual(r.stage.item(),0)
        self.assertEqual(r.stage_steps.item(),0)
        self.assertTrue(r.active.item())
        self.assertEqual(r.recovery.targets,{})
        torch.testing.assert_close(r.env.collected,torch.tensor([[True,False]]))

class EntryHandoffTest(unittest.TestCase):
    def test_grasp_to_pull_preserves_scene_and_does_not_fall_back(self):
        from types import SimpleNamespace
        from harvest_runtime.staged_teacher import StagedTeacher
        class Expert:
            def __init__(self,value):self.value=value
            def act_inference(self,obs):
                self.seen=obs['policy'].clone()
                return torch.full((2,6),self.value)
        r=StagedTeacher.__new__(StagedTeacher)
        r.env=SimpleNamespace(num_envs=2,device='cpu',max_episode_length=400,
            valid_detach=torch.zeros(2,dtype=torch.bool),has_retained=torch.zeros(2,dtype=torch.bool),
            grip=torch.ones(2,dtype=torch.bool),has_grasped=torch.tensor([True,False]),
            attached=torch.ones(2,dtype=torch.bool),release_armed=torch.zeros(2,dtype=torch.bool),
            targets=torch.ones(2,6),_t=lambda x:x)
        r.stage=torch.zeros(2,dtype=torch.long);r.active=torch.ones(2,dtype=torch.bool)
        r.stage_steps=torch.tensor([30.,40.]);r.experts=[Expert(.1),Expert(.2),Expert(.3)]
        r.grasp_expert=Expert(.4);r.grasp_active=torch.ones(2,dtype=torch.bool)
        obs={'policy':torch.zeros(2,82)}
        out=r(obs)
        torch.testing.assert_close(out[:,0],torch.tensor([.1,.4]))
        torch.testing.assert_close(r.env.expert_stage,torch.tensor([0,-1]))
        torch.testing.assert_close(r.experts[0].seen[:,42],torch.tensor([1.,.9]))
        torch.testing.assert_close(r.env.targets,torch.ones(2,6))
        # Recurrent handoff must not mutate the supplied observation clock.
        torch.testing.assert_close(obs['policy'],torch.zeros(2,82))
        r.env.grip.zero_();out=r(obs)
        torch.testing.assert_close(out[:,0],torch.tensor([.1,.4]))
        # Verified early separation can hand off without reattaching the fruit.
        r.env.grip.fill_(True);r.env.has_grasped.fill_(True)
        r.env.attached.zero_();r.env.valid_detach.fill_(True)
        out=r(obs)
        self.assertFalse(r.grasp_active.any())
        torch.testing.assert_close(out[:,0],torch.tensor([.1,.1]))
        r.reset()
        self.assertTrue(r.grasp_active.all())
        torch.testing.assert_close(r.env.expert_stage,torch.tensor([-1,-1]))

class RetentionGuardTest(unittest.TestCase):
    def test_only_captured_early_retention_blocks_opening(self):
        from harvest_runtime.staged_teacher import retention_open_guard
        yes=torch.ones(7,dtype=torch.bool);no=~yes
        actions=torch.ones(7,6)*.4;actions[6,5]=-.3
        stage=torch.tensor([0,0,1,2,0,0,0])
        attached=torch.tensor([False,True,False,False,False,False,False])
        contact=torch.tensor([True,True,True,True,False,True,True])
        valid=torch.tensor([True,True,True,True,True,False,True])
        out,blocked=retention_open_guard(actions,stage,yes,attached,valid,no,contact)
        torch.testing.assert_close(out[:,:5],actions[:,:5])
        torch.testing.assert_close(out[:,5],torch.tensor([0.,.4,.4,.4,.4,.4,-.3]))
        self.assertEqual(blocked.tolist(),[True,False,False,False,False,False,False])
        out,_=retention_open_guard(actions,stage,yes,attached,valid,yes,contact)
        self.assertEqual(out[5,5].item(),0.)
