"""ROS/Isaac 없는 계약·기하·경로·실행 조합 검사. 실기 구동 검증은 별도."""
import copy
import importlib.util
import json
import math
from pathlib import Path
import sys
import tempfile
import time
from types import SimpleNamespace as NS
import unittest
import numpy as np
import yaml
ROOT = Path(__file__).resolve().parents[2]
for tree, pkg in [('sim','farm_sim_harvest'),('sim','farm_sim_runtime'),('robot','farm_navigation'),('robot','harvest_robot')]:
    sys.path.insert(0, str(ROOT / tree / 'ros_ws/src' / pkg))
from harvest_robot.contract import validate_task, result_fields
from farm_sim_harvest.evaluation import count_snapshot, SceneEvaluator, evaluate_record
from harvest_robot.state_controller import HarvestStateController
from harvest_robot.mission import HarvestMission, MissionCanceled
from farm_sim_runtime.fleet_config import load_fleet
from farm_navigation.route import RouteGraph
CONFIG = ROOT/'sim/ros_ws/src/farm_sim_config/config'

def goal():
    return NS(robot_id='harvest_01',map_id='farm_map_v1',harvest_task=NS(
        task_id='test',window_id='SEC01_G01_W01',
        expected_count=9,goal_pose=NS(frame_id='map',position=NS(x=-5.955,y=6.,z=0.),yaw=-math.pi/2)))

def snapshot():
    T=np.array([[0.,-1,0,10],[1,0,0,20],[0,0,1,0],[0,0,0,1]])
    fruits=[]
    for ident,color,local in [('r','red',[.5,0,0]),('y','yellow',[0,.5,0]),('g','green',[0,0,0]),('out','red',[0,0,.501])]:
        fruits.append(dict(gt_id=ident,class_name=color,center_world_m=(T[:3,:3]@local+T[:3,3]).tolist()))
    return dict(complete=True,T_world_base=T.tolist(),fruits=fruits,stamp_ns=1000000000,
                scene_session='one',robot_id='harvest_01',map_id='farm_map_v1',written_monotonic_s=time.monotonic())
BOX=dict(center_m=[0,0,0],size_m=[1,1,1])

class ContractTests(unittest.TestCase):
    def test_valid_and_zero_count(self):
        g=goal();validate_task(g,json.loads((CONFIG/'harvest_task.json').read_text()))
        for status in ('SUCCESS','FAILED','CANCELED'):
            r=result_fields(g,status)
            self.assertEqual((r['expected_count'],r['harvested_count'],r['failed_count']),(9,0,0))
    def test_invalid_contract(self):
        config=json.loads((CONFIG/'harvest_task.json').read_text())
        for key,value in [('task_id',''),('expected_count',-1),('window_id',''),('window_id','   ')]:
            g=goal();setattr(g.harvest_task,key,value)
            with self.assertRaises(ValueError):validate_task(g,config)
        g=goal();g.harvest_task.goal_pose.position.x=float('nan')
        with self.assertRaises(ValueError):validate_task(g,config)
    def test_state_completion_and_error(self):
        for error in (None,RuntimeError('failed'),MissionCanceled('cancel')):
            def run():
                if error:raise error
                return {'stamp_ns':123}
            c=HarvestStateController(NS(run=run));c.start()
            self.assertTrue(c.done.wait(2));c.close()
            self.assertIs(c.error,error)
            if not error:self.assertEqual(c.outcome,{'stamp_ns':123})
    def test_failed_cancel_blocks_next_motion(self):
        def fail():raise RuntimeError('move error')
        def cancel():raise RuntimeError('stop unknown')
        n=NS(check=lambda:None,navigator=NS(preflight_navigation=fail,cancel_nav=cancel),blocked=False)
        with self.assertRaisesRegex(RuntimeError,'CANCEL_UNCONFIRMED'):HarvestMission(n,goal()).run()
        self.assertTrue(n.blocked)

