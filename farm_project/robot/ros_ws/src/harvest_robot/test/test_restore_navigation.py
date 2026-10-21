"""복귀 완료 판정과 기존 Navigator의 연결 검사. 실제 ROS 실행은 별도다."""
import math
import unittest
from types import SimpleNamespace as NS
import numpy as np
from builtin_interfaces.msg import Time
from farm_navigation.navigator import Navigator
from farm_navigation.navigation_types import NavigationSettings
from farm_navigation.transfer_arc import ArcSpec
from harvest_robot.transfer_restore import RestoreReference


class RestoreNavigationTests(unittest.TestCase):
    def fixture(self, *, x=2., yaw=0., stop_failure=False, tf_failure=False):
        self.events=[]
        ref=RestoreReference('farm','w','session','map','odom','base_footprint',10,
                             (2.,3.),(1.,0.),(0.,0.,0.),ArcSpec())
        def lookup(target,source,stamp,check):
            self.events.append('map_at_stop')
            self.assertEqual((target,source,stamp),('map','base_footprint',123))
            if tf_failure:raise RuntimeError('missing TF')
            m=np.eye(4);m[0,3]=x;m[1,3]=3.
            m[:2,:2]=[[math.cos(yaw),-math.sin(yaw)],[math.sin(yaw),math.cos(yaw)]]
            return m
        def stopped(check):
            self.events.append('stopped')
            if stop_failure:raise RuntimeError('not stopped')
            return 123
        def execute(*args):self.events.append('goal');return 4
        client=NS(has_goal=False,execute=execute,cancel=lambda:self.events.append('cancel'))
        node=NS(get_clock=lambda:NS(now=lambda:NS(to_msg=lambda:Time())))
        validator=ref.arrival_validator(NS(lookup=lookup),map_id='farm',window_id='w',session_id='session')
        nav=Navigator(node,NavigationSettings(mode='follow_path',map_frame='odom'),client,None,
                      NS(wait_stopped=stopped),lambda:None,explicit_routes=True,
                      stop_output=lambda:self.events.append('zero'),arrival_validator=validator)
        return nav,ref.return_arc()

    def test_success_after_stop_and_map_check(self):
        nav,route=self.fixture()
        result=nav.navigate(route.points[-1],route.headings[-1],route_plan=route)
        self.assertTrue(result.measurement['accepted'])
        self.assertEqual(self.events,['goal','zero','stopped','map_at_stop'])

    def test_position_failure_is_not_arrived(self):
        nav,route=self.fixture(x=2.021)
        with self.assertRaisesRegex(RuntimeError,'목표 오차'):
            nav.navigate(route.points[-1],route.headings[-1],route_plan=route)
        self.assertEqual(nav.status.phase,'INTERRUPTED')
        nav.cancel_nav();self.assertEqual(self.events[-3:],['zero','cancel','stopped'])

    def test_heading_failure_is_not_arrived(self):
        nav,route=self.fixture(yaw=math.radians(1.01))
        with self.assertRaisesRegex(RuntimeError,'목표 오차'):
            nav.navigate(route.points[-1],route.headings[-1],route_plan=route)
        self.assertEqual(nav.status.phase,'INTERRUPTED')

    def test_no_pose_check_before_stopped(self):
        nav,route=self.fixture(stop_failure=True)
        with self.assertRaisesRegex(RuntimeError,'not stopped'):
            nav.navigate(route.points[-1],route.headings[-1],route_plan=route)
        self.assertNotIn('map_at_stop',self.events)

    def test_tf_failure_is_not_arrived(self):
        nav,route=self.fixture(tf_failure=True)
        with self.assertRaisesRegex(RuntimeError,'missing TF'):
            nav.navigate(route.points[-1],route.headings[-1],route_plan=route)
        self.assertEqual(nav.status.phase,'INTERRUPTED')


if __name__=='__main__':unittest.main()
