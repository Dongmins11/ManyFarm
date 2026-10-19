import sys
import unittest
from pathlib import Path
import torch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from harvest_rl.settings import TaskSettings
from harvest_rl.behavior_contract import apply_gentle_hook
from harvest_rl.logic import attachment_wrench

class GentleHookTests(unittest.TestCase):
    def test_short_pulse_and_sustained_opening(self):
        s=TaskSettings();apply_gentle_hook(s);s.validate()
        a=torch.tensor([True]);t=torch.zeros(1);zero=torch.zeros(1,3)
        for i in range(6):
            _,_,a,t,_=attachment_wrench(torch.tensor([[-.04,0,0]]),zero,zero,s,a,t,s.physics_dt,torch.tensor([2.5]))
        self.assertTrue(a.item())
        _,_,a,t,_=attachment_wrench(zero,zero,zero,s,a,t,s.physics_dt,torch.tensor([2.5]))
        self.assertEqual(t.item(),0)
        for i in range(30):
            f,torque,a,t,_=attachment_wrench(torch.tensor([[-.04,0,0]]),zero,zero,s,a,t,s.physics_dt,torch.tensor([2.5]))
        self.assertFalse(a.item());self.assertEqual(f.abs().sum().item(),0)
        self.assertEqual(torque.abs().sum().item(),0)

    def test_pressed_point_has_no_energy_gain(self):
        for mass in (.035,.1):
            s=TaskSettings(mass=mass);apply_gentle_hook(s)
            x=torch.tensor([[0.,0.,-.03]],dtype=torch.float64);v=torch.zeros_like(x)
            zero=torch.zeros_like(x);a=torch.tensor([True]);t=torch.zeros(1)
            k=torch.tensor([120.,30.,80.],dtype=torch.float64)
            energy=lambda:float((mass*v.square()+k*x.square()).sum()/2)
            initial=previous=energy()
            for _ in range(480):
                f,_,a,t,_=attachment_wrench(x,v,zero,s,a,t,s.physics_dt,torch.tensor([2.5]))
                v+=s.physics_dt*f/mass;x+=s.physics_dt*v
                self.assertLessEqual(energy(),previous+1e-10);previous=energy()
            self.assertTrue(a.item());self.assertLess(energy(),initial*.001)
