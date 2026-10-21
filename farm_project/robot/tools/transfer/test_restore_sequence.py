import json
import math
from pathlib import Path
import tempfile
import unittest
from farm_navigation.arc_isolation import CommandGate
from harvest_robot.transfer_retreat import retreat_plan,retreat_error,retreat_profile,alignment_path
from sequence_support import next_stage,verify_predecessor,digest,pose_error,require_wall_start,STAGES

class GeometryTests(unittest.TestCase):
    def test_retreat_all_headings(self):
        for degrees in range(-180,180,5):
            yaw=math.radians(degrees);target=(1.,2.,yaw)
            current=(1.+.1*math.cos(yaw),2.+.1*math.sin(yaw),yaw)
            p=retreat_plan(current,target)
            self.assertAlmostEqual(p.distance,.1)
            self.assertIsNone(p.route.headings)
            self.assertLess(pose_error(p.path[-1],target)['heading_error_rad'],1e-9)
            self.assertLess(retreat_error(p,target)['position_error_m'],1e-9)
    def test_reject_forward(self):
        with self.assertRaises(ValueError):retreat_plan((0.,0.,0.),(.1,0.,0.))
    def test_reject_far_sideways_invalid(self):
        for target in ((-.21,0.,0.),(-.1,.1,0.),(float('nan'),0.,0.)):
            with self.assertRaises(ValueError):retreat_plan((0.,0.,0.),target)
    def test_tracking_bound(self):
        p=retreat_plan((.1,0.,0.),(0.,0.,0.))
        for point in ((.05,.02,0.),(.11,0.,0.),(-.01,0.,0.),(.05,0.,.4)):
            with self.assertRaises(RuntimeError):retreat_error(p,point)
    def test_near_target_skip(self):
        self.assertLessEqual(retreat_plan((.004,0.,0.),(0.,0.,0.)).distance,.005)
    def test_rotation_sweep(self):
        p=alignment_path((1.,2.,3.13),-3.13)
        self.assertGreater(len(p),2)
        self.assertTrue(all(x==1. and y==2. for x,y,_ in p))
        with self.assertRaises(ValueError):alignment_path((0.,0.,0.),.3)
    def test_profile_preserves_unknown_and_collision(self):
        station={'plugin':'farm_nav2_controller::ReverseRegulatedPurePursuitController','custom':17,'use_collision_detection':False}
        p=retreat_profile(station)['Retreat']
        self.assertTrue(p['use_collision_detection']);self.assertFalse(station['use_collision_detection'])
        self.assertEqual(p['custom'],17);self.assertFalse(p['use_rotate_to_heading']);self.assertTrue(p['allow_reversing'])

class GateTests(unittest.TestCase):
    def test_new_modes_bounds(self):
        for direction,good,bad in [('retreat',(-.01,.04),[(.001,0.),(-.011,0.),(-.01,.051)]),('align',(0.,-.03),[(.001,0.),(0.,.031),(0.,float('nan'))])]:
            for value in bad:
                gate=CommandGate(direction=direction);gate.arm(1.)
                self.assertTrue(gate.accept(*good,1.1));self.assertFalse(gate.accept(*value,1.2))
                self.assertFalse(gate.accept(*good,1.3))
    def test_timeout(self):
        gate=CommandGate(direction='retreat');gate.arm(0.);gate.accept(-.01,0.,.1)
        self.assertTrue(gate.expired(.41));self.assertFalse(gate.enabled)

class SequenceTests(unittest.TestCase):
    def test_exact_order(self):
        for i,stage in enumerate(STAGES):self.assertEqual(next_stage({'completed':list(STAGES[:i])}),stage)
        for state in ({'completed':['wall']},{'completed':list(STAGES)},{'failed':'x'},{'executing':'retreat'}):
            with self.assertRaises(ValueError):next_stage(state)
    def test_wall_start(self):
        d={'final_pose':(1.,2.,0.),'odom_session':'s'}
        r={'ok':True,'phase':'PLAN_ONLY','origin':(1.,2.,0.),'odom_session':'s'}
        require_wall_start(r,d)
        for key,value in [('origin',(1.1,2.,0.)),('odom_session','old'),('ok',False)]:
            with self.assertRaises(ValueError):require_wall_start(dict(r,**{key:value}),d)
    def test_proof_mutation_and_pose(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);result=root/'result.json';proof=root/'proof.json'
            r=dict(ok=True,mode='execute',phase='SUCCEEDED',cleanup_stopped=True,ros_cleanup_complete=True,cycle_id='c',odom_session='s',final_pose=(0.,0.,0.))
            result.write_text(json.dumps(r))
            p=dict(stage='wall',cycle_id='c',odom_session='s',departure_sha256='d',result_file=str(result),result_sha256=digest(result))
            proof.write_text(json.dumps(p))
            self.assertEqual(verify_predecessor(proof,'retreat','c','s','d',(0.,0.,0.)),digest(proof))
            for args in [('align','c','s','d',(0.,0.,0.)),('retreat','other','s','d',(0.,0.,0.)),('retreat','c','new','d',(0.,0.,0.)),('retreat','c','s','other',(0.,0.,0.)),('retreat','c','s','d',(.006,0.,0.))]:
                with self.assertRaises(ValueError):verify_predecessor(proof,*args)
            result.write_text(json.dumps(dict(r,ok=False)))
            with self.assertRaises(ValueError):verify_predecessor(proof,'retreat','c','s','d',(0.,0.,0.))

if __name__=='__main__':unittest.main()