class AuditTests(unittest.TestCase):
    def test_actual_rotated_pose_boundary_color_and_repeat(self):
        r=count_snapshot(snapshot(),BOX,9,{'r'})
        self.assertEqual((r['actual_in_workspace'],r['count_delta'],r['ignored_green_count']),(2,-7,1))
        self.assertEqual(r['repeated_gt_ids'],['r'])
        self.assertEqual({f['gt_id'] for f in r['matched_fruits']},{'r','y'})
    def test_audit_is_independent_of_action_result(self):
        record=dict(robot_id='harvest_01',map_id='farm_map_v1',arrival={'stamp_ns':1},result=dict(result_code='SUCCESS',expected_count=7,harvested_count=0))
        def missing(*args):raise FileNotFoundError('snapshot')
        output=evaluate_record(record,NS(evaluate=missing))
        self.assertEqual(output['evaluation']['status'],'UNAVAILABLE')
        self.assertEqual(output['result']['result_code'],'SUCCESS')
        self.assertNotIn('evaluation',record)
        record['result']['result_code']='FAILED'
        self.assertEqual(evaluate_record(record,NS(evaluate=missing))['evaluation']['status'],'SKIPPED_NOT_ARRIVED')
    def test_corrupt_snapshot_is_not_zero(self):
        for kind in ('incomplete','duplicate','pose'):
            s=snapshot()
            if kind=='incomplete':s['complete']=False
            elif kind=='duplicate':s['fruits'].append(s['fruits'][0])
            else:s['T_world_base'][0][0]=1
            with self.assertRaises(ValueError):count_snapshot(s,BOX,9,set())
    def test_stale_missing_and_session_reset(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'snapshot.json';e=SceneEvaluator(dict(snapshot_file=p.name,workspace=BOX),Path(d))
            with self.assertRaises(FileNotFoundError):e.evaluate(goal(),{'stamp_ns':1000000000})
            s=snapshot();p.write_text(json.dumps(s));r=e.evaluate(goal(),{'stamp_ns':s['stamp_ns']})
            self.assertEqual(r['repeated_gt_ids'],[])
            self.assertEqual(e.evaluate(goal(),{'stamp_ns':s['stamp_ns']})['repeated_gt_ids'],['r','y'])
            s['scene_session']='two';p.write_text(json.dumps(s))
            self.assertEqual(e.evaluate(goal(),{'stamp_ns':s['stamp_ns']})['repeated_gt_ids'],[])
            s['written_monotonic_s']-=2;p.write_text(json.dumps(s))
            with self.assertRaises(ValueError):e.evaluate(goal(),{'stamp_ns':s['stamp_ns']})

class RouteFleetTests(unittest.TestCase):
    def test_window_coordinates_inside_edges_all_sections(self):
        task=yaml.safe_load((CONFIG/'task.yaml').read_text());g=RouteGraph(CONFIG.parent/'maps/harvest_graph.geojson')
        station=tuple(task['stations']['harvest_01']['xy_m'])
        for section in task['sections'].values():
            a=g.nodes[section['harvest_route']['entry_node_id']];b=g.nodes[section['harvest_route']['exit_node_id']]
            points=[tuple(a[i]+(b[i]-a[i])*f for i in range(2)) for f in (.313,.637)]
            for p in points:self.assertFalse(any(math.dist(p,n)<1e-7 for n in g.nodes.values()))
            for start,end in [(station,points[0]),(points[0],points[1]),(points[1],station)]:
                plan=g.plan(start,end)
                self.assertLess(math.dist(plan.points[-1],end),1e-6)
        with self.assertRaises(ValueError):g.plan(station,(999.,999.))
    def test_fleet_unique_and_single_clock(self):
        configs,task=load_fleet(ROOT,CONFIG/'harvest_fleet.json')
        self.assertEqual({c['robot_id'] for c in configs},{'scout_01','harvest_01'})
        self.assertTrue(all(not c['publish_clock'] for c in configs))
        self.assertEqual(task['stations']['harvest_01']['xy_m'],[-2.,13.25])
    def test_conflicts_fail_before_launch(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'sim') as directory:
            p=Path(directory);fleet=json.loads((CONFIG/'harvest_fleet.json').read_text())
            device=json.loads((ROOT/fleet['device_configs'][0]).read_text())
            device['publish_clock']=True;(p/'device.json').write_text(json.dumps(device))
            fleet['device_configs'][0]=str(p/'device.json');(p/'fleet.json').write_text(json.dumps(fleet))
            with self.assertRaisesRegex(ValueError,'clock'):load_fleet(ROOT,p/'fleet.json')
            device['publish_clock']=False;device['runtime']['command_port']=17610
            (p/'device.json').write_text(json.dumps(device))
            with self.assertRaisesRegex(ValueError,'포트'):load_fleet(ROOT,p/'fleet.json')

spec=importlib.util.spec_from_file_location('launch_helpers',ROOT/'tests/test_launch_composition.py')
helper=importlib.util.module_from_spec(spec);spec.loader.exec_module(helper)
class HarvestLaunchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):helper.LaunchCompositionTests.setUpClass();cls.args=helper.LaunchCompositionTests.args
    @classmethod
    def tearDownClass(cls):helper.LaunchCompositionTests.tearDownClass()
    def test_fleet_counts(self):
        actions=helper.expand(helper.load('farm_sim_runtime','all.launch.py',dict(self.args,harvest='true')))
        self.assertEqual(sum(isinstance(a,helper.Process) for a in actions),1)
        names=[a.kwargs.get('executable') for a in actions if isinstance(a,helper.Node)]
        for name,count in [('ros_adapter',2),('controller_server',2),('amcl',2),('scout_node',1),('harvest_node',1),('harvest_audit',1),('clock_relay',1),('rviz2',1)]:
            self.assertEqual(names.count(name),count,name)
    def test_harvest_without_scout_server_has_clock_and_correct_rviz(self):
        actions=helper.expand(helper.load('farm_sim_runtime','all.launch.py',dict(self.args,harvest='true',scout='false')))
        nodes=[a for a in actions if isinstance(a,helper.Node)]
        names=[a.kwargs.get('executable') for a in nodes]
        self.assertNotIn('scout_node',names);self.assertIn('clock_relay',names)
        rviz=next(a for a in nodes if a.kwargs.get('executable')=='rviz2')
        self.assertTrue(rviz.kwargs['arguments'][-1].endswith('/harvest.rviz'))
    def test_common_server_same_in_sim_and_real(self):
        sim=helper.expand(helper.load('farm_bringup','harvest.launch.py',dict(self.args,mode='sim',devices='false',navigation='false')))
        self.assertEqual(len(sim),1)
        self.assertEqual(sim[0].kwargs['package'],'harvest_robot')
        self.assertTrue(sim[0].kwargs['parameters'][0]['use_sim_time'])
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            profile=yaml.safe_load((CONFIG/'harvest_runtime.yaml').read_text())
            profile['mode']='real'
            for key in ('device_config','map_yaml','nav_params','route_graph','harvest_config'):
                source=ROOT/profile[key];dest=root/source.name
                dest.write_bytes(source.read_bytes());profile[key]=str(dest)
            (root/'real.yaml').write_text(yaml.safe_dump(profile))
            actions=helper.load('farm_bringup','harvest.launch.py',dict(self.args,project_root=str(root),mode='real',
                devices='false',navigation='false',environment_config='real.yaml'))
            self.assertEqual(len(actions),1)
            self.assertEqual(actions[0].kwargs['package'],'harvest_robot')
            self.assertFalse(actions[0].kwargs['parameters'][0]['use_sim_time'])
    def test_harvest_only_bringup_and_real_rejected(self):
        actions=helper.expand(helper.load('farm_sim_runtime','harvest.launch.py',self.args))
        self.assertFalse(any(isinstance(a,helper.Process) for a in actions))
        names=[a.kwargs.get('executable') for a in actions if isinstance(a,helper.Node)]
        self.assertNotIn('rviz2',names);self.assertNotIn('clock_relay',names)
        with self.assertRaisesRegex(RuntimeError,'미구현'):
            helper.load('farm_sim_runtime','harvest.launch.py',dict(self.args,mode='real'))

if __name__=='__main__':unittest.main()
