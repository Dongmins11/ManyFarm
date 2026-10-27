"""가상 기구는 현재 세션의 유효 정렬 증거와 같은 task만 허용한다."""
import threading
import time
import unittest
from types import SimpleNamespace
from farm_sim_devices.mechanical_ros import MechanicalRosServer
from farm_interfaces.action import MechanicalOperation
from rclpy.action import GoalResponse

class VirtualMechanicalTests(unittest.TestCase):
    def setUp(self):
        self.s=MechanicalRosServer.__new__(MechanicalRosServer)
        self.s.lock=threading.RLock();self.s.session=None;self.s.proof=None
        self.s.busy=False;self.s.task=None;self.s.lid_open=False;self.s.received=0.
        self.now=10.
        self.s.node=SimpleNamespace(get_clock=lambda:SimpleNamespace(now=lambda:SimpleNamespace(nanoseconds=round(self.now*1e9))),
            get_logger=lambda:SimpleNamespace(info=lambda message:None))
        self.proof=dict(sim_time_s=10.,hold_pass=True,coverage=.721)
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

if __name__=='__main__':unittest.main()
