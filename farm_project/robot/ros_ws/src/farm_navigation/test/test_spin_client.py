"""ROS 없이 Spin 소유 Goal의 승인/실패/취소 경계를 검증한다."""
from concurrent.futures import Future
from pathlib import Path
import sys
from types import SimpleNamespace as S
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from farm_navigation.spin_client import SpinClient


def done(value):
    result=Future();result.set_result(value);return result


def terminal(status=4,code=0):
    return S(status=status,result=S(error_code=code))


class SpinTests(unittest.TestCase):
    def fixture(self, result=None, pending=None):
        result=done(terminal()) if result is None else result
        goal_id=S(uuid=[1]*16)
        handle=S(accepted=True,goal_id=goal_id,get_result_async=lambda:result)
        self.cancel_calls=[]
        def cancel():
            self.cancel_calls.append(True)
            if not result.done():result.set_result(terminal(5))
            return done(S(return_code=0,goals_canceling=[S(goal_id=goal_id)]))
        handle.cancel_goal_async=cancel
        raw=S(server_is_ready=lambda:True,destroy=lambda:None)
        self.sent=[]
        def send(goal):
            self.sent.append(goal)
            return done(handle) if pending is None else pending
        raw.send_goal_async=send
        client=SpinClient(None,'test_only/spin',S(response_timeout_s=.002,cancel_timeout_s=.002),
            client=raw,goal_factory=lambda:S(time_allowance=S()))
        return client,raw,handle

    def test_signed_relative_angle_and_duration(self):
        client,_,_=self.fixture()
        for angle in (1.5707963267948966,-1.5707963267948966):client.execute(angle,2.25,lambda:None)
        self.assertEqual([g.target_yaw for g in self.sent],[1.5707963267948966,-1.5707963267948966])
        self.assertEqual((self.sent[0].time_allowance.sec,self.sent[0].time_allowance.nanosec),(2,250000000))
        self.assertFalse(client.has_goal)

    def test_missing_server_sends_no_motion(self):
        client,raw,_=self.fixture();raw.server_is_ready=lambda:False
        with self.assertRaises(RuntimeError):client.execute(1.,1.,lambda:None)
        self.assertFalse(self.sent)

    def test_rejection_and_collision_are_not_success(self):
        client,_,handle=self.fixture();handle.accepted=False
        with self.assertRaises(RuntimeError):client.execute(1.,1.,lambda:None)
        self.assertFalse(client.has_goal)
        client,_,_=self.fixture(done(terminal(6,703)))
        with self.assertRaisesRegex(RuntimeError,'703'):client.execute(1.,1.,lambda:None)
        self.assertFalse(client.has_goal)

    def test_timeout_late_acceptance_cancels_only_own_goal(self):
        pending=Future();result=Future();client,_,handle=self.fixture(result,pending)
        with self.assertRaises(TimeoutError):client.execute(1.,1.,lambda:None)
        self.assertTrue(client.has_goal)
        pending.set_result(handle);client.cancel()
        self.assertEqual(len(self.cancel_calls),1)
        self.assertFalse(client.has_goal)

    def test_ack_without_terminal_retains_goal(self):
        result=Future();client,_,handle=self.fixture(result)
        def interrupted():
            if self.sent:raise RuntimeError('interrupt')
        with self.assertRaises(RuntimeError):client.execute(1.,1.,interrupted)
        handle.cancel_goal_async=lambda:done(S(return_code=0,goals_canceling=[S(goal_id=handle.goal_id)]))
        with self.assertRaises(TimeoutError):client.cancel()
        self.assertTrue(client.has_goal)
        with self.assertRaises(RuntimeError):client.execute(1.,1.,lambda:None)

    def test_wrong_goal_ack_is_not_cancellation_confirmation(self):
        result=Future();client,_,handle=self.fixture(result)
        def interrupted():
            if self.sent:raise RuntimeError('interrupt')
        with self.assertRaises(RuntimeError):client.execute(1.,1.,interrupted)
        def cancel():
            result.set_result(terminal(5))
            return done(S(return_code=0,goals_canceling=[S(goal_id=S(uuid=[2]*16))]))
        handle.cancel_goal_async=cancel
        with self.assertRaises(RuntimeError):client.cancel()
        self.assertTrue(client.has_goal)

    def test_invalid_arguments_send_nothing(self):
        client,_,_=self.fixture()
        for angle,allowance in ((0,1),(float('nan'),1),(4,1),(1,0),(True,1)):
            with self.assertRaises(ValueError):client.execute(angle,allowance,lambda:None)
        self.assertFalse(self.sent)


if __name__=='__main__':unittest.main()
