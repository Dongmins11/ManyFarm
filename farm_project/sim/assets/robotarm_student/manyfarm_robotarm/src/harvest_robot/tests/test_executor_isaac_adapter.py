"""CPU binding tests; do not claim PhysX return-path validation."""
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
import torch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from harvest_runtime import Request, Target
from harvest_runtime.adapters import Observation
from harvest_runtime.isaac_teacher import IsaacTeacher


class AdapterTests(unittest.TestCase):
    def make(self):
        env=SimpleNamespace(num_envs=1,settings=SimpleNamespace(target_mode='external',sequence=False,
            task='harvest',num_fruits=2),assignment_status='WAIT_TARGET',
            collected=torch.zeros(1,2,dtype=torch.bool),attached=torch.ones(1,2,dtype=torch.bool),
            ripe=torch.ones(1,2,dtype=torch.bool),scene=SimpleNamespace(env_origins=torch.zeros(1,3)))
        env.fruits=[SimpleNamespace(data=SimpleNamespace(root_link_pos_w=torch.tensor([[.2,float(i),.7]]))) for i in range(2)]
        assigned=[]
        def assign(slot):assigned.append(slot);env.assignment_status='RUNNING';return {'policy':torch.zeros(1,82)}
        env.assign_target=assign
        commands=[]
        def step(action):commands.append(action.clone());return {'policy':torch.ones(1,82)},None,None,None
        resets=[]
        adapter=IsaacTeacher(env,SimpleNamespace(step=step),lambda obs:torch.full((1,6),2.),
            {'red':0,'yellow':1},lambda:resets.append('history'))
        return adapter,env,assigned,commands,resets

    def test_world_and_completed_fruit_preserved_between_targets(self):
        a,e,assigned,commands,resets=self.make()
        before=[f.data.root_link_pos_w.clone() for f in e.fruits]
        a.start_target(Request('one','red'),a.observe_target('red',0))
        e.assignment_status='SUCCEEDED';a.end_target()
        self.assertEqual(e.collected.tolist(),[[True,False]])
        a.start_target(Request('two','yellow'),a.observe_target('yellow',1))
        self.assertEqual(assigned,[0,1]);self.assertEqual(len(resets),3)
        for f,p in zip(e.fruits,before):torch.testing.assert_close(f.data.root_link_pos_w,p)

    def test_policy_action_clips_without_marking_success(self):
        a,e,assigned,commands,resets=self.make();r=Request('one','red')
        a.start_target(r,a.observe_target('red',0));obs=a.read(r,0)
        action=a.act(obs);a.validate(action,obs);a.apply(action,0)
        torch.testing.assert_close(commands[0],torch.ones(1,6))
        self.assertEqual(a.completion(r,0).status,'RUNNING')
        self.assertFalse(bool(e.collected.any()))

    def test_failed_target_never_collected(self):
        a,e,*_=self.make();r=Request('one','red');a.start_target(r,a.observe_target('red',0))
        e.assignment_status='FAILED';a.end_target()
        self.assertFalse(bool(e.collected.any()))

    def test_nan_action_rejected(self):
        a,e,*_=self.make()
        with self.assertRaises(ValueError):a.validate(torch.full((1,6),float('nan')),None)


if __name__=='__main__':unittest.main()
