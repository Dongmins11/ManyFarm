"""TF 대기 중 정지·취소 및 기존 제한시간 정책을 검증한다."""
import unittest
from farm_navigation.tf_recovery import run_with_tf_recovery, Nav2TFError

class TFWaitTests(unittest.TestCase):
    def run_case(self,forever=True,cancel=False,other=False):
        now=[0.];calls=[0];stops=[];waits=[]
        def execute():
            calls[0]+=1
            if other:raise ValueError('other')
            if calls[0]==1:raise Nav2TFError('TF')
            return 4
        def check():
            if cancel and now[0]>=.15:raise RuntimeError('cancel')
        def sleep(dt):now[0]+=dt
        result=run_with_tf_recovery(execute,lambda:now[0]>=.3,
            lambda:stops.append(now[0]),check,lambda:0.,.1,lambda _:None,
            clock=lambda:now[0],sleep=sleep,wait_forever=forever,waiting=waits.append)
        return result,calls,stops,waits
    def test_persistent_wait_resumes_same_execution_after_timeout(self):
        result,calls,stops,waits=self.run_case()
        self.assertEqual(result,4);self.assertEqual(calls,[2])
        self.assertGreater(len(stops),3);self.assertEqual(waits,[True,False])
    def test_default_still_times_out(self):
        with self.assertRaises(TimeoutError):self.run_case(forever=False)
    def test_cancel_propagates(self):
        with self.assertRaisesRegex(RuntimeError,'cancel'):self.run_case(cancel=True)
    def test_non_tf_error_is_not_retried(self):
        with self.assertRaisesRegex(ValueError,'other'):self.run_case(other=True)
if __name__=='__main__':unittest.main()
