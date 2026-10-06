"""Offline regression tests: no ROS, GPU, simulator or truth-fed perception."""
from pathlib import Path
import importlib.util
import json
import math
import sys
import unittest
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
for package in ('scout_robot','farm_vision','farm_common'):
    sys.path.insert(0,str(ROOT/'robot/ros_ws/src'/package))
from scout_robot.survey_core import StraightBed,Survey,transform_points,matrix_from_pose
from scout_robot.route import load_route
from scout_robot.survey_policy import SurveyPolicy
from farm_vision.survey_worker import surface_sample
from farm_vision.preprocess import prepare

spec=importlib.util.spec_from_file_location('truth_compare',ROOT/'sim/tools/compare_scout_truth.py')
truth_compare=importlib.util.module_from_spec(spec);spec.loader.exec_module(truth_compare)

class SurveyTest(unittest.TestCase):
    def setUp(self):
        self.cfg=json.loads((ROOT/'sim/ros_ws/src/farm_sim_config/config/scout_survey.json').read_text())
        self.c=self.cfg['sections']['BED_01'];self.route=load_route(ROOT/self.c['route_file'],self.c['node_ids'])
        self.bed=StraightBed(self.route,self.c)
        self.pre=json.loads((ROOT/self.cfg['vision_config']).read_text())['preprocess']
        f=640*1.88/3.5;self.K=np.array([[f,0,320],[0,f,192],[0,0,1]])
        self.C=np.array([[1,0,0,0],[0,0,1,0],[0,-1,0,.6],[0,0,0,1]],float)
    def detection(self,s,n=1.14,z=.8):
        return dict(position_map_m=self.bed.world(s,n,z),class_name='Red',confidence=.9,stamp_ns=100)
    def test_policy_position_and_new_fruit(self):
        for policy in SurveyPolicy:
            with self.subTest(policy=policy):
                survey=Survey(self.bed,'policy',.065,policy=policy)
                first=survey.ingest([self.detection(1)])
                window=survey.windows()[0]['window_id']
                ids=survey.ingest([self.detection(1.04),self.detection(1.12)])
                self.assertEqual(first[0],ids[0])
                self.assertNotEqual(ids[0],ids[1])
                expected=1.02 if policy is SurveyPolicy.MEDIAN_REVALIDATE else 1.0
                self.assertAlmostEqual(self.bed.local(survey.fruits[0]['position_map_m'])[0],expected)
                self.assertEqual(survey.windows()[0]['window_id'],window)
                self.assertEqual(survey.windows()[0]['expected_count'],2)
                self.assertEqual(len(survey.fruits[0]['position_samples']),2)
                self.assertEqual(survey.record()['survey_policy'],policy.value)

    def test_viewpoint_coverage(self):
        d=self.bed.viewpoints(self.K,self.C,640,384,self.pre,.15)
        stops=d['stops_s_m'];lo,hi=d['relative_coverage_m']
        self.assertAlmostEqual(stops[0]+lo,0);self.assertAlmostEqual(stops[-1]+hi,self.bed.length)
        self.assertTrue(all(0<=s<=self.bed.length for s in stops))
        self.assertTrue(all(b-a<=d['usable_width_m']*.85+1e-6 for a,b in zip(stops,stops[1:])))
        print('Designed observation distances:',stops)
    def test_identity_and_permanent_windows(self):
        s=Survey(self.bed,'test',.065)
        ids=s.ingest([self.detection(1),self.detection(1.12),self.detection(1.5)])
        initial=s.windows();self.assertEqual(len(initial),2)
        again=s.ingest([self.detection(1.125),self.detection(1.005),self.detection(1.24)])
        self.assertEqual(again[0],ids[1]);self.assertEqual(again[1],ids[0])
        self.assertEqual(len(s.fruits),4);self.assertEqual(len(s.windows()),2)
        self.assertEqual(s.windows()[0]['goal_pose'],initial[0]['goal_pose'])
        self.assertEqual(s.windows()[0]['expected_count'],3)
        members=[m for w in s.windows() for m in w['member_ids']]
        self.assertEqual(len(members),len(set(members)))
    def test_one_to_one_and_holds(self):
        s=Survey(self.bed,'test',.065);s.ingest([self.detection(1)])
        ids=s.ingest([self.detection(1.01),self.detection(1.02)])
        self.assertNotEqual(*ids)
        s.ingest([self.detection(2,z=1.2),self.detection(3,n=1.3)])
        reasons={x.reason for x in s.plan.holds}
        self.assertEqual(reasons,{'height_out_of_range','depth_out_of_range'})
    def test_harvest_goal_offsets(self):
        s=Survey(self.bed,'t',.065);s.ingest([self.detection(1)])
        w=s.windows()[0];yaw=w['goal_pose']['yaw'];R=np.array([[math.cos(yaw),-math.sin(yaw)],[math.sin(yaw),math.cos(yaw)]])
        offset=np.array(self.c['harvest']['mount_xy_base_m'])+np.array(self.c['harvest']['work_offset_xy_base_m'])
        center=np.array(w['goal_pose']['position'][:2])+R@offset
        expected=np.mean(np.array(w['corners_map_m'])[:,:2],axis=0)
        np.testing.assert_allclose(center,expected,atol=1e-8)
    def test_surface_and_invalid_depth(self):
        mask=np.zeros((384,640),bool);mask[170:210,300:340]=True
        depth=np.full((384,640),np.nan);depth[mask]=1.14
        p=surface_sample(mask,depth,self.K)
        self.assertIsNotNone(p);self.assertAlmostEqual(p['position_camera_m'][2],1.14)
        depth[:]=np.nan;self.assertIsNone(surface_sample(mask,depth,self.K))
    def test_margin_mask_and_transform(self):
        m={'K':self.K.tolist(),'T_odom_camera_optical':self.C.tolist()}
        _,v,t,g=prepare(np.full((384,640,3),200,np.uint8),m,self.pre)
        old=np.array(g['observation_polygon_original_px']);new=np.array(g['polygon_original_px'])
        self.assertLess(new[:,1].min(),old[:,1].min());self.assertGreater(new[:,1].max(),old[:,1].max())
        p=np.array([[320,70],[320,180]],float);np.testing.assert_allclose(t.to_original(t.to_network(p)),p)
    def test_rotated_map(self):
        T=matrix_from_pose([3,4,0],[0,0,math.sin(math.pi/4),math.cos(math.pi/4)])
        np.testing.assert_allclose(transform_points(T,[[1,0,.8]]),[[3,5,.8]],atol=1e-8)
    def test_maximum_matching(self):
        self.assertEqual(len(truth_compare.maximum_matching([[(.01,0),(.02,1)],[(.01,0)]])),2)
    def test_truth_comparison(self):
        s=Survey(self.bed,'t',.065);s.ingest([self.detection(1),self.detection(1.12)])
        fruits=[]
        for i,f in enumerate(s.fruits):
            p=np.array(f['position_map_m'])
            fruits.append(dict(gt_id=str(i),bed_prim=self.c['evaluation_bed_prim'],class_name='Red',
                center_world_m=p.tolist(),aabb_world_m=[(p-.03).tolist(),(p+.03).tolist()]))
        r={'config':self.cfg,'status':'SUCCESS','sections':{'BED_01':{'status':'COMPLETE','survey':s.record()}}}
        out=truth_compare.compare(r,{'fruits':fruits},ROOT,.03)['sections']['BED_01']
        self.assertEqual(out['matched_count'],2);self.assertEqual(out['placed_target_recall'],1)
        self.assertEqual(out['task_count'],1)
if __name__=='__main__':unittest.main()
