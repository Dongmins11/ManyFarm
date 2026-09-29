"""Bed configuration and mission lifecycle tests using fake ROS/vision I/O."""
import copy
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace as NS
import unittest
from unittest.mock import patch
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'robot/ros_ws/src/scout_robot'))
sys.path.insert(0,str(ROOT/'tests'))
from scout_robot.survey_core import StraightBed,Survey,transform_points
from scout_robot.segments import plan_segments
from test_scout_arrival import server,server_namespace,MissionCanceled

K=np.array([[344.,0,320],[0,344.,192],[0,0,1.]])
C=np.array([[1,0,0,0],[0,0,1,0],[0,-1,0,.6],[0,0,0,1.]])
PRE={'height_band_m':[.603,1.053],'edge_fraction':.05}


def bed(length=7.,mode='auto',finish='last_segment'):
    section=json.loads((ROOT/'tests/fixtures/scout_range_56571de5ad6f.json').read_text())['section']
    section['harvest'].update(range_tolerance_m=.02,membership_margin_m=0.)
    section['segmentation']={'mode':mode,'overlap_fraction':.15}
    section['finish_at']=finish
    return StraightBed([(1,-6.655,9.5,0),(8,-6.655,9.5-length,0)],section)


def design(b,section='BED_01'):
    return plan_segments(b,section,K,C,640,384,PRE,.15)


