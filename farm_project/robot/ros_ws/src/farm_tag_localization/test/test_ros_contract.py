"""실제 _send 메서드의 경계를 가짜 ROS 객체로 검증한다. ROS 전송 시험은 아님."""
from pathlib import Path
from types import SimpleNamespace as NS, ModuleType
from unittest.mock import patch
import importlib.util
import sys
import unittest
import numpy as np
PKG=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(PKG))
from farm_tag_localization.runtime import Lease


def message():
    return NS(header=NS(frame_id='',stamp=None),pose=NS(pose=NS(position=NS(x=0.,y=0.),orientation=NS(z=0.,w=1.)),covariance=[]))


def module(name, **attrs):
    m=ModuleType(name)
    for k,v in attrs.items():setattr(m,k,v)
    return m


def load_node():
    mocks={'rclpy':module('rclpy'), 'rclpy.node':module('rclpy.node',Node=object),
      'rclpy.time':module('rclpy.time',Time=lambda **kw:NS(**kw)),
      'rclpy.qos':module('rclpy.qos',qos_profile_sensor_data=object()),
      'geometry_msgs.msg':module('geometry_msgs.msg',PoseWithCovarianceStamped=message),
      'std_msgs.msg':module('std_msgs.msg',String=message),
      'rcl_interfaces.srv':module('rcl_interfaces.srv',GetParameters=object),
      'tf2_ros':module('tf2_ros',Buffer=object,TransformListener=object)}
    with patch.dict(sys.modules,mocks):
        spec=importlib.util.spec_from_file_location('farm_tag_localization._test_node',PKG/'farm_tag_localization/node.py')
        m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
    return m


class SendTests(unittest.TestCase):
    def setUp(self):
        self.module=load_node();self.adapter=self.module.TagAdapter.__new__(self.module.TagAdapter)
        a=self.adapter;self.sent=[];self.logs=[]
        a._lease=Lease('h','m');a._lease.token='task';a._lease.begin_ns=1;a._lease.deadline=float('inf')
        a._config=dict(odom_frame='odom',base_frame='base',map_frame='map')
        a._amcl_owns_tf=True;a._owner_checked=self.module.time.monotonic()
        a._publisher=NS(publish=self.sent.append,get_subscription_count=lambda:1)
        a._log=lambda kind,**kw:self.logs.append((kind,kw))
        a._count=0;a.get_logger=lambda:NS(info=lambda s:None)
        a.get_clock=lambda:NS(now=lambda:NS(nanoseconds=1_200_000_000))
        def transform(x,ns):
            return NS(header=NS(stamp=NS(sec=1,nanosec=ns)),transform=NS(translation=NS(x=x,y=0.),rotation=NS(x=0.,y=0.,z=0.,w=1.)))
        a._buffer=NS(lookup_transform=lambda target,source,t: transform(0.,100_000_000) if target=='map' else (transform(0.,0) if hasattr(t,'nanoseconds') else transform(.1,100_000_000)))
        self.candidate=dict(q=[0.,0.,0.],p=np.eye(3)*.01)
        self.record=dict(source_stamp_ns=1_000_000_000,detections=[dict(id=101)])

    def test_send_compensates_odom_and_preserves_stamp(self):
        self.adapter._send(self.candidate,self.record,'task',.01)
        self.assertEqual(len(self.sent),1)
        self.assertAlmostEqual(self.sent[0].pose.pose.position.x,.05)
        self.assertEqual(self.sent[0].header.stamp.nanosec,100_000_000)
        self.assertEqual(self.logs[-1][0],'tag_correction_requested')

    def test_scan_sync_keeps_geometry_and_adds_task_contract(self):
        import json
        self.adapter._config.update(correction_transport='scan_sync',robot_id='h',map_id='m')
        self.adapter._session='session'
        self.adapter._send(self.candidate,self.record,'task',.01)
        data=json.loads(self.sent[0].data)
        self.assertEqual(data['token'],'task')
        self.assertEqual(data['producer_session'],'session')
        self.assertEqual(data['pose_stamp_ns'],1_100_000_000)
        self.assertEqual(data['source_stamp_ns'],1_000_000_000)
        self.assertEqual(data['sequence'],1)
        self.assertAlmostEqual(data['pose'][0],.05)

    def test_quality_reference_requires_actual_applied_event_in_current_lease(self):
        import json
        a=self.adapter
        a._config.update(robot_id='h',map_id='m')
        a._session='session'
        event=dict(kind='tag_correction_queued',robot_id='h',map_id='m',producer_session='session',
            token='task',source_stamp_ns=1_000_000_000,scan_stamp_ns=1_100_000_000,
            odom_anchor=[.1,0,0],observation_kind='multi_tag',sequence=1)
        a._on_receiver_event(NS(data=json.dumps(event)))
        self.assertIsNone(getattr(a,'_last_multi_applied',None))
        event['kind']='tag_correction_applied'
        a._on_receiver_event(NS(data=json.dumps(dict(event,token='old'))))
        self.assertIsNone(getattr(a,'_last_multi_applied',None))
        a._on_receiver_event(NS(data=json.dumps(event)))
        self.assertEqual(a._last_multi_applied['token'],'task')

    def test_recent_applied_multi_lowers_single_step(self):
        self.adapter._last_multi_applied = dict(token='task',scan_stamp_ns=1_000_000_000,odom_anchor=[.1,0,0])
        self.adapter._send(self.candidate,self.record,'task',.01)
        self.assertAlmostEqual(self.sent[0].pose.pose.position.x,.01)
        self.assertEqual(self.logs[-1][1]['correction_gain'],.1)

    def test_approach_requires_multi_and_proximity(self):
        self.adapter._lease.approach_pose = [.2,0.,0.]
        self.adapter._send(self.candidate,self.record,'task',.01)
        self.assertEqual(self.sent,[])
        multi=dict(self.candidate, observation_kind='multi_tag')
        self.adapter._lease.approach_pose = [5.,0.,0.]
        self.adapter._send(multi,self.record,'task',.01)
        self.assertEqual(self.sent,[])
        self.adapter._lease.approach_pose = [.2,0.,0.]
        self.adapter._send(multi,self.record,'task',.01)
        self.assertEqual(len(self.sent),1)

    def test_expired_compute_cannot_publish(self):
        self.adapter.get_clock=lambda:NS(now=lambda:NS(nanoseconds=3_000_000_000))
        self.adapter._send(self.candidate,self.record,'task',2.)
        self.assertEqual(self.sent,[])
        self.assertEqual(self.logs[-1][0],'timing_skip')

    def test_task_ended_during_compute_cannot_publish(self):
        self.adapter._lease.deadline=0.
        self.adapter._send(self.candidate,self.record,'task',.01)
        self.assertEqual(self.sent,[])

    def test_wrong_tf_owner_cannot_publish(self):
        self.adapter._amcl_owns_tf=False
        self.adapter._send(self.candidate,self.record,'task',.01)
        self.assertEqual(self.sent,[])

    def test_no_amcl_subscriber_cannot_publish(self):
        self.adapter._publisher.get_subscription_count=lambda:0
        self.adapter._send(self.candidate,self.record,'task',.01)
        self.assertEqual(self.sent,[])

if __name__=='__main__':unittest.main()
