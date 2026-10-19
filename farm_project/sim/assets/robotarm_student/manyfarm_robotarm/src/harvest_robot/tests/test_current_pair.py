import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import numpy as np
import torch
from harvest_rl.current_pair_geometry import separated_pairs,select_layout,selected_teacher_observation,current_to_policy_frame
from harvest_rl.settings import TaskSettings

class CurrentPairTests(unittest.TestCase):
    def test_matched_distractor_does_not_move_target(self):
        from harvest_rl.current_pair_geometry import add_matched_distractor
        candidates=np.array([[0.,0,0],[.2,0,0],[0,.3,0]])
        for slot in (0,1):
            positions=np.zeros((2,3))
            result=add_matched_distractor(positions,slot,candidates,.18,42,7)
            np.testing.assert_array_equal(result[slot],positions[slot])
            self.assertGreaterEqual(np.linalg.norm(result[0]-result[1]),.18)
            np.testing.assert_array_equal(result,add_matched_distractor(positions,slot,candidates,.18,42,7))
        with self.assertRaises(ValueError):add_matched_distractor(positions,0,candidates,1.,42,7)

    def test_spacing_and_matched_target(self):
        points=np.array([[.5,0,.8],[.5,.2,.8],[.5,.01,.8]])
        pairs=separated_pairs(points,.18)
        self.assertEqual(len(pairs),2)
        for i in range(10):
            layout,slot=select_layout(points,pairs,42,i,'yellow')
            self.assertEqual(slot,1)
            self.assertGreaterEqual(np.linalg.norm(layout[0]-layout[1]),.18)
            again,_=select_layout(points,pairs,42,i,'yellow')
            np.testing.assert_array_equal(layout,again)
        with self.assertRaises(ValueError):separated_pairs(points,1.)

    def test_teacher_keeps_selected_slot_and_frozen_padding(self):
        obs=torch.randn(4,82)
        output=selected_teacher_observation(obs)
        torch.testing.assert_close(output[:,:44],obs[:,:44])
        torch.testing.assert_close(output[:,44:47],obs[:,25:28])
        self.assertEqual(output[:,47:68].count_nonzero().item(),0)
        self.assertTrue(bool((output[:,68]==1).all()))
        self.assertEqual(output[:,69:76].count_nonzero().item(),0)
        torch.testing.assert_close(output[:,76:],obs[:,76:])
        self.assertFalse(torch.equal(obs,output))

    def test_two_external_harvest_only(self):
        TaskSettings(task='harvest',num_fruits=2,target_mode='external',sequence=False,reward_version=6).validate()
        with self.assertRaises(ValueError):TaskSettings(task='grasp',num_fruits=2,target_mode='external').validate()

    def test_frame_rejects_nonrigid_changes(self):
        class Kin:
            lower=np.zeros(6);upper=np.ones(6)
            def __init__(self,offset=0,bad=False):self.offset=offset;self.bad=bad
            def fk(self,q,link):
                t=np.eye(4);t[0,3]=self.offset
                if self.bad and link=='harvest_box':t[1,3]=.1
                return t
        frame,errors=current_to_policy_frame(Kin(),Kin(1),[np.zeros(6)])
        self.assertEqual(frame[0,3],-1.)
        with self.assertRaises(ValueError):current_to_policy_frame(Kin(),Kin(1,True),[np.zeros(6)])

    def test_external_second_fruit_state_is_selected(self):
        # Execute the actual small method without importing the Isaac runtime.
        import ast
        from types import SimpleNamespace
        tree=ast.parse((Path(__file__).resolve().parents[1]/'harvest_rl/env.py').read_text())
        cls=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='HarvestEnv')
        method=next(n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name=='_target_fruit')
        module=ast.Module(body=[method],type_ignores=[])
        scope=dict(torch=torch,SimpleNamespace=SimpleNamespace)
        exec(compile(ast.fix_missing_locations(module),'<env target method>','exec'),scope)
        names=('root_link_pos_w','root_link_quat_w','root_com_pos_w','root_com_lin_vel_w','root_com_ang_vel_w')
        fruits=[SimpleNamespace(data=SimpleNamespace(**{n:torch.full((1,3),float(i)) for n in names})) for i in (0,1)]
        fake=SimpleNamespace(settings=SimpleNamespace(num_fruits=2,sequence=False,target_mode='external'),
            fruits=fruits,_t=lambda x:x[:,1])
        got=scope['_target_fruit'](fake)
        for name in names:torch.testing.assert_close(getattr(got.data,name),torch.ones(1,3))
        fake.settings.target_mode='nearest'
        self.assertIs(scope['_target_fruit'](fake),fruits[0])
