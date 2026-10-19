"""CPU-only regression tests: python -m unittest discover -s src/harvest_robot/tests."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import numpy as np
import torch
from harvest_rl.settings import TaskSettings, URDF
from harvest_rl.kinematics import ArmKinematics
from harvest_rl.logic import attachment_wrench, bilateral_contact, contained_in_box, valid_pull
from harvest_rl.policy import VisionStudent, History
from harvest_rl.logic import limited_joint_targets, dwell, stage_success, compliant_gripper_hold


class HarvestCoreTests(unittest.TestCase):
    def test_contact_substeps_validation(self):
        for value in (1, 2, 4):
            TaskSettings(contact_substeps=value).validate()
        for value in (0, 3, -1, True, 2.0):
            with self.assertRaisesRegex(ValueError, 'contact_substeps'):
                TaskSettings(contact_substeps=value).validate()

    def test_native_recovery_requires_strict_reconfirmation(self):
        from harvest_rl.logic import recover_pending_detach
        pending=torch.tensor([True]); elapsed=torch.zeros(1);age=elapsed.clone();lost=elapsed.clone()
        def step(grip, contact=True, distance=.0101, slip=0.):
            nonlocal pending,elapsed,age,lost
            pending,elapsed,accepted,rejected,age,lost=recover_pending_detach(
                pending,torch.tensor([grip]),torch.tensor([contact]),torch.tensor([distance]),
                torch.tensor([slip]),elapsed,age,lost,.05,.25,.012,.015)
            return accepted.item(), rejected.item()
        self.assertEqual(step(False), (False,False))  # 10.1 mm is provisional, not success
        self.assertEqual(step(False,False), (False,False))
        for _ in range(4): self.assertEqual(step(True,distance=.008),(False,False))
        self.assertEqual(step(True,distance=.008),(True,False))

    def test_native_recovery_rejects_drop_and_indefinite_grace(self):
        from harvest_rl.logic import recover_pending_detach
        for case in ('lost','slip','far','timeout'):
            pending=torch.tensor([True]);elapsed=torch.zeros(1);age=elapsed.clone();lost=elapsed.clone()
            for _ in range(16):
                pending,elapsed,accepted,rejected,age,lost=recover_pending_detach(
                    pending,torch.tensor([False]),torch.tensor([case!='lost']),
                    torch.tensor([.016 if case=='far' else .011]),
                    torch.tensor([.013 if case=='slip' else 0.]),
                    elapsed,age,lost,.05,.25,.012,.015)
                self.assertFalse(accepted.item())
                if rejected.item(): break
            self.assertTrue(rejected.item(),case)
            self.assertFalse(pending.item())

    def test_pending_native_detach_requires_unbroken_hold(self):
        from harvest_rl.logic import update_pending_detach
        pending=torch.tensor([True,True,True,False]);elapsed=torch.zeros(4)
        # Case1 continuous hold; case2 contact loss; case3 slip; case4 never admitted.
        for step in range(5):
            grip=torch.tensor([True,step!=1,True,True])
            slip=torch.tensor([0.,0.,.02 if step==1 else 0.,0.])
            pending,elapsed,accepted,rejected=update_pending_detach(pending,grip,slip,elapsed,.05,.25,.012)
            if step==1:self.assertEqual(rejected.tolist(),[False,True,True,False])
        self.assertEqual(accepted.tolist(),[True,False,False,False])
        self.assertFalse(pending.any())

    def test_warm_start_normalizer_adaptation(self):
        from harvest_rl.exploration import adapt_warm_start_normalizers
        from types import SimpleNamespace
        n=SimpleNamespace(count=torch.tensor(300000000),_mean=torch.tensor([[2.,4.]]),
                          _var=torch.tensor([[0.,9.]]),_std=torch.tensor([[0.,3.]]))
        p=SimpleNamespace(actor_obs_normalizer=n)
        adapt_warm_start_normalizers(p)
        self.assertEqual(n.count.item(),8192)
        torch.testing.assert_close(n._mean,torch.tensor([[0.,4.]]))
        torch.testing.assert_close(n._std,torch.tensor([[1.,3.]]))
        torch.testing.assert_close(n._var,torch.tensor([[1.,9.]]))

    def test_exploration_reset_and_optimizer_bound(self):
        from harvest_rl.exploration import configure_exploration
        p=torch.nn.Module();p.std=torch.nn.Parameter(torch.full((6,),7.))
        p.actor=torch.nn.Linear(2,2);weight=p.actor.weight.detach().clone()
        opt=torch.optim.SGD(p.parameters(),lr=1.)
        handle=configure_exploration(p,opt,reset_std=.3)
        torch.testing.assert_close(p.std,torch.full((6,),.3))
        torch.testing.assert_close(p.actor.weight,weight)
        (-100*p.std.sum()).backward();opt.step()
        self.assertTrue(bool((p.std<=.6).all()))
        opt.zero_grad();(100*p.std.sum()).backward();opt.step()
        self.assertTrue(bool((p.std>=.05).all()))
        handle.remove()

    def test_recent_metrics_window_and_replay_are_separate(self):
        from harvest_rl.recent_metrics import RecentEpisodes
        r=RecentEpisodes(4,'cpu')
        self.assertEqual(r.metrics()['Recent/episodes'].item(),0)
        r.add(torch.tensor([1,0,0],dtype=torch.bool),torch.tensor([0,1,0],dtype=torch.bool),torch.tensor([1,0,0],dtype=torch.bool))
        m=r.metrics()
        self.assertEqual(m['Recent/replay_success_rate'].item(),1.)
        self.assertEqual(m['Recent/primary_success_rate'].item(),0.)
        self.assertAlmostEqual(m['Recent/timeout_rate'].item(),1/3,places=6)
        r.add(torch.tensor([1,1,1],dtype=torch.bool),torch.zeros(3,dtype=torch.bool),torch.zeros(3,dtype=torch.bool))
        m=r.metrics()
        self.assertEqual(m['Recent/episodes'].item(),4)
        self.assertEqual(m['Recent/success_rate'].item(),.75)
        self.assertEqual(m['Recent/failure_rate'].item(),0.)
        self.assertEqual(m['Recent/replay_episodes'].item(),0.)

    def test_transport_replay_sampling_and_validation(self):
        from harvest_rl.stage_bank import StageStartBank
        b=StageStartBank.__new__(StageStartBank)
        b.indices=torch.tensor([2,3]);b.replay_indices=torch.tensor([0,1]);b.replay_fraction=.2
        torch.manual_seed(42);sample=b.sample_indices(torch.arange(10000))
        self.assertTrue(.18<float((sample<2).float().mean())<.22)
        b.replay_fraction=0
        self.assertTrue((b.sample_indices(torch.arange(100))>=2).all())
        from dataclasses import replace
        cfg=TaskSettings(task='transport',reward_version=8,attachment_version=3,stage_transfer=True,
                         target_mode='random',sequence=True,num_fruits=3,start_bank='physical.pt',
                         transport_start_min=.10,transport_start_max=.15,transport_replay_fraction=.2)
        cfg.validate()
        for change in ({'transport_replay_fraction':1.},{'transport_start_min':.03},{'task':'place'}):
            with self.assertRaises(ValueError):replace(cfg,**change).validate()

    def test_transport_arm_head_reset_preserves_gripper_and_features(self):
        from harvest_rl.exploration import scale_warm_start_arm
        from types import SimpleNamespace
        actor=torch.nn.Sequential(torch.nn.Linear(82,8),torch.nn.ELU(),torch.nn.Linear(8,6))
        old={k:v.clone() for k,v in actor.state_dict().items()}
        x=torch.randn(5,82);gripper=actor(x)[:,-1].detach().clone()
        scale_warm_start_arm(SimpleNamespace(actor=actor),0.)
        torch.testing.assert_close(actor(x)[:,:5],torch.zeros(5,5))
        torch.testing.assert_close(actor(x)[:,-1],gripper)
        torch.testing.assert_close(actor[0].weight,old['0.weight'])
        with self.assertRaises(ValueError):scale_warm_start_arm(SimpleNamespace(actor=actor),-1.)

    def test_transport_curriculum_uses_target_slot_and_preserves_poses(self):
        from harvest_rl.stage_bank import select_start_indices
        from harvest_rl.logic import placement_target
        cfg=TaskSettings(task='transport',reward_version=8,transport_start_min=.03,transport_start_max=.08)
        fruit=torch.zeros(3,3,13);target=torch.tensor([2,0,1])
        fruit[torch.arange(3),target,:3]=placement_target(cfg,'cpu')+torch.tensor([[.07,0,0],[.15,0,0],[.04,0,0]])
        fruit[:,:,3]=1
        before=fruit.clone()
        states={'fruits':fruit,'target_index':target}
        ids,_=select_start_indices(states,cfg)
        self.assertEqual(ids.tolist(),[0]);torch.testing.assert_close(fruit,before)
        cfg.transport_start_min=.25;cfg.transport_start_max=.3
        with self.assertRaisesRegex(ValueError,'No physical'):select_start_indices(states,cfg)
        cfg.transport_start_min=cfg.transport_start_max=0
        ids,_=select_start_indices(states,cfg);self.assertEqual(ids.tolist(),[0,1,2])

    def test_transport_curriculum_rejects_invalid_ranges(self):
        from dataclasses import replace
        cfg=TaskSettings(task='transport',reward_version=8,attachment_version=3,stage_transfer=True,
                         target_mode='random',sequence=True,num_fruits=3,start_bank='physical.pt',transport_start_min=.03,transport_start_max=.08)
        cfg.validate()
        for overrides in ({'transport_start_max':.02},{'transport_start_max':0},
                          {'transport_start_min':-.1},{'task':'place'}):
            with self.assertRaises(ValueError):replace(cfg,**overrides).validate()

    def test_stage_task_requires_certified_predecessor_bank(self):
        for task in ('transport','place'):
            with self.assertRaises(ValueError):TaskSettings(task=task,reward_version=8).validate()
            TaskSettings(task=task,reward_version=8,attachment_version=3,stage_transfer=True,
                         sequence=True,target_mode='random',num_fruits=3,start_bank='physical.pt').validate()
        with self.assertRaises(ValueError):TaskSettings(task='harvest',start_bank='physical.pt').validate()

    def test_harvest8_milestones_do_not_pay_for_quick_failure(self):
        from harvest_rl.logic import harvest_stage_bonus
        t=torch.tensor([True]);f=~t
        total=harvest_stage_bonus(t,f,f,f)+harvest_stage_bonus(f,t,f,f)+harvest_stage_bonus(f,f,t,f)
        self.assertLess(total.item(),0)
        self.assertEqual(harvest_stage_bonus(f,f,f,t).item(),-5)
        self.assertEqual(harvest_stage_bonus(f,f,t,t).item(),-10)
        TaskSettings(task='harvest',reward_version=8).validate()
        with self.assertRaises(ValueError):TaskSettings(task='pull',reward_version=8).validate()

    def test_transport_potential_telescopes_and_guides_retreat(self):
        from harvest_rl.logic import transport_potential_step
        origin=torch.tensor([.4]);previous=torch.zeros(1);yes=torch.tensor([True]);no=~yes
        rewards=[]
        for distance,done in [( .4,False),(.3,False),(.3,False),(.4,False),(.2,False),(.2,True)]:
            reward,previous=transport_potential_step(torch.tensor([distance]),origin,previous,yes,yes if done else no)
            rewards.append(reward.item())
        self.assertGreater(rewards[1],0)
        self.assertLess(rewards[2],0)
        self.assertLess(rewards[3],0)
        self.assertAlmostEqual(sum(.99**i*r for i,r in enumerate(rewards)),0,places=5)
        self.assertEqual(previous.item(),0)

    def test_legacy_transport_progress_has_no_hover_or_cycle_payout(self):
        from harvest_rl.logic import harvest_place_shaping
        best=torch.tensor([float('inf')]);zero=torch.zeros(1);yes=torch.tensor([True]);no=~yes
        paid=no;best_time=zero
        rewards=[]
        for distance in (.4,.3,.3,.4,.3,.2):
            reward,best,paid,best_time=harvest_place_shaping(torch.tensor([distance]),best,yes,
                no,paid,zero,best_time,.05,.6,progress_scale=30.)
            rewards.append(reward.item())
        self.assertAlmostEqual(sum(rewards),6.,places=5)
        for i in [0,2,3,4]:self.assertEqual(rewards[i],0)

    def test_batched_fruit_sampling_spacing_and_failure(self):
        from harvest_rl.sequence import sample_separated
        candidates=torch.tensor([[0.,0,0],[.2,0,0],[.4,0,0],[.6,0,0]])
        torch.manual_seed(42)
        picked=[]
        for _ in range(3):
            current=sample_separated(candidates,513,picked,.105)
            self.assertEqual(current.shape,(513,3))
            for previous in picked:self.assertTrue(((current-previous).norm(dim=-1)>.105).all())
            self.assertTrue((current[:,None]==candidates[None]).all(-1).any(-1).all())
            picked.append(current)
        with self.assertRaises(RuntimeError):sample_separated(candidates[:1],2,[torch.zeros(2,3)],.105)
        self.assertEqual(sample_separated(candidates,0,[],.105).shape,(0,3))

    def test_stage_normalization_preserves_learned_inputs(self):
        from harvest_rl.exploration import prepare_stage_normalizers
        from types import SimpleNamespace
        mean=torch.arange(82,dtype=torch.float32).reshape(1,-1)
        std=torch.ones_like(mean)*2
        std[:,[38,40,41,43,79,80]]=0
        std[:,53]=0  # unused fruit input must remain untouched
        norm=SimpleNamespace(_mean=mean.clone(),_std=std.clone(),_var=std.square(),
                             count=torch.tensor(19000000),until=100)
        policy=SimpleNamespace(actor_obs_normalizer=norm,critic_obs_normalizer=norm)
        prepare_stage_normalizers(policy)
        torch.testing.assert_close(norm._mean,mean)
        self.assertEqual(norm._std[0,38],1)
        self.assertEqual(norm._std[0,40],1)
        self.assertEqual(norm._std[0,39],2)  # learned grasp progress preserved
        self.assertEqual(norm._std[0,53],0)
        self.assertEqual(norm.count.item(),19000000)
        self.assertEqual(norm.until,0)

    def test_multifruit_stage_contracts(self):
        for task in ('grasp','hold','pull','harvest'):
            cfg=TaskSettings(task=task,sequence=True,num_fruits=3,target_mode='random',
                             attachment_version=3,lock_attachment=task in ('grasp','hold'))
            cfg.validate()
        for task in ('pull','harvest'):
            with self.assertRaises(ValueError):
                TaskSettings(task=task,attachment_version=3,lock_attachment=True).validate()
        with self.assertRaises(ValueError):
            TaskSettings(task='grasp',attachment_version=2,lock_attachment=True).validate()

    def test_random_assignment_eligibility_and_coverage(self):
        from harvest_rl.sequence import random_target
        ripe=torch.tensor([[True,False,True,True]]).repeat(512,1)
        collected=torch.tensor([[False,False,True,False]]).repeat(512,1)
        target,valid=random_target(ripe,collected)
        self.assertTrue(valid.all())
        self.assertEqual(set(target.tolist()),{0,3})
        _,valid=random_target(ripe,torch.ones_like(collected))
        self.assertFalse(valid.any())
        with self.assertRaises(ValueError):TaskSettings(target_mode="random").validate()

    def test_force_break_requires_extension_tension_and_dwell(self):
        s=TaskSettings(attachment_version=2)
        # Far but unloading; fast but tiny extension; sustained tensile pull in Y.
        d=torch.tensor([[.04,0,0],[.001,0,0],[0,.025,0]],dtype=torch.float32)
        v=torch.tensor([[-3.2,0,0],[2.,0,0],[0,0,0]],dtype=torch.float32)
        a=torch.ones(3,dtype=torch.bool); t=torch.zeros(3)
        for _ in range(12):
            _,_,a,t,load=attachment_wrench(d,v,d*0,s,a,t,s.physics_dt,torch.full((3,),2.5))
        self.assertEqual(a.tolist(),[True,True,False])
        self.assertTrue(valid_pull(d,s)[2])
        # High force on one substep cannot accumulate across an unloading step.
        a=torch.ones(1,dtype=torch.bool); t=torch.zeros(1)
        for _ in range(20):
            for velocity in (torch.zeros(1,3),torch.tensor([[0.,-3.2,0.]])):
                _,_,a,t,_=attachment_wrench(d[2:],velocity,d[2:]*0,s,a,t,s.physics_dt,torch.tensor([2.5]))
        self.assertTrue(a.item())

    def test_separation_reward_has_no_retreat_or_loiter_payout(self):
        from harvest_rl.logic import separation_stage_shaping
        reward=separation_stage_shaping(torch.tensor([1.,1.,1.]),
            torch.tensor([False,True,True]),torch.tensor([True,True,False]),.05)
        torch.testing.assert_close(reward,torch.tensor([1.,-.01,0.]))

    def test_harvest_progress_release_and_settling_cannot_repeat(self):
        from harvest_rl.logic import harvest_place_shaping, placement_target
        z=torch.zeros(1); yes=torch.tensor([True]); no=~yes
        best=torch.full((1,),float("inf")); paid=no; settled=z
        def step(distance, eligible=yes, released=no, time=0.):
            nonlocal best,paid,settled
            r,best,paid,settled=harvest_place_shaping(torch.tensor([distance]),best,
                eligible,released,paid,torch.tensor([time]),settled,.05,.6)
            return r.item()
        self.assertEqual(step(.3,no),0.)
        self.assertEqual(step(.3),0.)
        self.assertAlmostEqual(step(.2),1.,places=5)
        for d in (.2,.3,.2):self.assertEqual(step(d),0.)
        self.assertEqual(step(.1,no),0.) # a dropped fruit earns no transport progress
        self.assertEqual(step(.2,no,yes),3.)
        self.assertEqual(step(.2,no,yes),0.)
        self.assertAlmostEqual(step(.2,no,yes,.3),1.,places=5)
        self.assertEqual(step(.2,no,yes,0.),0.)
        self.assertEqual(step(.2,no,yes,.3),0.)
        self.assertAlmostEqual(step(.2,no,yes,.6),1.,places=5)
        cfg=TaskSettings(reward_version=6);target=placement_target(cfg,"cpu")[None]
        self.assertTrue(contained_in_box(target,torch.zeros_like(target),cfg).item())
        self.assertFalse(contained_in_box(target,torch.ones_like(target),cfg).item())

    def test_prepared_bank_verifies_actual_contents(self):
        import tempfile, hashlib
        from run import validate_prepared_bank
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory); q=np.zeros((1,6)); points=np.zeros((1,3)); home=np.zeros(6)
            meta={"workspace_sha256":hashlib.sha256(q.tobytes()+points.tobytes()+home.tobytes()).hexdigest()}
            for name in ("harvest_robot.usd","harvest_training.urdf"):(root/name).touch()
            np.savez(root/"workspace.npz",q=q,points=points,home=home)
            validate_prepared_bank(root,meta)
            np.savez(root/"workspace.npz",q=q+1,points=points,home=home)
            with self.assertRaises(ValueError):validate_prepared_bank(root,meta)

    def test_oriented_body_accepts_edge_contact_but_not_outside_or_rim(self):
        from harvest_rl.logic import settled_in_box, fruit_bounds, above_box, placement_target
        cfg=TaskSettings(reward_version=7)
        q=torch.tensor([[1.,0,0,0]])
        # Body touching inner wall and resting on floor; root differs from body centre.
        p=torch.tensor([[cfg.box_min[0]+cfg.diameter/2,0,cfg.box_min[2]+cfg.length*.48]])
        self.assertTrue(settled_in_box(p,q,p*0,cfg).item())
        outside=p.clone();outside[:,0]-=.006
        self.assertFalse(settled_in_box(outside,q,p*0,cfg).item())
        rim=p.clone();rim[:,2]=cfg.box_max[2]
        self.assertFalse(settled_in_box(rim,q,p*0,cfg).item())
        self.assertFalse(settled_in_box(p,q,torch.ones_like(p),cfg).item())
        rotated=torch.tensor([[2**-.5,0,2**-.5,0.]])
        center,extent=fruit_bounds(p,rotated,cfg)
        torch.testing.assert_close(extent,torch.tensor([[cfg.length*.4,cfg.diameter/2,cfg.diameter/2]]))
        target=placement_target(cfg,"cpu")[None]
        self.assertTrue(above_box(target,q,cfg).item())
        self.assertTrue(above_box(target,rotated,cfg).item())

    def test_release_requires_stop_and_rejects_throw(self):
        from harvest_rl.logic import controlled_release
        cfg=TaskSettings();yes=torch.tensor([True]);no=~yes;zero=torch.zeros(1)
        self.assertTrue(controlled_release(yes,yes,yes,zero,zero,zero,cfg).item())
        for armed,zone,previous,tcp,horizontal in ((no,yes,zero,zero,zero),
            (yes,no,zero,zero,zero),(yes,yes,zero+.2,zero,zero),
            (yes,yes,zero,zero+.2,zero),(yes,yes,zero,zero,zero+.2)):
            self.assertFalse(controlled_release(yes,armed,zone,previous,tcp,horizontal,cfg).item())
        timer=zero
        for _ in range(5):timer=dwell(timer,yes,.05)
        self.assertLess(timer.item(),cfg.release_stop_s)
        timer=dwell(timer,no,.05)
        self.assertEqual(timer.item(),0.)

    def test_sequence_ripeness_selection_and_completed_fruit_protection(self):
        from harvest_rl.sequence import fruit_colors,next_target,forbidden_detach
        self.assertEqual(fruit_colors(3,True),["Red","Yellow","Green"])
        self.assertEqual(fruit_colors(3,False),["Red","Green","Green"])
        ripe=torch.tensor([True,True,False])
        positions=torch.tensor([[[1.,0,0],[2.,0,0],[.1,0,0]],[[2.,0,0],[1.,0,0],[.1,0,0]]])
        collected=torch.zeros(2,3,dtype=torch.bool)
        targets,remaining=next_target(positions,torch.zeros(2,3),ripe,collected)
        self.assertEqual(targets.tolist(),[0,1])
        collected[torch.arange(2),targets]=True
        targets,remaining=next_target(positions,torch.zeros(2,3),ripe,collected)
        self.assertEqual(targets.tolist(),[1,0])
        attached=~collected
        self.assertFalse(forbidden_detach(attached,collected,targets).any())
        attached[:,2]=False
        self.assertTrue(forbidden_detach(attached,collected,targets).all())
        collected[:,:2]=True
        _,remaining=next_target(positions,torch.zeros(2,3),ripe,collected)
        self.assertFalse(remaining.any())
        from harvest_rl.logic import settled_in_box
        cfg=TaskSettings(sequence=True,task="harvest",num_fruits=3)
        # Native convex contact fixture rests ~3.9 mm below analytic bound; only floor gets extra tolerance.
        pos=torch.tensor([[.4,0.,cfg.box_min[2]+cfg.length*.48-.004]])
        quat=torch.tensor([[1.,0,0,0]])
        self.assertTrue(settled_in_box(pos,quat,pos*0,cfg).item())
        pos[:,2]-=.003
        self.assertFalse(settled_in_box(pos,quat,pos*0,cfg).item())
        TaskSettings(task="harvest",num_fruits=3,sequence=True,attachment_version=3,background="grove").validate()
        for changes in ({"task":"pull"},{"num_fruits":2},{"reward_version":6}):
            cfg={"task":"harvest","num_fruits":3,"sequence":True};cfg.update(changes)
            with self.assertRaises(ValueError):TaskSettings(**cfg).validate()

    def test_random_colors_and_per_fruit_clock(self):
        from harvest_rl.sequence import sample_color_ids,next_target,target_elapsed
        torch.manual_seed(91)
        colors=sample_color_ids(256,5,"cpu")
        self.assertEqual(tuple(colors.shape),(256,5))
        self.assertTrue(((colors>=0)&(colors<3)).all())
        self.assertTrue((colors!=2).any(-1).all())
        counts=torch.stack([(colors==i).sum(-1) for i in range(3)],dim=-1)
        self.assertGreater(len(torch.unique(counts,dim=0)),5)
        torch.manual_seed(91)
        torch.testing.assert_close(colors,sample_color_ids(256,5,"cpu"))
        p=torch.randn(256,5,3);ripe=colors!=2
        target,_=next_target(p,torch.zeros(256,3),ripe,torch.zeros_like(ripe))
        self.assertTrue(ripe[torch.arange(256),target].all())
        steps=torch.tensor([399,620]);start=torch.tensor([0,610])
        self.assertEqual(target_elapsed(steps,start,True).tolist(),[399,10])
        self.assertEqual(target_elapsed(steps,start,False).tolist(),[399,620])

    def test_native_worker_configuration_is_explicit(self):
        from run import simulator_kit_args
        key="--/plugins/carb.tasking.plugin/threadCount"
        self.assertEqual(simulator_kit_args("",1),key+"=1")
        self.assertEqual(simulator_kit_args("--/log/level=warn",2),"--/log/level=warn "+key+"=2")
        for invalid in (0,-1):
            with self.assertRaises(ValueError):simulator_kit_args("",invalid)
        with self.assertRaises(ValueError):simulator_kit_args(key+"=8",1)

    def test_pull_progress_replaces_hold_reward_and_cannot_be_farmed(self):
        from harvest_rl.logic import pull_stage_shaping
        yes=torch.tensor([True]);no=~yes;zero=torch.zeros(1);grasp=torch.tensor([.2])
        r,b=pull_stage_shaping(grasp,no,yes,yes,zero,zero,.05)
        torch.testing.assert_close(r,grasp)
        r,b=pull_stage_shaping(grasp,yes,yes,yes,zero,zero,.05)
        self.assertLess(r.item(),0)  # confirmed static hold has no payout
        r,b=pull_stage_shaping(grasp,yes,yes,yes,zero+.01,b,.05)
        self.assertAlmostEqual(r.item(),1.99,places=5)
        for retreat in (.005,.01):
            r,b=pull_stage_shaping(grasp,yes,yes,yes,zero+retreat,b,.05)
            self.assertLess(r.item(),0)  # repeated retreat does not pay twice
        r,b=pull_stage_shaping(grasp,yes,yes,yes,zero+.02,b,.05)
        self.assertAlmostEqual(r.item(),1.99,places=5)
        for attached,grip in ((no,yes),(yes,no)):
            r,new=pull_stage_shaping(grasp,yes,attached,grip,zero+.06,b,.05)
            torch.testing.assert_close(new,b)
            self.assertLessEqual(r.item(),0)
        r,b=pull_stage_shaping(grasp,yes,yes,yes,zero-.02,zero,.05)
        self.assertEqual(b.item(),0)
        self.assertLess(r.item(),0)  # forward motion is not rewarded

    def test_centered_contact_rejects_tips_and_resets_dwell(self):
        from harvest_rl.logic import qualified_grasp
        s=TaskSettings();f=torch.tensor([[1.,0,0]]).repeat(5,1);m=-f
        distance=torch.tensor([0.,.009,.010,.011,.04])
        contact=bilateral_contact(f,m,distance,s)
        self.assertTrue(contact.all())  # Old gate admitted these tip contacts.
        valid=qualified_grasp(contact,distance,s)
        self.assertEqual(valid.tolist(),[True,True,True,False,False])
        timer=torch.zeros(5)
        for _ in range(5):timer=dwell(timer,valid,.05)
        success=stage_success("grasp",timer>=s.grip_hold_s,torch.ones(5,dtype=torch.bool),timer*0,timer*0,timer*0,s)
        self.assertEqual(success.tolist(),[True,True,True,False,False])
        timer=dwell(timer,qualified_grasp(contact,torch.full((5,),.02),s),.05)
        self.assertEqual(timer.sum(),0)
        self.assertFalse(qualified_grasp(torch.zeros_like(contact),distance,s).any())
        self.assertTrue(qualified_grasp(contact,distance,TaskSettings(grasp_version=1,reward_version=2)).all())

    def test_center_reward_rejects_edge_loitering_and_guides_alignment(self):
        from harvest_rl.logic import centered_grasp_shaping
        s=TaskSettings();d=torch.tensor([.005,.03]);q=torch.ones(2);contact=torch.ones(2,dtype=torch.bool)
        reward=centered_grasp_shaping(d,d,q,q,contact,torch.full((2,),.25),.05,s)
        self.assertGreater(reward[0],0);self.assertLess(reward[1],0)
        no_contact=torch.zeros_like(contact)
        progress=centered_grasp_shaping(d+.005,d,q,q,no_contact,d*0,.05,s)
        self.assertTrue((progress>0).all())
        stationary=centered_grasp_shaping(d,d,q,q,no_contact,d*0,.05,s)
        torch.testing.assert_close(stationary,torch.zeros_like(d))
        for tolerance in (0.,-.01,.04,float("nan")):
            with self.assertRaises(ValueError):TaskSettings(grasp_center_tolerance=tolerance).validate()

    def test_grasp_diagnostic_evidence(self):
        from harvest_rl.logic import grasp_diagnostics
        d=torch.zeros(4); f=torch.tensor([[0.,0,0],[0.,0,0],[1.,0,0],[1.,0,0]])
        m=torch.tensor([[0.,0,0],[0.,0,0],[0.,0,0],[1.,0,0]])
        result=grasp_diagnostics(d,torch.tensor([0.,-1.,-1.,-1.]),
            torch.tensor([0.,0.,-.2,-.2]),f,m,torch.zeros(4,dtype=torch.bool),TaskSettings())
        self.assertEqual(result["near_no_close_command"].tolist(),[True,False,False,False])
        self.assertEqual(result["near_close_no_motion"].tolist(),[False,True,False,False])
        self.assertEqual(result["near_one_contact"].tolist(),[False,False,True,False])
        self.assertEqual(result["near_two_contacts_not_opposed"].tolist(),[False,False,False,True])

    def test_no_stationary_or_distant_closing_reward(self):
        from harvest_rl.logic import grasp_shaping
        d=torch.tensor([0.,.1]);q=torch.ones(2);grip=torch.zeros(2,dtype=torch.bool)
        local=torch.tensor([[0.,0,0],[.1,0,0]])
        stationary=grasp_shaping(d,d,local,q,q,grip,d*0,.05)
        torch.testing.assert_close(stationary,torch.zeros(2))
        closed=grasp_shaping(d,d,local,q,q-.03,grip,d*0,.05)
        self.assertGreater(closed[0],0);self.assertEqual(closed[1],0)
        opened=grasp_shaping(d,d,local,q-.03,q,grip,d*0,.05)
        torch.testing.assert_close(closed+opened,torch.zeros(2))
        self.assertFalse(stage_success("grasp",grip,~grip,d*0,d*0,d*0,TaskSettings()).any())

    def test_checkpoint_reward_and_eval_reset_contract(self):
        import hashlib, json, tempfile
        from types import SimpleNamespace
        from unittest.mock import patch
        import run
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);urdf=root/"robot.urdf";urdf.write_text("fixture")
            prep={"sha256":hashlib.sha256(urdf.read_bytes()).hexdigest(),"workspace_sha256":"same"}
            (root/"preparation.json").write_text(json.dumps(prep))
            ckpt=root/"teacher.pt";ckpt.touch()
            task=TaskSettings(pregrasp_fraction=.75).as_dict()
            (root/"run.json").write_text(json.dumps({"task":task,"asset":prep}))
            args=SimpleNamespace(resume=None,checkpoint=ckpt,warm_start=None,seed=42,split=None,mode="play",
                task=None,num_fruits=None,diameter=None,curriculum=None,mass=None,grip_friction=None,
                attachment_version=None,valid_pull_distance=None,spring_k=None,spring_d=None,break_hold_s=None,
                dynamic_friction=None,break_force=None,hold_force=None,pregrasp_fraction=None,reward_version=None,grasp_version=None,grasp_center_tolerance=None)
            with patch.object(run,"CACHE",root),patch.object(run,"URDF",urdf):
                evaluated=run.load_settings(args)
                self.assertEqual(evaluated.pregrasp_fraction,0)
                self.assertEqual(evaluated.workspace_split,"eval")
                urdf.write_text("edited source")
                with self.assertRaises(ValueError):run.load_settings(args)
                args.use_prepared_assets=True
                with patch.object(run,"validate_prepared_bank"):
                    self.assertEqual(run.load_settings(args).task,"grasp")
                    args.eval_break_force=10.
                    self.assertEqual(run.load_settings(args).break_force,10.)
                    args.eval_break_force=None
                    args.mode="train";args.warm_start=ckpt;args.checkpoint=None
                    self.assertEqual(run.load_settings(args).task,"grasp")
                    args.warm_start=None;args.checkpoint=ckpt;args.mode="play"
                    args.mode="train"
                    with self.assertRaises(ValueError):run.load_settings(args)
                    args.checkpoint=None
                    self.assertEqual(run.load_settings(args).task,"grasp")  # explicit fresh cached training
                    args.checkpoint=ckpt;args.mode="play"
                    prep["sha256"]="different cache"
                    (root/"preparation.json").write_text(json.dumps(prep))
                    with self.assertRaises(ValueError):run.load_settings(args)
                prep["sha256"]=hashlib.sha256(b"fixture").hexdigest()
                (root/"preparation.json").write_text(json.dumps(prep))
                urdf.write_text("fixture");args.use_prepared_assets=False
                task.pop("random_colors");task.pop("timeout_scope");task.pop("attachment_version");task.pop("reward_version");task.pop("pregrasp_fraction");task.pop("grasp_version");task.pop("grasp_center_tolerance")
                (root/"run.json").write_text(json.dumps({"task":task,"asset":prep}))
                self.assertEqual(run.load_settings(args).attachment_version,1)
                self.assertFalse(run.load_settings(args).random_colors)
                self.assertEqual(run.load_settings(args).timeout_scope,"episode")
                self.assertEqual(run.load_settings(args).reward_version,1)
                self.assertEqual(run.load_settings(args).grasp_version,1)
                args.mode="train";args.checkpoint=None;args.resume=ckpt;args.reward_version=2
                with self.assertRaises(ValueError):run.load_settings(args)
                args.resume=None;args.warm_start=ckpt
                self.assertEqual(run.load_settings(args).reward_version,2)
                args.reward_version=4;args.grasp_version=2
                self.assertEqual(run.load_settings(args).grasp_version,2)
                args.warm_start=None;args.resume=ckpt
                with self.assertRaises(ValueError):run.load_settings(args)

    def test_pregrasp_cannot_leak_into_evaluation(self):
        with self.assertRaises(ValueError):
            TaskSettings(pregrasp_fraction=.5,workspace_split="eval").validate()
        with self.assertRaises(ValueError):
            TaskSettings(pregrasp_fraction=.5,num_fruits=2).validate()

    def test_smooth_pull_ik_preserves_pose_and_limits(self):
        from harvest_rl.reference import pull_waypoint, solve_pull_ik
        kin=ArmKinematics(); q=np.array([0.,-.97,.68,.29,-1.522,.78])
        pose=kin.grasp_fk(q)
        np.testing.assert_allclose(pull_waypoint(pose,0),pose[:3,3])
        np.testing.assert_allclose(pull_waypoint(pose,1),pose[:3,3]+[-.06,0,0])
        solution,error=solve_pull_ik(kin,q,pose,pull_waypoint(pose,.3))
        self.assertLess(error,.01)
        self.assertTrue(np.all(solution>kin.lower[:5]) and np.all(solution<kin.upper[:5]))

    def test_compliant_squeeze_release_latches_open(self):
        measured=torch.tensor([.8,.8]); target=torch.tensor([.9,.9])
        active=torch.tensor([True,True])
        out,active=compliant_gripper_hold(target,measured,torch.tensor([0.,1.]),active,.035,0.,1.5)
        torch.testing.assert_close(out,torch.tensor([.765,.9]))
        self.assertEqual(active.tolist(),[True,False])
        out,active=compliant_gripper_hold(target,measured,torch.zeros(2),active,.035,0.,1.5)
        self.assertAlmostEqual(out[1].item(),.9,places=5)

    def test_close_anti_windup_and_open(self):
        q=torch.ones(2,6)*.7
        target=q.clone(); target[0,-1]=-1
        a=torch.zeros_like(q); a[0,-1]=-1; a[1,-1]=1
        out=limited_joint_targets(target,q,a,torch.ones(6),.05,torch.zeros(6),torch.ones(6)*2,.04)
        self.assertAlmostEqual(out[0,-1].item(),.66,places=5)
        self.assertAlmostEqual(out[1,-1].item(),.75,places=5)

    def test_four_stage_success_and_dwell_reset(self):
        s=TaskSettings(); yes=torch.tensor([True]); no=~yes; t=torch.tensor([1.1]); z=t*0
        self.assertTrue(stage_success("hold",yes,yes,t,z,z,s).item())
        self.assertFalse(stage_success("hold",yes,no,t,z,z,s).item())
        self.assertTrue(stage_success("pull",yes,no,z,t,z,s).item())
        self.assertFalse(stage_success("pull",yes,yes,z,t,z,s).item())
        self.assertFalse(stage_success("harvest",yes,no,t,t,z,s).item())
        self.assertEqual(dwell(t,no,.05).item(),0)
        for task in ("grasp","hold","pull","harvest"):
            TaskSettings(task=task).validate()

    def test_pull_direction_rejects_push_and_sideways_knock(self):
        displacements=torch.tensor([[-.02,0.,0.],[.02,0.,0.],[0.,0.,-.03],[-.005,0.,0.]])
        self.assertEqual(valid_pull(displacements,TaskSettings(attachment_version=1)).tolist(),[True,False,False,False])

    def test_simulator_failure_returns_nonzero(self):
        import subprocess
        import os
        script="from harvest_rl.lifecycle import close_simulator; close_simulator(None,failed=True)"
        process=subprocess.run([sys.executable,"-c",script],env={**os.environ,
            "PYTHONPATH":str(Path(__file__).resolve().parents[1])},capture_output=True)
        self.assertEqual(process.returncode,1)

    def test_fk_region_and_repeatability(self):
        from harvest_rl.settings import CACHE
        preserved = CACHE / "harvest_training.urdf"
        if not preserved.exists():
            self.skipTest("Preserved front-mounted training URDF required for workspace regression")
        k, s = ArmKinematics(preserved), TaskSettings()
        q, p = k.candidates(s,count=64)
        q2, p2 = k.candidates(s,count=64)
        np.testing.assert_allclose(q,q2)
        np.testing.assert_allclose(p,p2)
        self.assertTrue(np.all(p >= np.array(s.region_origin)+s.region_min))
        self.assertTrue(np.all(p <= np.array(s.region_origin)+s.region_max))
        for qi, pi in zip(q,p):
            np.testing.assert_allclose(k.grasp_fk(qi)[:3,3],pi)
        self.assertTrue(np.all(q>=k.lower) and np.all(q<=k.upper))

    def test_gravity_does_not_detach(self):
        s = TaskSettings()
        zero = torch.zeros(2,3)
        attached = torch.ones(2,dtype=torch.bool)
        timer = torch.zeros(2)
        for _ in range(100):
            force, torque, attached, timer, load = attachment_wrench(
                zero,zero,zero,s,attached,timer,s.physics_dt,torch.full((2,),s.break_force))
        self.assertTrue(attached.all())
        torch.testing.assert_close(force[:,2],torch.full((2,),s.mass*9.81))

    def test_sustained_break_and_no_reattach(self):
        s = TaskSettings()
        d = torch.tensor([[.04,0.,0.],[0.,0.,0.]])
        z = torch.zeros_like(d)
        attached = torch.ones(2,dtype=torch.bool)
        timer = torch.zeros(2)
        for _ in range(12):
            f,t,attached,timer,_ = attachment_wrench(d,z,z,s,attached,timer,s.physics_dt,torch.full((2,),2.5))
        self.assertEqual(attached.tolist(),[False,True])
        self.assertEqual(f[0].abs().sum().item(),0.)
        _,_,attached,_,_=attachment_wrench(z,z,z,s,attached,timer,s.physics_dt,torch.full((2,),2.5))
        self.assertFalse(attached[0])

    def test_impulse_does_not_break(self):
        s = TaskSettings()
        z = torch.zeros(1,3)
        a = torch.ones(1,dtype=torch.bool)
        t = torch.zeros(1)
        _,_,a,t,_=attachment_wrench(z+.04,z,z,s,a,t,s.physics_dt,torch.tensor([2.5]))
        _,_,a,t,_=attachment_wrench(z,z,z,s,a,t,s.physics_dt,torch.tensor([2.5]))
        self.assertTrue(a.item())
        self.assertEqual(t.item(),0)

    def test_grip_requires_opposed_bilateral_contact(self):
        s=TaskSettings()
        f=torch.tensor([[1.,0,0],[1.,0,0],[0.,0,0]])
        m=torch.tensor([[-1.,0,0],[1.,0,0],[-1.,0,0]])
        self.assertEqual(bilateral_contact(f,m,torch.zeros(3),s).tolist(),[True,False,False])

    def test_place_requires_containment_and_settling(self):
        s=TaskSettings()
        p=torch.tensor([[.4,0,.55],[.49,0,.55],[.4,0,.8],[.4,0,.55]])
        v=torch.zeros(4,3);v[-1,0]=1
        self.assertEqual(contained_in_box(p,v,s).tolist(),[True,False,False,False])

    def test_legacy_box_bottom_margin_keeps_other_bounds(self):
        s=TaskSettings()
        p=torch.tensor([[.4,0,.5335],[.4,0,.527],[.4,0,.50],
                        [.49,0,.5335],[.4,0,.8],[.4,0,.5335]])
        v=torch.zeros_like(p);v[-1,0]=1.
        self.assertFalse(contained_in_box(p,v,s).any().item())
        s.legacy_box_bottom_margin=.010
        self.assertEqual(contained_in_box(p,v,s).tolist(),[True,False,False,False,False,False])
        s.validate()
        s.legacy_box_bottom_margin=.011
        with self.assertRaises(ValueError):s.validate()

    def test_student_contract_history_reset_and_gradient(self):
        torch.manual_seed(1)
        rgb=torch.zeros(2,96,128,3,dtype=torch.uint8)
        prop=torch.zeros(2,18)
        h=History(rgb,prop)
        h.update(rgb+255,prop+1,torch.tensor([True,False]))
        self.assertTrue((h.rgb[0]==255).all())
        self.assertTrue((h.rgb[1,0]==0).all())
        model=VisionStudent()
        y=model(h.rgb,h.proprio)
        self.assertEqual(tuple(y.shape),(2,6))
        self.assertTrue((y.abs()<=1).all())
        y.square().mean().backward()
        self.assertTrue(all(p.grad is not None for p in model.parameters()))

    def test_invalid_parameters_fail_loudly(self):
        for s in (TaskSettings(num_fruits=0),TaskSettings(task="wrong"),TaskSettings(diameter=.2)):
            with self.assertRaises(ValueError):
                s.validate()


if __name__ == "__main__":
    unittest.main()
