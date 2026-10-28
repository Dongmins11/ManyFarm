"""시뮬 인계 승인 경계와 정지 연속성 검사."""
import copy
import json
import sys
import unittest
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'sim/ros_ws/src/farm_sim_devices'))
from farm_sim_devices.basket_alignment import BasketAlignment

class BasketHandoffTests(unittest.TestCase):
    def setUp(self):
        self.spec=json.loads((ROOT/'sim/ros_ws/src/farm_sim_config/config/docking/basket_alignment_evaluation.json').read_text())
        for role,z in [('harvest',.1),('transport',0.)]:
            self.spec[role].update(center_local_m=[0.,0.,z],opening_size_m=[1.,1.])
        self.h=dict(wheel_odom=[0.]*5,T_world_evaluation_frames={'harvest_lid_fixed':np.eye(4).tolist()})
        m=np.eye(4);m[0,3]=.28
        self.t=dict(wheel_odom=[0.]*5,T_world_evaluation_frames={'cargo_box':m.tolist()})
        self.e=BasketAlignment(self.spec)
    def held(self):
        for i in range(61):r=self.e.sample(i/60.,self.h,self.t)
        return r
    def test_72_percent_passes_after_hold(self):
        r=self.held();self.assertAlmostEqual(r['coverage'],.72);self.assertTrue(r['hold_pass']);self.assertFalse(r['full_containment'])
    def test_719_percent_within_approved_distance_tolerance_passes(self):
        self.t['T_world_evaluation_frames']['cargo_box'][0][3]=.281
        self.assertTrue(self.held()['hold_pass'])
    def test_694_percent_passes_but_693_percent_does_not(self):
        self.t['T_world_evaluation_frames']['cargo_box'][0][3]=.306
        self.assertTrue(self.held()['hold_pass'])
        self.t['T_world_evaluation_frames']['cargo_box'][0][3]=.307
        self.assertFalse(self.held()['hold_pass'])
    def test_gap_or_wheel_motion_resets_hold(self):
        self.assertTrue(self.held()['hold_pass'])
        self.assertFalse(self.e.sample(2.,self.h,self.t)['hold_pass'])
        self.t['wheel_odom'][3]=.006
        self.assertFalse(self.e.sample(2.02,self.h,self.t)['hold_pass'])
    def test_actual_world_motion_resets_hold(self):
        self.assertTrue(self.held()['hold_pass'])
        self.t['T_world_evaluation_frames']['cargo_box'][1][3]+=.001
        self.assertFalse(self.e.sample(1.02,self.h,self.t)['hold_pass'])
    def test_nonpositive_height_rejected(self):
        self.spec['harvest']['center_local_m'][2]=0.
        self.assertFalse(self.held()['hold_pass'])

if __name__=='__main__':unittest.main()
