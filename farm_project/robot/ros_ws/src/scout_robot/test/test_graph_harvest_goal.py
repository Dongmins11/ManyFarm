import unittest
import copy
import json
from pathlib import Path
from scout_robot.survey_core import StraightBed,Survey
from scout_robot.graph_harvest_goal import load_harvest_route
from farm_navigation.route import load_route
ROOT=Path(__file__).resolve().parents[4]

class GraphGoalTests(unittest.TestCase):
    def bed(self, graph=True):
        cfg=json.loads((ROOT/'config/survey/scout_real.json').read_text())['sections']['SEC01']
        root=ROOT.parent
        if not graph:cfg.pop('harvest_goal',None)
        return StraightBed(load_route(root/cfg['route_file'],cfg['node_ids']),cfg,
                           harvest_route=load_harvest_route(root,cfg))
    def test_graph_line_and_arm_geometry(self):
        b=self.bed();s=Survey(b,'test',.065)
        s.ingest([dict(position_map_m=[2,.42,.9],class_name='Red',confidence=.9,stamp_ns=1)])
        w=s.windows()[0]
        self.assertAlmostEqual(w['goal_pose']['position'][1],-.035)
        # 먼 경계 15cm 확장으로 창 중심만 7.5cm 이동; 정차선은 유지.
        self.assertAlmostEqual(w['actual_work_distance_m'],.345)
        ys = [p[1] for p in w['corners_map_m']]
        self.assertAlmostEqual(min(ys), .37)
        self.assertAlmostEqual(max(ys), .62)
        self.assertAlmostEqual(w['nominal_work_distance_m'],.315)
        self.assertEqual(w['goal_pose']['yaw'],0)
        self.assertAlmostEqual(w['arm_y'],w['base_y']+.185)
    def test_default_unchanged(self):
        b=self.bed(False)
        self.assertAlmostEqual(b.world(0,b.plan_cfg.route_y)[1],-.08)
    def test_rotated_frame(self):
        b=self.bed();cfg=copy.deepcopy(b.cfg)
        route=[(0,0,0,0),(1,0,3,0)]
        h=[(11,-.685,0,0),(12,-.685,1,0),(14,-.685,3,0)]
        rotated=StraightBed(route,cfg,harvest_route=h)
        self.assertAlmostEqual(rotated.world(1,rotated.plan_cfg.route_y)[0],-.685)
    def test_nonparallel_rejected(self):
        b=self.bed()
        with self.assertRaisesRegex(ValueError,'parallel'):
            StraightBed([(0,0,0,0),(1,3,0,0)],b.cfg,
                        harvest_route=[(11,0,.6,0),(14,3,.7,0)])
