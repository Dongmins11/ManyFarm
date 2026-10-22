"""정답 범위·예찰 예상량·실제 수확량을 분리하고 재시도 실적을 중복 합산하지 않는다."""
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'sim/tools'))
sys.path.insert(0, str(ROOT/'robot/ros_ws/src/farm_navigation'))
from campaign_performance import ratios, write_performance, loss_breakdown


class PerformanceTests(unittest.TestCase):
    def test_counts_are_not_clamped_or_mislabeled_as_recall(self):
        value = ratios(2, 3, 1)
        self.assertEqual(value['scout_count_ratio'], 1.5)
        self.assertEqual(value['expected_minus_harvested'], 2)
        self.assertIsNone(ratios(None, 0, 0)['harvest_to_actual_ratio'])
        self.assertIsNone(ratios(0, 0, 1)['harvest_to_expected_ratio'])

    def test_truth_scope_and_latest_attempt_have_independent_counts(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fruits = [dict(gt_id=f'/World/Vegetation/Bed_02/Fruits/{i}', class_name=color,
                           center_world_m=pos, aabb_world_m=[pos,pos])
                      for i,(color,pos) in enumerate([
                          ('red',[-5.5,6,.9]), ('yellow',[-5.5,5,.9]), ('green',[-5.5,4,.9]),
                          ('red',[-4.5,6,.9]), ('red',[-5.5,6,2.])])]
            (root/'evaluation_scene_initial.json').write_text(json.dumps(dict(complete=True, fruits=fruits)))
            for attempt, status, count in ((1,'FAILED',1), (2,'SUCCESS',1)):
                d = root/f'SEC01_attempt_{attempt:04d}'
                d.mkdir()
                (d/'result.json').write_text(json.dumps(dict(section='SEC01',status=status,
                    scout_result=dict(result=dict(task_id='scout', harvest_tasks=[dict(expected_count=3)])),
                    harvest_results=[dict(result=dict(result_code='SUCCESS',harvested_count=count))])))
            survey_path = root/'SEC01_attempt_0001/artifacts/scout_survey/session/survey.json'
            survey_path.parent.mkdir(parents=True)
            cfg = json.loads((ROOT/'sim/ros_ws/src/farm_sim_config/config/scout_survey.json').read_text())
            survey_path.write_text(json.dumps(dict(goal=dict(task_id='scout'),status='SUCCESS',config=cfg,
                sections=dict(SEC01=dict(status='SUCCESS',survey=dict(fruits=[],windows=[]))))))
            report = write_performance(root)
            row = report['sections']['SEC01']
            self.assertEqual(row['attempt'], 'SEC01_attempt_0002')
            self.assertEqual(row['counts']['actual_target_count'], 2)
            self.assertEqual(row['counts']['expected_count'], 3)
            self.assertEqual(row['counts']['harvested_count'], 1)
            self.assertEqual(len(row['scout_evaluation']['excluded_gt']), 3)
            self.assertEqual(len(report['attempt_reports']), 2)
            self.assertTrue(row['scout_evaluation']['retrospective_same_scene'])

    def test_missing_detection_window_duplicate_and_arm_loss_are_separate(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            d=root/'artifacts/robotarm/student/session/job';d.mkdir(parents=True)
            (d/'performance.json').write_text(json.dumps(dict(window_id='w')))
            events=[dict(event='CANDIDATES',candidates=[dict(target_id='a',camera_target_id='1')]),
                    dict(event='TARGET',target_id='a')]
            (d/'trace.jsonl').write_text('\n'.join(json.dumps(x) for x in events))
            evaluation=dict(status='OK',matches=[dict(gt_id=x) for x in ['a','b','c']],
                missed_gt_ids=['d'],possible_duplicate_ids=['dup'],duplicate_window_gt_owners={},
                unmatched_ids=['dup'],window_checks=[dict(window_id='w',matched_gt_ids=['a','b'],unmatched_member_ids=[])])
            r=loss_breakdown(evaluation,[],root)
            self.assertEqual(r['scout']['detected_without_window_gt_ids'],['c'])
            self.assertEqual(r['scout']['unique_gt_missing_from_windows'],['c','d'])
            self.assertEqual(r['arm']['matched_window_object_case_counts'],dict(
                attempted_without_confirmed_basket_passage=1,not_selected_by_arm_camera=1))


if __name__ == '__main__':
    unittest.main()
