"""Stable off-centre connector tests; not a material calibration."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import torch
from harvest_rl.logic import attachment_wrench
from harvest_rl.settings import TaskSettings

class StemResponseTests(unittest.TestCase):
    def test_offcentre_release_dissipates_energy(self):
        cfg=TaskSettings(attachment_version=4,stem_response_version=2)
        dt=cfg.physics_dt
        lever=torch.tensor([[.02,0.,.06]],dtype=torch.float64)
        inv=torch.diag(torch.tensor([100000.,100000.,80000.],dtype=torch.float64))[None]
        r=lever[0];skew=torch.tensor([[0.,-r[2],r[1]],[r[2],0.,-r[0]],[-r[1],r[0],0.]],dtype=torch.float64)
        mobility=torch.eye(3,dtype=torch.float64)/cfg.mass-skew@inv[0]@skew
        effective_mass=torch.linalg.inv(mobility)
        stiffness=torch.diag(torch.tensor([120.,30.,80.],dtype=torch.float64))
        x=torch.tensor([[0.,0.,-.03]],dtype=torch.float64);v=torch.zeros_like(x)
        attached=torch.ones(1,dtype=torch.bool);timer=torch.zeros(1,dtype=torch.float64)
        energy=lambda: float(.5*(v[0]@effective_mass@v[0]+x[0]@stiffness@x[0]))
        initial=previous=energy()
        for _ in range(240):
            f,_,attached,timer,_=attachment_wrench(x,v,lever,cfg,attached,timer,dt,torch.tensor([2.5]),inv)
            v += dt*(mobility@f[...,None]).squeeze(-1)
            x += dt*v
            now=energy()
            self.assertLessEqual(now,previous+1e-10)
            previous=now
        self.assertTrue(attached.item())
        self.assertLess(energy(),initial*.01)

    def test_no_antigravity_and_no_infinite_tether(self):
        cfg=TaskSettings(attachment_version=4,stem_response_version=2)
        zero=torch.zeros(1,3)
        f,_,attached,_,_=attachment_wrench(zero,zero,zero,cfg,torch.tensor([True]),torch.zeros(1),cfg.physics_dt,torch.tensor([2.5]))
        self.assertEqual(f.abs().sum().item(),0.)
        f,_,attached,_,_=attachment_wrench(torch.tensor([[0.,0.,-.081]]),zero,zero,cfg,torch.tensor([True]),torch.zeros(1),cfg.physics_dt,torch.tensor([2.5]))
        self.assertFalse(attached.item())
        self.assertEqual(f.abs().sum().item(),0.)

    def test_sustained_pull_still_breaks(self):
        cfg=TaskSettings(attachment_version=4,stem_response_version=2)
        attached=torch.tensor([True]);timer=torch.zeros(1);zero=torch.zeros(1,3)
        for _ in range(40):
            _,_,attached,timer,_=attachment_wrench(torch.tensor([[-.04,0.,0.]]),zero,zero,cfg,attached,timer,cfg.physics_dt,torch.tensor([2.5]))
        self.assertFalse(attached.item())

    def test_real_inertia_required_off_com(self):
        cfg=TaskSettings(attachment_version=4,stem_response_version=2)
        with self.assertRaises(ValueError):
            attachment_wrench(torch.zeros(1,3),torch.zeros(1,3),torch.ones(1,3)*.02,cfg,torch.tensor([True]),torch.zeros(1),cfg.physics_dt,torch.tensor([2.5]))


class SustainedOverloadTests(unittest.TestCase):
    def response(self, x, steps, version=3):
        cfg=TaskSettings(attachment_version=4,stem_response_version=version)
        attached=torch.tensor([True]);timer=torch.zeros(1);zero=torch.zeros(1,3)
        for _ in range(steps):
            force,torque,attached,timer,load=attachment_wrench(torch.tensor([x]),zero,zero,cfg,attached,timer,cfg.physics_dt,torch.tensor([2.5]))
        return attached,force,torque

    def test_brief_overtravel_not_instant_fracture(self):
        self.assertTrue(self.response([.081,0.,0.],1)[0].item())
        self.assertFalse(self.response([.081,0.,0.],1,version=2)[0].item())

    def test_sustained_large_compression_can_still_break(self):
        attached,force,torque=self.response([.081,0.,0.],29)
        self.assertFalse(attached.item())
        self.assertEqual(force.abs().sum().item(),0.)
        self.assertEqual(torque.abs().sum().item(),0.)

    def test_distance_without_sufficient_load_does_not_break(self):
        self.assertTrue(self.response([0.,.081,0.],60)[0].item())
