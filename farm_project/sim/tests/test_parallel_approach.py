"""수확 평행 접근의 기하 및 공통 옵션 비활성 호환 검사."""
import json
import math
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock
import numpy as np

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'robot/ros_ws/src/farm_navigation'))
from farm_navigation.parallel_approach import select_corridor, straight_plan
from farm_navigation.route import RouteGraph
from farm_navigation.navigation_types import NavigationSettings, RoutePlan
from farm_navigation.navigator import Navigator


class ParallelApproachTests(unittest.TestCase):
    def setUp(self) -> None:
        self.graph=RouteGraph(ROOT/'sim/ros_ws/src/farm_sim_config/maps/harvest_graph.geojson')
        self.template=RoutePlan('test','hash','map',(),(),0.)

    def test_all_sections_end_parallel(self) -> None:
        self.assertEqual(len(self.graph.parallel_corridors),16)
        for c in self.graph.parallel_corridors:
            a,b=c['entry'],c['exit']
            goal=tuple((a[i]+b[i])/2 for i in range(2))
            selected=select_corridor(self.graph.parallel_corridors,goal,c['yaw'],.05)
            plan=straight_plan(self.template,selected,tuple(a),c['yaw'],goal,.02,.05)
            final=math.atan2(plan.points[-1][1]-a[1],plan.points[-1][0]-a[0])
            self.assertAlmostEqual(math.remainder(final-c['yaw'],2*math.pi),0.)
            route=self.graph.plan(tuple(a),goal,.02,.02)
            self.assertAlmostEqual(route.distance_m,math.dist(a,goal))

    def test_wrong_heading_lateral_or_passed_goal_rejected(self) -> None:
        c=self.graph.parallel_corridors[0];x,y=c['entry'];goal=(x,y-1)
        for xy,yaw in [((x,y),0.),((x+.06,y),c['yaw']),((x,y-2),c['yaw'])]:
            with self.assertRaisesRegex(RuntimeError,'RECOVERY_REQUIRED'):
                straight_plan(self.template,c,xy,yaw,goal,.02,.05)

    def test_off_lane_goal_rejected(self) -> None:
        c=self.graph.parallel_corridors[0];x,y=c['entry']
        with self.assertRaises(ValueError):
            select_corridor(self.graph.parallel_corridors,(x+.06,y-1),c['yaw'],.05)

    def test_legacy_option_default(self) -> None:
        self.assertFalse(NavigationSettings.from_mapping({}).parallel_approach)
        with self.assertRaises(ValueError):
            NavigationSettings.from_mapping({'parallel_approach':'true'})

    def make_navigator(self, drift: float = 0.) -> tuple:
        current=np.eye(4);current[0,3]=1.;current[1,3]=2.
        settled=current.copy();settled[0,3]+=drift
        poses=Mock();poses.current.return_value=current;poses.lookup.return_value=settled
        motion=Mock();motion.wait_stopped.return_value=100
        client=Mock();client.has_goal=False
        navigator=Navigator(Mock(),NavigationSettings(mode='follow_path',parallel_approach=True),
            client,poses,motion,lambda:None,self.graph)
        return navigator,client

    def test_already_arrived_remeasures_without_sending_goal(self) -> None:
        nav,client=self.make_navigator()
        result=nav.navigate((1.,2.),0.)
        self.assertTrue(result.measurement['accepted'])
        client.execute.assert_not_called()

    def test_settle_drift_does_not_fake_arrival(self) -> None:
        nav,client=self.make_navigator(.2)
        with self.assertRaisesRegex(RuntimeError,'재검사'):
            nav.navigate((1.,2.),0.)
        client.execute.assert_not_called()

    def test_entry_alignment_then_parallel_goal(self) -> None:
        c=self.graph.parallel_corridors[0]
        def pose(xy, yaw):
            matrix=np.eye(4);matrix[:2,3]=xy
            matrix[:2,:2]=[[math.cos(yaw),-math.sin(yaw)],[math.sin(yaw),math.cos(yaw)]]
            return matrix
        a,b=c['entry'],c['exit'];goal=tuple((a[i]+b[i])/2 for i in range(2))
        start=(a[0], a[1]+.4)
        poses=Mock();poses.current.return_value=pose(start,c['yaw'])
        poses.lookup.side_effect=[pose(a,c['yaw']),pose(goal,c['yaw'])]
        motion=Mock();motion.wait_stopped.return_value=100
        client=Mock();client.has_goal=False;client.execute.return_value=4
        from builtin_interfaces.msg import Time
        node=Mock();node.get_clock.return_value.now.return_value.to_msg.return_value=Time()
        nav=Navigator(node,NavigationSettings(mode='follow_path',parallel_approach=True),client,poses,motion,lambda:None,self.graph)
        result=nav.navigate(goal,c['yaw'])
        self.assertTrue(result.measurement['accepted'])
        self.assertEqual(client.execute.call_count,2)
        self.assertEqual(client.execute.call_args_list[0].args[0],tuple(a))
        self.assertEqual(client.execute.call_args_list[1].args[0],goal)



if __name__=='__main__':
    unittest.main()
