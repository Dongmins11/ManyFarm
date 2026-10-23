"""베드 깊이에만 측정 오차 여유를 적용하고 다른 축/실제 작업 상자는 보존한다."""
from dataclasses import replace
from pathlib import Path
import json,sys,unittest
import numpy as np

SRC=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(SRC/'scout_robot'),str(SRC/'farm_navigation')]
from scout_robot.b_planner import Config,Fruit,plan_harvest,extend_plan
from scout_robot.survey_core import StraightBed,Survey
from scout_robot.route import load_route
ROOT=Path(__file__).resolve().parents[5]

class DepthTolerance(unittest.TestCase):
    def setUp(self) -> None:
        self.cfg=Config(route_end=2.,depth_tolerance=.02)
    def test_default_is_strict_and_invalid_allowance_is_rejected(self) -> None:
        result=plan_harvest([Fruit('edge',.2,.051,.5)],replace(self.cfg,depth_tolerance=0.))
        self.assertEqual(result.holds[0].reason,'depth_out_of_range')
        for value in (-.001,float('nan'),float('inf')):
            with self.assertRaises(ValueError):replace(self.cfg,depth_tolerance=value).validate()
    def test_both_depth_edges_expand_but_height_does_not(self) -> None:
        result=plan_harvest([Fruit('a',.2,-.07,.5),Fruit('b',.3,.07,.5),
            Fruit('deep',.4,.0701,.5),Fruit('high',.5,0,.751)],self.cfg)
        self.assertEqual(set(result.tasks[0].member_ids),{'a','b'})
        self.assertEqual({h.anchor_id:h.reason for h in result.holds},
            {'deep':'depth_out_of_range','high':'height_out_of_range'})
        self.assertAlmostEqual(result.tasks[0].window_y_min,-.05)
        self.assertAlmostEqual(result.tasks[0].window_y_max,.05)
    def test_later_member_joins_existing_window_using_depth_allowance(self) -> None:
        first=plan_harvest([Fruit('a',.2,0,.5)],self.cfg)
        result=extend_plan(first,[Fruit('b',.3,.069,.5)],self.cfg)
        self.assertEqual(len(result.tasks),1)
        self.assertEqual(result.tasks[0].member_ids,('a','b'))
        self.assertEqual(result.tasks[0].base_y,first.tasks[0].base_y)
    def test_revalidation_keeps_inside_and_releases_outside_depth(self) -> None:
        first=plan_harvest([Fruit('a',.2,0,.5)],self.cfg)
        keep=extend_plan(first,[Fruit('a',.2,.069,.5)],self.cfg,revalidate=True)
        self.assertEqual(keep.tasks[0].member_ids,('a',))
        drop=extend_plan(keep,[Fruit('a',.2,.071,.5)],self.cfg,revalidate=True)
        self.assertEqual(drop.tasks[0].member_ids,())
        self.assertEqual(drop.holds[0].reason,'depth_out_of_range')
    def test_new_member_does_not_get_extra_progress_direction_margin(self) -> None:
        first=plan_harvest([Fruit('a',.2,0,.5)],self.cfg)
        boundary=first.tasks[0].safe_x_max
        result=extend_plan(first,[Fruit('b',boundary+.001,0,.5)],self.cfg)
        self.assertNotIn('b',result.tasks[0].member_ids)
    def test_all_sections_expose_only_depth_expansion_and_keep_nominal_box(self) -> None:
        config=json.loads((ROOT/'sim/ros_ws/src/farm_sim_config/config/scout_survey.json').read_text())
        self.assertEqual(len(config['sections']),16)
        for section,cfg in config['sections'].items():
            bed=StraightBed(load_route(ROOT/cfg['route_file'],cfg['node_ids']),cfg)
            self.assertEqual(bed.plan_cfg.depth_tolerance,.02)
            survey=Survey(bed,'test',.05)
            survey.ingest([dict(position_map_m=bed.world(1.,bed.bed_n+.06,.9),
                class_name='Red',confidence=.9,stamp_ns=100)])
            window=survey.windows()[0]
            inner=np.array([bed.local(p)for p in window['corners_map_m']])
            outer=np.array([bed.local(p)for p in window['acceptance_corners_map_m']])
            self.assertAlmostEqual(np.ptp(inner[:,1]),.1)
            self.assertAlmostEqual(np.ptp(outer[:,1]),.14)
            self.assertAlmostEqual(np.ptp(outer[:,0]),np.ptp(inner[:,0]))
            self.assertAlmostEqual(np.ptp(outer[:,2]),np.ptp(inner[:,2]))
            self.assertEqual(window['depth_tolerance_m'],.02)
            self.assertEqual(window['expected_count'],1)
