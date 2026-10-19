import ast
from pathlib import Path
from types import SimpleNamespace
import sys
import unittest
import torch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from harvest_rl.settings import TaskSettings
from harvest_rl.logic import placement_contained

class PlacementCompatibility(unittest.TestCase):
    def test_edge_and_invalid_deposits(self):
        s=TaskSettings(reward_version=6,shape_placement=True,box_bottom_contact_tolerance=.010)
        p=torch.tensor([[.4624156,-.008,.536886],[.52,0,.537],[.4,0,.48],[.4,0,.80],[.4,0,.537]])
        q=torch.tensor([[1.,0,0,0]]).repeat(5,1)
        v=torch.zeros_like(p);v[-1,0]=.2
        self.assertEqual(placement_contained(p,q,v,s).tolist(),[True,False,False,False,False])
        s.shape_placement=False
        self.assertFalse(bool(placement_contained(p,q,v,s)[0]))

    def method(self,name):
        tree=ast.parse((Path(__file__).resolve().parents[1]/'harvest_rl/env.py').read_text())
        cls=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='HarvestEnv')
        node=next(n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name==name)
        scope={'torch':torch}
        exec(compile(ast.fix_missing_locations(ast.Module(body=[node],type_ignores=[])),'env','exec'),scope)
        return scope[name]

    def test_external_success_never_auto_resets(self):
        e=SimpleNamespace(settings=SimpleNamespace(target_mode='external',sequence=False),
            _update_task=lambda:None,_target_elapsed_steps=lambda:torch.tensor([10]),max_episode_length=400,
            failure=torch.tensor([False]),success=torch.tensor([True]))
        done,timeout=self.method('_get_dones')(e)
        self.assertEqual(e.assignment_status,'SUCCEEDED')
        self.assertFalse(bool(done.any() or timeout.any()))

    def test_assign_second_preserves_scene_and_collected(self):
        e=SimpleNamespace(settings=SimpleNamespace(target_mode='external',num_fruits=2),
            assignment_status='SUCCEEDED',ripe=torch.tensor([[True,True]]),
            collected=torch.tensor([[True,False]]),attached=torch.tensor([[False,True]]),
            target_index=torch.tensor([0]),target_start_step=torch.tensor([0]),episode_length_buf=torch.tensor([80]),
            place_best_distance=torch.tensor([0.]),actions=torch.ones(1,6),previous_actions=torch.ones(1,6),
            _get_observations=lambda:'second')
        before=e.collected.clone(),e.attached.clone()
        self.assertEqual(self.method('assign_target')(e,1),'second')
        self.assertEqual(int(e.target_index[0]),1)
        self.assertEqual(int(e.target_start_step[0]),80)
        torch.testing.assert_close(e.collected,before[0]);torch.testing.assert_close(e.attached,before[1])
