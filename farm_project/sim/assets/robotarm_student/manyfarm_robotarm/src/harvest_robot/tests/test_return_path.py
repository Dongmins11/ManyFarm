import sys
from pathlib import Path
import unittest
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from harvest_runtime.return_path import reverse_path,bounded_target


class ReturnTests(unittest.TestCase):
    def test_reverse_keeps_curve_and_opens_finger(self):
        home=np.zeros(6);home[-1]=1.1
        history=np.array([home, [.1,0,0,0,0,.2],[.1,.1,0,0,0,.2],[0,.1,0,0,0,.9]])
        path=reverse_path(history,home,1.1)
        np.testing.assert_allclose(path[0,:5],history[-1,:5])
        self.assertTrue(np.all(path[:,-1]==1.1))
        np.testing.assert_allclose(path[1,:5],history[-2,:5])
        np.testing.assert_allclose(path[-1],home)

    def test_rate_limit_and_no_overshoot(self):
        q=np.zeros(6);goal=np.array([1,-1,.001,0,0,1.])
        out=bounded_target(q,goal,.5,.05)
        self.assertLessEqual(np.max(abs(out-q)),.025)
        self.assertEqual(out[2],.001)

    def test_reject_nonfinite_and_empty(self):
        with self.assertRaises(ValueError):reverse_path([],np.zeros(6),1.1)
        with self.assertRaises(ValueError):bounded_target(np.zeros(6),np.full(6,np.nan),.5,.05)


if __name__=='__main__':unittest.main()

class ReturnGuardTests(unittest.TestCase):
    def make(self):
        import torch
        from types import SimpleNamespace
        from harvest_runtime.isaac_return import IsaacReturn
        from harvest_rl.settings import TaskSettings
        sensor=lambda:SimpleNamespace(data=SimpleNamespace(net_forces_w=torch.zeros(1,1,3)))
        e=SimpleNamespace(settings=TaskSettings(reward_version=6,legacy_box_bottom_margin=.01),
            robot=SimpleNamespace(data=SimpleNamespace(joint_pos=torch.zeros(1,6))),
            arm_contact=sensor(),fixed_contact=sensor(),moving_contact=sensor(),
            attached=torch.tensor([[False,True]]),collected=torch.tensor([[True,False]]),
            scene=SimpleNamespace(env_origins=torch.zeros(1,3)),
            fruits=[SimpleNamespace(data=SimpleNamespace(root_link_quat_w=torch.tensor([[1.,0,0,0]]),root_link_pos_w=torch.tensor([[.4,0,.535]]))),
                    SimpleNamespace(data=SimpleNamespace(root_link_quat_w=torch.tensor([[1.,0,0,0]]),root_link_pos_w=torch.tensor([[.5,-.2,.9]])))])
        return IsaacReturn(e,path_mode='retrace'),e

    def test_deposit_and_attached_neighbor_allowed(self):
        motion,e=self.make();self.assertEqual(motion._guard(),'')

    def test_return_contact_stops(self):
        motion,e=self.make();e.arm_contact.data.net_forces_w[0,0,0]=3.
        self.assertIn('return_contact',motion._guard())

    def test_neighbor_detachment_stops(self):
        motion,e=self.make();e.attached[0,1]=False
        self.assertEqual(motion._guard(),'uncollected_fruit_detached')

    def test_previous_deposit_escape_stops(self):
        motion,e=self.make();e.fruits[0].data.root_link_pos_w[0,0]=.6
        self.assertEqual(motion._guard(),'collected_fruit_0_outside_box')

    def test_nonfinite_state_stops(self):
        motion,e=self.make();e.robot.data.joint_pos[0,0]=float('nan')
        self.assertEqual(motion._guard(),'nonfinite_joint')

    def test_physical_return_compensates_static_drive_error(self):
        import torch
        from harvest_runtime import Request
        motion,e=self.make()
        e.jids=list(range(6));e.step_dt=.05
        e.home=torch.tensor([0.,0.,0.,0.,0.,1.1])
        e.lower=torch.full((6,),-3.);e.upper=torch.full((6,),3.)
        current=e.home.clone();current[0]=.2
        e.robot.data.joint_pos=current[None].clone()
        e.robot.data.joint_vel=torch.zeros(1,6)
        e.targets=current[None].clone()
        e.robot.set_joint_position_target=lambda *a,**k:None
        motion.history=[e.home.numpy().copy(),current.numpy().copy()]
        def plant(command):
            old=e.robot.data.joint_pos.clone()
            equilibrium=torch.tensor(command,dtype=torch.float32)[None]
            equilibrium[0,0]+=.04  # Fixed load/drive error requires integral compensation.
            e.robot.data.joint_pos += .5*(equilibrium-e.robot.data.joint_pos)
            e.robot.data.joint_vel=(e.robot.data.joint_pos-old)/e.step_dt
        motion._physical_step=plant
        request=Request('r','red')
        motion.start_return(request,0.)
        for tick in range(1,400):
            result=motion.tick_return(request,tick*e.step_dt)
            if result.status!='RUNNING':break
        self.assertEqual(result.status,'SUCCEEDED',result.reason)
        self.assertLess(float(torch.max(abs(e.robot.data.joint_pos[0]-e.home))),.035)
        self.assertLessEqual(np.max(abs(motion.bias)),.06)

    def test_nonfinite_contact_and_fruit_stop(self):
        motion,e=self.make();e.fixed_contact.data.net_forces_w[0,0,0]=float('nan')
        self.assertEqual(motion._guard(),'nonfinite_contact')
        e.fixed_contact.data.net_forces_w.zero_()
        e.fruits[1].data.root_link_pos_w[0,0]=float('inf')
        self.assertEqual(motion._guard(),'nonfinite_fruit_position')
