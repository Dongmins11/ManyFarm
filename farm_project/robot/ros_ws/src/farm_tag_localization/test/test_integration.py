"""ROS 없는 계약 시험. 실물/ROS 실행 성공을 대신하지 않는다."""
import ast
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace as NS
import hashlib
import json
import sys
import tempfile
import unittest
import numpy as np
import yaml
ROOT = Path(__file__).resolve().parents[5]
PKG = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PKG))
sys.path.insert(0, str(ROOT/'robot/ros_ws/src/harvest_robot'))
from farm_tag_localization.runtime import Lease, Journal, time_valid, validate_binding, load_observer
from farm_tag_localization.tag_adapter import correction, transported, observe
from harvest_robot.mission import HarvestMission, MissionCanceled


class Contracts(unittest.TestCase):
    def message(self, **changes):
        d=dict(robot_id='harvest_01',map_id='map1',token='task1',sequence=1,enabled=True,
               begin_ns=1_000_000_000,stamp_ns=1_000_000_000)
        d.update(changes)
        return d

    def test_lease_expiry_and_wrong_identity(self):
        lease=Lease('harvest_01','map1')
        lease.update(self.message(map_id='other'),1_000_000_000,0.)
        self.assertFalse(lease.active(0.))
        lease.update(self.message(),1_000_000_000,0.)
        self.assertTrue(lease.active(1.))
        self.assertFalse(lease.active(2.))
        self.assertFalse(lease.accepts('task1',999_999_999,1.))

    def test_stop_reordered_packets_and_new_task(self):
        lease=Lease('harvest_01','map1')
        lease.update(self.message(),1_000_000_000,0.)
        lease.update(self.message(sequence=3,enabled=False),1_000_000_000,.2)
        lease.update(self.message(sequence=2),1_000_000_000,.3)
        self.assertFalse(lease.active(.3))
        lease.update(self.message(sequence=4),1_000_000_000,.4)
        self.assertFalse(lease.active(.4))
        lease.update(self.message(token='task2'),1_000_000_000,.5)
        self.assertTrue(lease.active(.5))
        self.assertFalse(lease.accepts('task1',1_000_000_000,.5))

    def test_stale_control_is_not_replayed(self):
        lease=Lease('harvest_01','map1')
        lease.update(self.message(),4_000_000_000,0.)
        self.assertFalse(lease.active(0.))

    def test_delayed_compute_rechecks_send_time(self):
        self.assertTrue(time_valid(1_000_000_000,1_100_000_000,1_200_000_000))
        self.assertFalse(time_valid(1_000_000_000,1_100_000_000,2_500_000_000))
        self.assertFalse(time_valid(1_000_000_000,1_100_000_000,999_999_999))

    def test_position_heading_and_transport_preserved(self):
        target,delta=correction([0,0,0],[.1,.1,.1])
        np.testing.assert_allclose(target,[.05,.05,.05])
        target,_=correction([0,0,0],[.4,0,.4])
        self.assertAlmostEqual(target[0],.08)
        self.assertAlmostEqual(target[2],np.deg2rad(5))
        np.testing.assert_allclose(transported([1,2,0],[0,0,0],[.1,0,0]),[1.1,2,0])
        with self.assertRaises(ValueError):correction([0,0,0],[1,0,0])

    def test_partial_journal_and_no_old_frame_replay(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'settings.json').write_text(json.dumps(dict(calibration_sha256='hash')))
            path=root/'detections.jsonl';path.write_text('{"old":true}\n')
            journal=Journal(root,'sha256:hash')
            self.assertIsNone(journal.latest())
            with path.open('a') as f:f.write('{"new":')
            self.assertIsNone(journal.latest())
            with path.open('a') as f:f.write('true}\n')
            self.assertEqual(journal.latest(),{'new':True})
            journal.close()

    def test_map_change_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'map.yaml').write_text('image: map.pgm\n');(root/'map.pgm').write_bytes(b'old')
            cfg=dict(configured=True,robot_id='h',map_id='m',map_yaml_sha256=hashlib.sha256((root/'map.yaml').read_bytes()).hexdigest(),map_image_sha256=hashlib.sha256(b'old').hexdigest())
            env=dict(robot_id='h',map_id='m',map_yaml='map.yaml')
            validate_binding(cfg,env,root)
            (root/'map.pgm').write_bytes(b'new')
            with self.assertRaises(ValueError):validate_binding(cfg,env,root)

    def test_reference_can_construct_geometry_without_old_estimator(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'test.yaml'
            cfg=yaml.safe_load((ROOT/'robot/config/localization/harvest_real.yaml').read_text());cfg['configured']=True
            p.write_text(yaml.safe_dump(cfg));_,observer=load_observer(str(p),str(ROOT),'test')
            record=dict(source_stamp_ns=1,frame_id='apriltag_camera_optical_frame',detections=[])
            candidate,result=observe(observer,record)
            self.assertIsNone(candidate)
            self.assertEqual(result['all_packets'],[])

    def test_mission_off_and_failure_cleanup(self):
        @dataclass
        class Result:
            stamp_ns:int=1
        for enabled in (False,True):
            for error in (None,RuntimeError('nav failure'),MissionCanceled('cancel')):
                events=[]
                def navigate(*args):
                    events.append('navigate')
                    if error:raise error
                    return Result()
                control=NS(begin=lambda:events.append('begin'),end=lambda:events.append('end')) if enabled else None
                node=NS(check=lambda:None,tag_control=control,navigator=NS(preflight_navigation=lambda:None,navigate=navigate,cancel_nav=lambda:events.append('cancel')),blocked=False)
                goal=NS(harvest_task=NS(goal_pose=NS(position=NS(x=1,y=2),yaw=0)))
                if error:
                    with self.assertRaises(type(error)):HarvestMission(node,goal).run()
                else:self.assertEqual(HarvestMission(node,goal).run(),dict(stamp_ns=1))
                self.assertEqual('begin' in events,enabled)
                if enabled:self.assertEqual(events[-1],'end')
                self.assertEqual('cancel' in events,error is not None)

    def test_node_has_no_motion_or_tf_publishers(self):
        source=(PKG/'farm_tag_localization/node.py').read_text()
        tree=ast.parse(source)
        publishers=[n for n in ast.walk(tree) if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and n.func.attr=='create_publisher']
        self.assertEqual(len(publishers),1)
        self.assertEqual(publishers[0].args[1].value,'initialpose')
        self.assertNotIn('TransformBroadcaster',source)
        self.assertNotIn('SetParameters',source)
        self.assertNotIn('ActionClient',source)

if __name__=='__main__':unittest.main()
