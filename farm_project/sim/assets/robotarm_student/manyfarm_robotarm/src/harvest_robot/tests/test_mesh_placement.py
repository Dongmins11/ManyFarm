import unittest
from types import SimpleNamespace
import torch
from harvest_rl.logic import mesh_settled_in_box
class MeshPlacement(unittest.TestCase):
    def test_edges_speed_and_rotation(self):
        cfg=SimpleNamespace(box_min=(-1.,-1.,0.),box_max=(1.,1.,2.),box_contact_tolerance=.003,box_bottom_contact_tolerance=.01,sequence=False)
        v=torch.tensor([[-.4,-.1,-.1],[.4,.1,.1]])
        q=torch.tensor([[1.,0.,0.,0.]])
        def check(pos,vel=(0.,0.,0.),quat=q):
            return mesh_settled_in_box(torch.tensor([pos]),quat,torch.tensor([vel]),v,cfg).item()
        self.assertTrue(check((.6,0.,.1)))
        self.assertFalse(check((.61,0.,.1)))
        self.assertFalse(check((0.,0.,.1),(.2,0.,0.)))
        self.assertFalse(check((0.,0.,-.1)))
        self.assertTrue(check((.8,0.,.1),quat=torch.tensor([[2**-.5,0.,0.,2**-.5]])))

class DepositGuardMesh(unittest.TestCase):
    def test_retention_uses_actual_hull_and_rejects_escape(self):
        from harvest_runtime.deposit_guard import still_in_box
        cfg=SimpleNamespace(attachment_version=4,stem_response_version=5,box_min=(-1.,-1.,0.),box_max=(1.,1.,2.),box_contact_tolerance=.003,box_bottom_contact_tolerance=.01,sequence=False)
        fruit=SimpleNamespace(data=SimpleNamespace(root_link_pos_w=torch.tensor([[.8,0.,.2]]),root_link_quat_w=torch.tensor([[1.,0.,0.,0.]])))
        env=SimpleNamespace(settings=cfg,fruits=[fruit],fruit_collision_hulls=[torch.tensor([[-.1,-.1,-.1],[.1,.1,.1]])],scene=SimpleNamespace(env_origins=torch.zeros(1,3)))
        self.assertTrue(still_in_box(fruit,env))
        fruit.data.root_link_pos_w[0,0]=1.2
        self.assertFalse(still_in_box(fruit,env))
