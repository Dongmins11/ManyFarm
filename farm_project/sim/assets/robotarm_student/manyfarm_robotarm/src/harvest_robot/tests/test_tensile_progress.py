import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import torch
from harvest_rl.logic import tensile_progress_reward
class TensileTests(unittest.TestCase):
 def test_contact_axis_load_and_no_farming(self):
  b=torch.tensor([True]);z=torch.zeros(1);best=z.clone()
  def call(x,f,grip=True):
   nonlocal best
   reward,best=tensile_progress_reward(z,b,b,torch.tensor([grip]),torch.tensor([x]),torch.tensor([f]),torch.tensor([2.5]),best,.05)
   return float(reward[0])
  self.assertLessEqual(call(-.02,3),0)
  self.assertLessEqual(call(.025,0),0)
  self.assertLessEqual(call(.025,3,False),0)
  self.assertAlmostEqual(call(.0125,1.25),2.99,places=5)
  self.assertLessEqual(call(.0125,1.25),0)
  self.assertLessEqual(call(0,0),0)
  self.assertLessEqual(call(.0125,1.25),0)
  self.assertAlmostEqual(call(.03,3),2.99,places=5)
  self.assertLessEqual(call(.05,5),0)


class PullSqueezeTests(unittest.TestCase):
 def test_ramp_is_delayed_bounded_and_needs_contact(self):
  from harvest_rl.logic import pull_squeeze_error,compliant_gripper_hold
  times=torch.tensor([.25,.75,1.75,9.,9.])
  grip=torch.tensor([True,True,True,True,False])
  error=pull_squeeze_error(.035,times,grip,torch.ones(5,dtype=torch.bool))
  torch.testing.assert_close(error,torch.tensor([.035,.035,.045,.055,.035]))
  target,active=compliant_gripper_hold(torch.ones(5),torch.ones(5),torch.ones(5)*.1,grip,error,0,2)
  torch.testing.assert_close(target,torch.ones(5));self.assertFalse(bool(active.any()))


class SqueezeRearmTests(unittest.TestCase):
 def test_rearm_requires_confirmed_contact_and_close_and_respects_open(self):
  from harvest_rl.logic import rearm_confirmed_squeeze
  active=torch.tensor([False,False,False,True,True])
  confirmed=torch.tensor([True,False,True,True,True])
  action=torch.tensor([-.2,-.2,0.,.1,-.2])
  torch.testing.assert_close(rearm_confirmed_squeeze(active,confirmed,action),torch.tensor([True,False,False,False,True]))


class RecoveryPotentialTests(unittest.TestCase):
 def test_discounted_cycle_and_timeout_are_not_profitable(self):
  from harvest_rl.logic import pull_recovery_step
  previous=torch.zeros(1);total=0.;b=torch.tensor([True])
  for i,d in enumerate([.10,.03,.01,.12,.03,.01,.01]):
   reward,previous=pull_recovery_step(previous,torch.tensor([d]),b,b,torch.tensor([i==6]))
   total+=(.99**i)*float(reward)
  self.assertAlmostEqual(total,0.,places=5);self.assertEqual(float(previous),0.)
 def test_reapproach_signal_and_no_reward_before_grasp(self):
  from harvest_rl.logic import pull_recovery_step
  b=torch.tensor([True]);f=~b;z=torch.zeros(1)
  r,p=pull_recovery_step(z,torch.tensor([.01]),f,b,f)
  self.assertEqual(float(r),0.)
  _,p=pull_recovery_step(z,torch.tensor([.10]),b,b,f)
  r,p=pull_recovery_step(p,torch.tensor([.02]),b,b,f)
  self.assertGreater(float(r),0.)
  r,p=pull_recovery_step(p,torch.tensor([.02]),b,b,f)
  self.assertLess(float(r),0.)