class SegmentTests(unittest.TestCase):
    def test_auto_counts_depend_on_bed_length(self):
        first=design(bed());second=design(bed(3.),'BED_REAL')
        self.assertEqual(len(first['segments']),5)
        self.assertEqual(len(second['segments']),2)
        self.assertEqual(first['segments'][0]['segment_id'],'BED_01_S001')
        self.assertEqual(second['segments'][0]['segment_id'],'BED_REAL_S001')

    def test_manual_stops_and_ids_are_used(self):
        b=bed();auto=design(b)
        b.cfg['segmentation']={'mode':'manual','segments':[
            {'segment_id':f'MANUAL_{i}','offset_m':v['offset_m']}
            for i,v in enumerate(auto['segments'])]}
        manual=design(b)
        self.assertEqual(manual['stops_s_m'],auto['stops_s_m'])
        self.assertEqual(manual['segments'][0]['segment_id'],'MANUAL_0')

    def test_manual_gap_duplicate_reverse_and_invalid_values_fail(self):
        b=bed();items=[{'segment_id':s['segment_id'],'offset_m':s['offset_m']} for s in design(b)['segments']]
        cases=[items[:1]+items[2:],list(reversed(items)),
               [dict(v,segment_id='same') for v in items],
               [dict(items[0],offset_m=float('nan'))]+items[1:],
               [dict(items[0],offset_m=-1)]+items[1:],items[1:]]
        for values in cases:
            with self.subTest(values=values):
                b.cfg['segmentation']={'mode':'manual','segments':values}
                with self.assertRaises(ValueError):design(b)

    def test_window_owner_is_creation_segment_and_survives_reobservation(self):
        b=bed();survey=Survey(b,'test',.065)
        def detection(n,stamp):return dict(position_map_m=b.world(2,n,.8),class_name='Red',confidence=.9,stamp_ns=stamp)
        # First observation held; creation happens only after the second view.
        survey.ingest([detection(1.218,1)],'S001')
        self.assertEqual(survey.windows(),[])
        survey.ingest([detection(1.198,2)],'S002')
        self.assertEqual(survey.windows()[0]['segment_id'],'S002')
        survey.ingest([detection(1.198,3)],'S003')
        self.assertEqual(survey.windows()[0]['segment_id'],'S002')
        self.assertEqual(survey.fruits[0]['first_segment_id'],'S001')
        self.assertEqual(survey.fruits[0]['observed_segment_ids'],['S001','S002','S003'])

    def run_mission(self,finish='last_segment',failure_at=None,cancel=False,two_beds=False):
        node=server();node.beds={'BED_01':bed(finish=finish)}
        if two_beds:node.beds['BED_02']=bed(finish=finish)
        node.cfg.update(vision_config='unused.json',association_distance_m=.065,
            association_band_half_depth_m=.2,overlap_fraction=.15)
        node.vcfg={'preprocess':PRE};node.python=Path(sys.executable)
        node.get_parameter=lambda name:NS(value=False if name=='headless' else '0')
        node.lookup=lambda *_:np.eye(4)
        node.stationary_now=lambda:True;node.show=lambda _:None
        moves=[];feedback=[];terminal=[];captures=[]
        def navigate(xy,yaw):moves.append(list(xy));return 100
        node.navigate=navigate
        request=NS(robot_id='scout_01',task_id='test',section_ids=list(node.beds),
                   map_id='farm_map_v1',frame_id='map',crop_type='PAPRIKA',target_ripeness='RIPE')
        action=NS(request=request,is_cancel_requested=False,publish_feedback=lambda f:feedback.append(f),
                  succeed=lambda:terminal.append('success'),abort=lambda:terminal.append('abort'),
                  canceled=lambda:terminal.append('canceled'))
        class FakeWorker:
            def __init__(self,*_):pass
            def receive(self,*_):return {'ready':True}
            def call(self,op,check,**kwargs):
                meta={'session':'camera','pose_frame':'scout_01/odom','stamp_ns':200+len(captures),
                      'K':K.tolist(),'T_odom_camera_optical':C.tolist()}
                if op=='info':return {'metadata':meta,'width':640,'height':384}
                if op=='capture':
                    captures.append(True)
                    if failure_at==len(captures):
                        if cancel:
                            action.is_cancel_requested=True
                            raise MissionCanceled('test cancellation')
                        raise RuntimeError('test capture failure')
                    return {'metadata':meta,'timings':{},'rejected':[],
                            'detections':[{'position_odom_m':node.beds['BED_01'].world(2.,1.14,.8),
                                           'class_name':'Red','confidence':.9,'mask_box_original_xyxy':[10,10,20,20]}]}
                if op=='annotate':return {'saved':kwargs['directory']}
                raise AssertionError(op)
            def close(self):pass
        globals_patch={'Survey':Survey,'plan_segments':plan_segments,'Worker':FakeWorker,'transform_points':transform_points,
                       'HarvestTask':lambda:NS(goal_pose=NS()),'Point':NS,
                       'ScoutArea':NS(Result=NS,Feedback=NS)}
        with tempfile.TemporaryDirectory() as tmp,patch.dict(server_namespace,globals_patch):
            node.root=Path(tmp)
            result=node.execute(action)
            paths=list(node.root.glob('runs/scout_survey/*/survey.json'))
            self.assertEqual(len(paths),1)
            report=json.loads(paths[0].read_text())
        return result,report,feedback,moves,terminal

    def test_five_segments_one_bed_batch_no_tail_drive(self):
        result,report,feedback,moves,terminal=self.run_mission()
        self.assertEqual(result.result_code,'SUCCESS')
        self.assertEqual(result.completed_segment_count,5)
        self.assertEqual(len(moves),6) # Approach plus five captures, no end goal.
        phases=[f.phase for f in feedback]
        self.assertEqual(phases.count('SEGMENT_COMPLETE'),5)
        self.assertEqual(phases.count('SECTION_COMPLETE'),1)
        self.assertNotIn('FINISHING',phases)
        completed=[f for f in feedback if f.phase=='SEGMENT_COMPLETE']
        self.assertEqual([f.completed_segment_count for f in completed],[1,2,3,4,5])
        self.assertTrue(all(not f.harvest_tasks for f in completed))
        batch=[f for f in feedback if f.phase=='SECTION_COMPLETE'][0]
        self.assertEqual(len(batch.harvest_tasks),1)
        self.assertEqual(batch.harvest_tasks[0].segment_id,'BED_01_S001')
        self.assertEqual(report['sections']['BED_01']['post_capture_navigation']['status'],'SKIPPED')
        self.assertEqual(terminal,['success'])

    def test_route_end_policy_keeps_tail_goal_and_announces_it(self):
        result,report,feedback,moves,_=self.run_mission(finish='route_end')
        self.assertEqual(result.result_code,'SUCCESS')
        self.assertEqual(len(moves),7)
        self.assertAlmostEqual(moves[-1][1],2.5)
        self.assertEqual([f.phase for f in feedback].count('FINISHING'),1)
        self.assertEqual(report['sections']['BED_01']['post_capture_navigation']['status'],'ARRIVED')

    def test_failure_counts_only_completed_segments_and_sends_no_batch(self):
        result,report,feedback,_,terminal=self.run_mission(failure_at=3)
        self.assertEqual(result.result_code,'FAILED')
        self.assertEqual(result.completed_segment_count,2)
        self.assertEqual(result.completed_section_ids,[])
        self.assertFalse(any(f.phase=='SECTION_COMPLETE' for f in feedback))
        self.assertEqual(report['sections']['BED_01']['segments'][-1]['status'],'FAILED')
        self.assertEqual(terminal,['abort'])

    def test_cancellation_keeps_partial_segment_count(self):
        result,report,feedback,_,terminal=self.run_mission(failure_at=3,cancel=True)
        self.assertEqual(result.result_code,'CANCELED')
        self.assertEqual(result.completed_segment_count,2)
        self.assertEqual(terminal,['canceled'])

    def test_counts_across_two_beds_and_independent_segment_ids(self):
        result,report,feedback,moves,_=self.run_mission(two_beds=True)
        self.assertEqual(result.completed_segment_count,10)
        self.assertEqual(result.completed_section_ids,['BED_01','BED_02'])
        batches=[f for f in feedback if f.phase=='SECTION_COMPLETE']
        self.assertEqual(len(batches),2)
        self.assertEqual(batches[1].harvest_tasks[0].segment_id,'BED_02_S001')

    def test_config_migration_preserves_existing_manual_settings(self):
        spec=importlib.util.spec_from_file_location('segment_patch',ROOT/'scripts/apply_scout_segment_config.py')
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        manual={'mode':'manual','segments':[{'segment_id':'CUSTOM','offset_m':1.}]}
        data={'sections':{'BED_01':{'segment_id':'BED_01_BATCH','harvest':{'range_tolerance_m':.02}},
                          'BED_02':{'segmentation':manual,'finish_at':'route_end'}}}
        self.assertTrue(module.configure(data));self.assertFalse(module.configure(data))
        self.assertEqual(data['sections']['BED_01']['finish_at'],'last_segment')
        self.assertEqual(data['sections']['BED_02']['finish_at'],'route_end')
        self.assertEqual(data['sections']['BED_02']['segmentation'],manual)
        self.assertEqual(data['sections']['BED_01']['harvest']['range_tolerance_m'],.02)
        self.assertNotIn('segment_id',data['sections']['BED_01'])


if __name__=='__main__':unittest.main()
