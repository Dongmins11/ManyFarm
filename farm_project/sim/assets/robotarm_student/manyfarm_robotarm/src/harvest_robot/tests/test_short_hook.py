import unittest
import torch
from harvest_rl.settings import TaskSettings
from harvest_rl.behavior_contract import apply_short_hook,apply_gentle_hook
from harvest_rl.logic import attachment_wrench

class ShortHookTest(unittest.TestCase):
    def run_load(self,x,steps):
        s=TaskSettings();apply_short_hook(s);s.validate()
        a=torch.tensor([True]);t=torch.zeros(1);zero=torch.zeros(1,3)
        for _ in range(steps):
            f,_,a,t,_=attachment_wrench(torch.tensor([x]),zero,zero,s,a,t,s.physics_dt,torch.tensor([2.5]))
            self.assertLessEqual(float(f.norm()),2.50001)
        return bool(a),f
    def test_tap_retained(self):self.assertTrue(self.run_load([-.03,0.,0.],6)[0])
    def test_opening_releases(self):self.assertFalse(self.run_load([-.03,0.,0.],12)[0])
    def test_large_lateral_releases(self):
        attached,force=self.run_load([0.,.05,0.],12)
        self.assertFalse(attached);self.assertEqual(float(force.norm()),0.)
    def test_small_deflection_retained(self):self.assertTrue(self.run_load([0.,.01,0.],100)[0])
    def test_old_preset_preserved(self):
        s=TaskSettings();apply_gentle_hook(s)
        self.assertEqual((s.stem_response_version,s.spring_k,s.stem_max_extension),(4,120.,.08))
