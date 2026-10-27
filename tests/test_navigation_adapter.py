"""실제 ROS 타입을 import하지만 노드/액션/모터를 실행하지 않는 어댑터 시험."""
import unittest
from types import SimpleNamespace as S
import numpy as np
from transport_robot.navigation_adapter import TransportNavigator
from transport_robot.sorter_approach import MarkerHandoff
from farm_navigation.navigation_types import NavigationSettings

class Adapter(unittest.TestCase):
    def make(self, x=0., handoff=False):
        calls=[]
        matrix=np.eye(4);matrix[0,3]=x
        def execute(*args):
            calls.append('execute')
            if handoff:raise MarkerHandoff('test')
            return 4
        def stopped(check):calls.append('stop_confirmed');return 123
        client=S(has_goal=False,execute=execute,cancel=lambda:calls.append('cancel'))
        poses=S(lookup=lambda *a:matrix,current=lambda check:matrix)
        motion=S(wait_stopped=stopped,stationary_now=lambda:True)
        n=TransportNavigator(S(),NavigationSettings(),client,poses,motion,lambda:None)
        return n,calls
    def test_success_requires_stopped_pose(self):
        n,c=self.make();result=n.navigate((0.,0.),0.)
        self.assertEqual(c,['execute','stop_confirmed']);self.assertTrue(result.measurement['accepted'])
    def test_transport_retains_strict_arrival(self):
        n,c=self.make(x=.5)
        with self.assertRaisesRegex(RuntimeError,'도착 허용오차'):n.navigate((0.,0.),0.)
        self.assertEqual(n.status.phase,'INTERRUPTED')
        with self.assertRaisesRegex(RuntimeError,'이전 이동'):n.navigate((0.,0.),0.)
        n.cancel_nav();self.assertEqual(c[-2:],['cancel','stop_confirmed'])
    def test_marker_handoff_propagates_then_cancels_and_stops(self):
        n,c=self.make(handoff=True)
        with self.assertRaises(MarkerHandoff):n.navigate((0.,0.),0.)
        self.assertEqual(c,['execute'])
        n.cancel_nav();self.assertEqual(c,['execute','cancel','stop_confirmed'])
if __name__=='__main__':unittest.main()
