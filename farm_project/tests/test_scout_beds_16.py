"""Offline route handedness, per-side geometry and config migration checks."""
import argparse
import ast
import copy
import importlib.util
import json
import math
from pathlib import Path
import sys
import unittest
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'robot/ros_ws/src/scout_robot'))
from scout_robot.route import load_route
from scout_robot.survey_core import StraightBed,Survey
from scout_robot.segments import plan_segments
spec=importlib.util.spec_from_file_location('apply_beds',ROOT/'scripts/apply_scout_beds_16.py')
migration=importlib.util.module_from_spec(spec);spec.loader.exec_module(migration)
GRAPH=ROOT/migration.GRAPH
DATA=json.loads(GRAPH.read_text())
CFG=json.loads((ROOT/migration.CONFIG).read_text())
K=np.array([[344.,0,320],[0,344.,192],[0,0,1.]])
C=np.array([[1,0,0,0],[0,0,1,0],[0,-1,0,.6],[0,0,0,1.]])
PRE={'height_band_m':[.603,1.053],'edge_fraction':.05}
# Independent expected USD background bed centers, top row then bottom row.
PHYSICAL=[(2,-5,6),(4,-2,6),(6,2,6),(8,5,6),(1,-5,-6),(3,-2,-6),(5,2,-6),(7,5,-6)]


class BedRoutes(unittest.TestCase):
    def test_16_sides_match_usd_beds_and_camera_left(self):
        sections=DATA['survey_sections']
        self.assertEqual(list(sections),[f'BED_{i:02d}' for i in range(1,17)])
        ids=[];segments=set()
        for i,(sid,s) in enumerate(sections.items()):
            with self.subTest(section=sid):
                usd,cx,cy=PHYSICAL[i//2];west=i%2==0
                self.assertEqual(s['evaluation_bed_prim'],f'/World/Vegetation/Bed_{usd:02d}')
                r=load_route(GRAPH,s['node_ids']);b=StraightBed(r,CFG['sections'][sid])
                self.assertEqual(len(r),8);self.assertAlmostEqual(b.length,8.)
                self.assertAlmostEqual(b.yaw,-math.pi/2 if west else math.pi/2)
                self.assertGreater(np.dot(np.array([cx,cy])-b.origin,b.n),0)
                plane=b.world(4.,b.bed_n)
                self.assertAlmostEqual(plane[0],cx+(-.515 if west else .515))
                self.assertAlmostEqual(plane[1],cy)
                planned=plan_segments(b,sid,K,C,640,384,PRE,.15)
                self.assertEqual(len(planned['segments']),5)
                for item in planned['segments']:
                    self.assertNotIn(item['segment_id'],segments);segments.add(item['segment_id'])
                ids.extend(s['node_ids'])
        self.assertEqual(len(set(ids)),128);self.assertEqual(len(segments),80)

    def test_bed_01_full_length_endpoints_and_interior_nodes(self):
        r=load_route(GRAPH,list(range(1,9)))
        for i,(n,x,y,yaw) in enumerate(r):
            self.assertEqual(n,i+1);self.assertAlmostEqual(x,-6.655)
            self.assertAlmostEqual(y,10. if i==0 else 2. if i==7 else 9.5-i);self.assertAlmostEqual(yaw,-math.pi/2)

    def test_box_geometry_rotates_for_all_sides(self):
        for sid,s in CFG['sections'].items():
            with self.subTest(section=sid):
                bed=StraightBed(load_route(ROOT/s['route_file'],s['node_ids']),s)
                survey=Survey(bed,sid,.065);p=bed.world(3.5,bed.bed_n,.8)
                survey.ingest([{'position_map_m':p,'class_name':'Red','confidence':.9,'stamp_ns':1}],sid+'_S001')
                windows=survey.windows();self.assertEqual(len(windows),1)
                self.assertEqual(windows[0]['expected_count'],1)
                local=bed.local(p);np.testing.assert_allclose(local,[3.5,1.14,.8],atol=1e-12)
                self.assertAlmostEqual(math.cos(bed.harvest_yaw-bed.yaw),-1.)

    def test_migration_preserves_tuning_and_is_idempotent(self):
        source=copy.deepcopy(CFG);source['sections']={'BED_01':source['sections']['BED_01']}
        source['arrival_tolerance_m']=.071
        source['sections']['BED_01']['harvest']['range_tolerance_m']=.023
        source['sections']['BED_01']['segmentation']={'mode':'manual','segments':[{'segment_id':'CUSTOM','offset_m':3.5}]}
        before=copy.deepcopy(source);out=migration.configure(source,DATA)
        self.assertEqual(source,before);self.assertEqual(out['arrival_tolerance_m'],.071)
        self.assertEqual(out['sections']['BED_01']['segmentation'],before['sections']['BED_01']['segmentation'])
        self.assertEqual(out['sections']['BED_02']['segmentation']['mode'],'auto')
        self.assertEqual(out['sections']['BED_02']['harvest']['range_tolerance_m'],.023)
        out['sections']['BED_02']['harvest']['width_m']=.36
        self.assertEqual(migration.configure(out,DATA),out)

    def test_control_argument_selection(self):
        path=ROOT/'control/scripts/send_scout_area.py'
        tree=ast.parse(path.read_text());fn=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='parse_args')
        ns={'argparse':argparse,'Path':Path,'json':json,'__file__':str(path)}
        exec(compile(ast.Module(body=[fn],type_ignores=[]),str(path),'exec'),ns)
        parse=ns['parse_args']
        self.assertEqual(parse([]).section,['BED_01'])
        self.assertEqual(parse(['--section','BED_02','BED_01']).section,['BED_02','BED_01'])
        self.assertEqual(parse(['--all']).section,[f'BED_{i:02d}' for i in range(1,17)])


if __name__=='__main__':unittest.main()
