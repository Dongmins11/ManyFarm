"""가상 기구는 현재 세션의 유효 정렬 증거와 같은 task만 허용한다."""
import threading
import time
import unittest
from types import SimpleNamespace
from farm_sim_devices.mechanical_ros import MechanicalRosServer
from farm_interfaces.action import MechanicalOperation
from rclpy.action import GoalResponse
from std_srvs.srv import Trigger

class VirtualMechanicalTests(unittest.TestCase):
    def setUp(self):
        self.s=MechanicalRosServer.__new__(MechanicalRosServer)
        self.s.lock=threading.RLock();self.s.session=None;self.s.proof=None
        self.s.busy=False;self.s.task=None;self.s.lid_open=False;self.s.received=0.
        self.now=10.
        self.s.node=SimpleNamespace(get_clock=lambda:SimpleNamespace(now=lambda:SimpleNamespace(nanoseconds=round(self.now*1e9))),
            get_logger=lambda:SimpleNamespace(info=lambda message:None,warning=lambda message:None))
        self.proof=dict(sim_time_s=10.,hold_pass=True,coverage=.721,wheel_stopped=True,world_stopped=True)
        self.s.observe('session1',self.proof)
    def request(self,operation='LID_OPEN',task='task1'):
        return MechanicalOperation.Goal(task_id=task,operation=operation)
    def execute(self,q,cancel=False):
        terminal=[]
        h=SimpleNamespace(request=q,is_cancel_requested=cancel,canceled=lambda:terminal.append('CANCELED'),
            abort=lambda:terminal.append('ABORTED'),succeed=lambda:terminal.append('SUCCESS'))
        return self.s.execute(h),terminal
    def test_open_close_and_unknown_count(self):
        q=self.request();self.assertEqual(self.s.goal(q),GoalResponse.ACCEPT)
        r,terminal=self.execute(q)
        self.assertEqual(terminal,['SUCCESS']);self.assertFalse(r.count_valid);self.assertFalse(r.safe_to_clear)
        self.assertEqual(self.s.goal(self.request('LID_CLOSE','other')),GoalResponse.REJECT)
        q=self.request('LID_CLOSE');self.assertEqual(self.s.goal(q),GoalResponse.ACCEPT)
        r,_=self.execute(q);self.assertTrue(r.safe_to_clear);self.assertFalse(r.count_valid)
    def test_unsupported_and_unaligned_rejected(self):
        self.assertEqual(self.s.goal(self.request('UNLOAD')),GoalResponse.REJECT)
        self.proof['hold_pass']=False
        self.assertEqual(self.s.goal(self.request()),GoalResponse.REJECT)
    def test_stale_wall_or_sim_proof_rejected(self):
        self.now=10.6;self.assertFalse(self.s.ready())
        self.now=9.9;self.assertFalse(self.s.ready())
        self.now=10.;self.s.received=time.monotonic()-1.;self.assertFalse(self.s.ready())
    def test_cancel_does_not_open(self):
        q=self.request();self.s.goal(q);r,terminal=self.execute(q,True)
        self.assertEqual(terminal,['CANCELED']);self.assertFalse(r.success);self.assertFalse(self.s.lid_open)
    def test_restart_invalidates_accepted_action(self):
        q=self.request();self.s.goal(q);self.s.observe('session2',dict(self.proof))
        r,terminal=self.execute(q);self.assertEqual(terminal,['ABORTED']);self.assertFalse(r.success)
    def test_concurrent_goal_rejected(self):
        q=self.request();self.s.goal(q);self.assertEqual(self.s.goal(q),GoalResponse.REJECT)

    def test_trigger_uses_alignment_and_preserves_action_ownership(self):
        self.proof['hold_pass']=False
        self.assertFalse(self.s.open_lid(None,Trigger.Response()).success)
        self.proof['hold_pass']=True
        self.assertTrue(self.s.open_lid(None,Trigger.Response()).success)
        self.assertEqual(self.s.goal(self.request('LID_CLOSE')),GoalResponse.REJECT)
        self.assertTrue(self.s.stop_device(None,Trigger.Response()).success)
        self.assertTrue(self.s.lid_open)  # STOP은 자동 닫힘이 아니다.
        self.assertTrue(self.s.close_lid(None,Trigger.Response()).success)
        self.assertFalse(self.s.unsupported_unload(None,Trigger.Response()).success)

    def test_trigger_rejects_stale_or_busy_device(self):
        self.s.busy=True
        self.assertFalse(self.s.open_lid(None,Trigger.Response()).success)
        self.s.busy=False;self.now=11.
        self.assertFalse(self.s.open_lid(None,Trigger.Response()).success)
        self.assertFalse(self.s.stop_device(None,Trigger.Response()).success)

    def test_close_does_not_repeat_completed_transfer_alignment(self):
        self.assertTrue(self.s.open_lid(None,Trigger.Response()).success)
        self.proof.update(hold_pass=False,coverage=.719)
        self.assertFalse(self.s.open_lid(None,Trigger.Response()).success)
        self.proof['world_stopped']=False
        self.assertFalse(self.s.close_lid(None,Trigger.Response()).success)
        self.proof['world_stopped']=True
        self.assertTrue(self.s.close_lid(None,Trigger.Response()).success)
        self.assertFalse(self.s.lid_open)

if __name__=='__main__':unittest.main()
