"""20mm boundary and multi-observation position regressions, without ROS/GT."""
from dataclasses import replace
import importlib.util
import json
from pathlib import Path
import sys
import unittest
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'robot/ros_ws/src/scout_robot'))
from scout_robot.b_planner import Config,Fruit,plan_harvest,extend_plan,_fits_task
from scout_robot.survey_core import StraightBed,Survey


class RangeTests(unittest.TestCase):
    def setUp(self):
        self.fixture=json.loads((ROOT/'tests/fixtures/scout_range_56571de5ad6f.json').read_text())
        section=self.fixture['section']
        section['harvest'].update(range_tolerance_m=.02,membership_margin_m=0.)
        self.bed=StraightBed([(1,-6.655,9.5,0),(8,-6.655,2.5,0)],section)

    def detection(self,s=2.,n=1.14,z=.8,stamp=1):
        return dict(position_map_m=self.bed.world(s,n,z),class_name='Red',confidence=.9,stamp_ns=stamp)

    def test_all_six_faces_accept_exact_20mm_reject_over(self):
        config=Config(route_end=7.,range_tolerance=.02,membership_margin=0.)
        task=plan_harvest([Fruit('anchor',1.,0.,.4)],config).tasks[0]
        center=[(task.window_x_min+task.window_x_max)/2,0.,.4]
        bounds=[(task.window_x_min,task.window_x_max),(task.window_y_min,task.window_y_max),
                (task.window_z_min,task.window_z_max)]
        for axis,(lo,hi) in enumerate(bounds):
            for sign,bound in [(-1,lo),(1,hi)]:
                point=center.copy();point[axis]=bound+sign*.02
                self.assertTrue(_fits_task(Fruit('boundary',*point),task,safe=True,tolerance=.02))
                point[axis]+=sign*.00001
                self.assertFalse(_fits_task(Fruit('outside',*point),task,safe=True,tolerance=.02))

    def test_tolerance_is_per_axis_not_euclidean_radius(self):
        task=plan_harvest([Fruit('anchor',1.,0.,.4)],Config(route_end=7.,membership_margin=0.)).tasks[0]
        corner=Fruit('corner',task.window_x_max+.02,task.window_y_max+.02,task.window_z_max+.02)
        self.assertTrue(_fits_task(corner,task,safe=True,tolerance=.02))

    def test_existing_window_uses_tolerance_and_original_geometry(self):
        config=Config(route_end=7.,range_tolerance=.02,membership_margin=0.)
        original=plan_harvest([Fruit('anchor',1.,0.,.4)],config)
        task=original.tasks[0]
        result=extend_plan(original,[Fruit('extra',task.window_x_max+.02,0.,.4)],config,revalidate=True)
        self.assertEqual(result.tasks[0].member_ids,('anchor','extra'))
        self.assertEqual(result.tasks[0].window_x_max,task.window_x_max)
        self.assertEqual(result.tasks[0].base_x,task.base_x)

    def test_both_first_and_later_observation_use_height_depth_tolerance(self):
        survey=Survey(self.bed,'test',.065)
        survey.ingest([self.detection(z=1.073,n=1.21)])
        self.assertEqual(len(survey.windows()),1)
        survey.ingest([self.detection(s=3.,z=1.074,stamp=2)])
        self.assertEqual(len(survey.plan.holds),1)
        self.assertEqual(survey.plan.holds[0].reason,'height_out_of_range')

    def test_coordinate_median_and_measurement_history(self):
        survey=Survey(self.bed,'test',.065)
        first=survey.ingest([self.detection(s=2.,stamp=1)])[0]
        self.assertEqual(survey.ingest([self.detection(s=2.02,stamp=2)])[0],first)
        self.assertAlmostEqual(self.bed.local(survey.fruits[0]['position_map_m'])[0],2.01)
        self.assertEqual(survey.ingest([self.detection(s=2.06,stamp=3)])[0],first)
        fruit=survey.fruits[0]
        self.assertAlmostEqual(self.bed.local(fruit['position_map_m'])[0],2.02)
        self.assertEqual(fruit['seen_count'],3)
        self.assertEqual(len(fruit['position_samples']),3)
        np.testing.assert_allclose(fruit['position_first_map_m'],self.bed.world(2.,1.14,.8))

    def test_fused_position_can_release_a_hold(self):
        survey=Survey(self.bed,'test',.065)
        first=survey.ingest([self.detection(n=1.218)])[0]
        self.assertEqual(len(survey.plan.holds),1)
        again=survey.ingest([self.detection(n=1.198,stamp=2)])[0]
        self.assertEqual(first,again)
        self.assertAlmostEqual(self.bed.local(survey.fruits[0]['position_map_m'])[1],1.208)
        self.assertEqual(survey.plan.holds,[])
        self.assertEqual(survey.windows()[0]['expected_count'],1)

    def test_outside_after_fusion_is_removed_and_can_rejoin_reserved_window(self):
        survey=Survey(self.bed,'test',.065)
        survey.ingest([self.detection(n=1.208)])
        old=survey.windows()[0]
        survey.ingest([self.detection(n=1.238,stamp=2)])
        self.assertEqual(survey.windows(),[])
        self.assertEqual(survey.record()['harvest_task_count'],0)
        self.assertEqual(survey.record()['reserved_empty_window_count'],1)
        self.assertEqual(len(survey.plan.holds),1)
        survey.ingest([self.detection(n=1.208,stamp=3)])
        new=survey.windows()[0]
        self.assertEqual(new['window_id'],old['window_id'])
        self.assertEqual(new['goal_pose'],old['goal_pose'])
        self.assertEqual(new['corners_map_m'],old['corners_map_m'])
        self.assertEqual(survey.plan.holds,[])

    def test_user_first_coordinate_fixture_resolves_three_holds(self):
        survey=Survey(self.bed,'fixture',.065)
        source_to_id={}
        stamps=sorted({f['first_stamp_ns'] for f in self.fixture['fruits']})
        for stamp in stamps:
            group=[f for f in self.fixture['fruits'] if f['first_stamp_ns']==stamp]
            ids=survey.ingest([dict(f,stamp_ns=stamp) for f in group])
            source_to_id.update({f['id'].split('_')[-1]:new for f,new in zip(group,ids)})
        members=[fid for window in survey.windows() for fid in window['member_ids']]
        for suffix in ['F0001','F0003','F0005']:
            self.assertIn(source_to_id[suffix],members)
        self.assertEqual(len(members),len(set(members)))
        self.assertEqual(len(members),13)
        self.assertEqual(survey.plan.holds,[])
        print('Stored first-coordinate fixture:',len(survey.windows()),'windows,',len(members),'IDs, no holds')

    def test_empty_reserved_window_ids_are_not_reused(self):
        survey=Survey(self.bed,'test',.065)
        survey.ingest([self.detection(n=1.208)])
        survey.ingest([self.detection(n=1.238,stamp=2)])
        survey.ingest([self.detection(s=4.,stamp=3)])
        self.assertTrue(survey.windows()[0]['window_id'].endswith('W002'))

    def test_new_acceptance_box_dimensions_and_placement_margin(self):
        survey=Survey(self.bed,'test',.065)
        survey.ingest([self.detection()])
        window=survey.windows()[0]
        nominal=np.ptp(window['corners_map_m'],axis=0)
        expanded=np.ptp(window['acceptance_corners_map_m'],axis=0)
        np.testing.assert_allclose(expanded-nominal,[.04,.04,.04])
        self.assertEqual(self.bed.plan_cfg.margin,.03)
        self.assertEqual(self.bed.plan_cfg.membership_margin,0.)

    def test_config_updater_preserves_other_settings(self):
        spec=importlib.util.spec_from_file_location('range_patch',ROOT/'scripts/apply_scout_range_fix.py')
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        data={'unrelated':{'speed':.137},'sections':{'BED_01':{'harvest':{'side_margin_m':.03,'width_m':.35}}}}
        self.assertTrue(module.configure(data))
        self.assertFalse(module.configure(data))
        self.assertEqual(data['unrelated'],{'speed':.137})
        self.assertEqual(data['sections']['BED_01']['harvest']['side_margin_m'],.03)
        self.assertEqual(data['sections']['BED_01']['harvest']['range_tolerance_m'],.02)

    def test_truth_evaluation_uses_new_height_allowance(self):
        spec=importlib.util.spec_from_file_location('truth_range',ROOT/'sim/tools/compare_scout_truth.py')
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        survey=Survey(self.bed,'test',.065)
        survey.ingest([self.detection(z=1.06)])
        point=np.array(survey.fruits[0]['position_map_m'])
        cfg=json.loads((ROOT/'sim/ros_ws/src/farm_sim_config/config/scout_survey.json').read_text())
        cfg['sections']={'BED_01':self.bed.cfg}
        report={'config':cfg,'status':'SUCCESS','sections':{'BED_01':{'status':'COMPLETE','survey':survey.record()}}}
        truth={'fruits':[{'gt_id':'test_gt','bed_prim':self.bed.cfg['evaluation_bed_prim'],
            'class_name':'Red','center_world_m':point.tolist(),
            'aabb_world_m':[(point-.002).tolist(),(point+.002).tolist()]}]}
        result=module.compare(report,truth,ROOT,.03)
        self.assertEqual(result['tolerance_m'],.03)
        section=result['sections']['BED_01']
        self.assertEqual(section['work_range_tolerance_m'],.02)
        self.assertEqual(section['evaluated_id_count'],1)
        self.assertEqual(section['matched_count'],1)


if __name__=='__main__':unittest.main()
