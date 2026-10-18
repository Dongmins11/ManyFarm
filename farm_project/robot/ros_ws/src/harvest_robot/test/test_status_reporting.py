"""실제 Status 발행 메서드의 값·타이머·오래된 관측 처리를 모의 ROS로 검사."""
import importlib.util
from pathlib import Path
from types import SimpleNamespace as S
import threading
import unittest
from unittest.mock import patch


def status_message():
    return S(pose=S(position=S(x=0.,y=0.,z=0.),yaw=0.))


class FakeClient:
    def __init__(self,*a,**k):pass
    def server_is_ready(self):return True
    def destroy(self):pass


class Buffer:
    def __init__(self):self.stamp=9
    def lookup_transform(self,*args):
        return S(header=S(stamp=S(sec=self.stamp,nanosec=0)),
            transform=S(translation=S(x=1.2,y=-2.,z=0.),rotation=S(x=0.,y=0.,z=0.,w=1.)))


class StatusTests(unittest.TestCase):
    def setUp(self):
        modules={'rclpy.clock':S(Clock=lambda **k:S(),ClockType=S(STEADY_TIME=1)),
            'rclpy.time':S(Time=lambda:S()),'rclpy.action':S(ActionClient=FakeClient),
            'rclpy.callback_groups':S(MutuallyExclusiveCallbackGroup=lambda:S()),
            'rclpy.qos':S(qos_profile_sensor_data=1),
            'tf2_ros':S(Buffer=Buffer,TransformListener=lambda *a:S(unregister=lambda:None)),
            'nav2_msgs.action':S(FollowPath=object),'sensor_msgs.msg':S(BatteryState=object),
            'farm_interfaces.msg':S(RobotStatus=status_message)}
        spec=importlib.util.spec_from_file_location('status_under_test',Path(__file__).parents[1]/'harvest_robot/status.py')
        module=importlib.util.module_from_spec(spec)
        with patch.dict('sys.modules',modules):spec.loader.exec_module(module)
        self.sent=[];self.periods=[]
        self.node=S(config={'robot_id':'harvest_01'},lock=threading.Lock(),busy=False,blocked=False,
            transfer=None,handoff=S(current=None),
            stopping=False,active_goal=None,get_clock=lambda:S(now=lambda:S(nanoseconds=10_000_000_000)),
            create_publisher=lambda *a:S(publish=self.sent.append),create_subscription=lambda *a,**k:S(),
            create_timer=lambda period,*a,**k:self.periods.append(period),destroy_timer=lambda *a:None)
        self.reporter=module.HarvestStatus(self.node,S(follow_action='follow_path',map_frame='map',base_frame='base_footprint',tf_max_age_s=2.),dict(map_id='farm_map_v1',battery_topic='battery_state'))

    def test_one_hz_sequence_and_real_pose(self):
        self.reporter.on_battery(S(percentage=.82));self.reporter.publish();self.reporter.publish()
        a,b=self.sent
        self.assertEqual(self.periods,[1.0]);self.assertEqual((a.sequence,b.sequence),(1,2))
        self.assertEqual(a.boot_id,b.boot_id);self.assertTrue(a.boot_id)
        self.assertEqual((a.pose.position.x,a.pose.position.y),(1.2,-2.))
        self.assertEqual(a.battery_percent,82.);self.assertTrue(a.ready)
        self.assertFalse(a.transfer_required);self.assertEqual(a.loaded_count,0)

    def test_task_and_unknown_battery_not_claimed_measured(self):
        self.node.busy=True;self.node.active_goal=S(request=S(harvest_task=S(task_id='H1')))
        self.reporter.publish();a=self.sent[-1]
        self.assertEqual((a.state,a.current_task_id),('NAVIGATION_MOVE','H1'))
        self.assertFalse(a.ready);self.assertEqual(a.error_code,'BATTERY_UNAVAILABLE')
        self.assertIn('미측정',a.error_message)

    def test_stale_pose_not_ready_and_no_motion_change(self):
        self.reporter.buffer.stamp=1;self.reporter.publish();a=self.sent[-1]
        self.assertFalse(a.ready);self.assertEqual(a.error_code,'POSE_UNAVAILABLE')
        self.assertFalse(self.node.blocked)

    def test_cancel_unconfirmed_not_ready(self):
        self.node.blocked=True;self.reporter.publish();a=self.sent[-1]
        self.assertFalse(a.ready);self.assertEqual(a.state,'ERROR')
        self.assertEqual(a.error_code,'CANCEL_UNCONFIRMED')

    def test_return_and_transfer_preserve_task_and_load_status(self):
        self.node.handoff.current=('return','R1')
        self.reporter.publish()
        a=self.sent[-1]
        self.assertEqual((a.state,a.current_task_id,a.ready),('RETURNING','R1',False))
        self.node.handoff.current=('transfer','T1')
        self.node.transfer=S(load_topic='/load',snapshot=lambda:dict(task_id='T1',
            phase='WAIT_DOCK_STABLE',loaded_count=4,transfer_required=True,error=''))
        self.reporter.publish()
        a=self.sent[-1]
        self.assertEqual((a.state,a.current_task_id),('WAIT_DOCK_STABLE','T1'))
        self.assertEqual(a.loaded_count,4)
        self.assertTrue(a.transfer_required)
        self.assertFalse(a.ready)


if __name__=='__main__':unittest.main()
