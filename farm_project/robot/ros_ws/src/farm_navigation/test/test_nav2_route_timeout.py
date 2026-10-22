from types import SimpleNamespace as NS
from unittest.mock import Mock,patch
import unittest
from geometry_msgs.msg import PoseStamped
from nav_msgs.msg import Path
from farm_navigation.nav2_client import Nav2Client
from farm_navigation.navigation_types import NavigationSettings


def route(points):
 p=Path()
 for x,y in points:
  pose=PoseStamped();pose.pose.position.x=float(x);pose.pose.position.y=float(y);p.poses.append(pose)
 return p


class RouteBudgetTests(unittest.TestCase):
 def client(self,speed=.1,**settings):
  c=Nav2Client.__new__(Nav2Client);c._settings=NavigationSettings(mode='follow_path',**settings);c._nominal_linear_speed_mps=speed;return c

 def test_failed_sec10_route_gets_sufficient_finite_budget(self):
  # 27.535m 합성 경로: 실패한 SEC10과 같은 거리/속도 조건.
  points=[(0.,0.),(20.,0.),(20.,7.534978759689984)]
  self.assertEqual(self.client()._execution_timeout(route(points)),611.)

 def test_length_speed_and_existing_floor(self):
  c=self.client()
  for length,expected in [(1.,300.),(10.,300.),(27.5,610.),(50.,1060.)]:
   self.assertEqual(c._execution_timeout(route([(0,0),(length,0)])),expected)
  c._nominal_linear_speed_mps=.2
  self.assertEqual(c._execution_timeout(route([(0,0),(27.5,0)])),335.)
  self.assertEqual(self.client(goal_timeout_s=900.)._execution_timeout(route([(0,0),(27.5,0)])),900.)

 def test_polyline_not_straight_line_distance(self):
  self.assertEqual(self.client()._execution_timeout(route([(0,0),(20,0),(20,20),(0,20)])),1260.)

 def test_unknown_speed_or_unknown_plan_keeps_previous_budget(self):
  self.assertEqual(self.client(None)._execution_timeout(route([(0,0),(100,0)])),300.)
  self.assertEqual(self.client()._execution_timeout(None),300.)
  c=self.client();c._settings=NavigationSettings(mode='navigate_to_pose')
  self.assertEqual(c._execution_timeout(route([(0,0),(100,0)])),300.)

 def test_preflight_reads_speed_in_existing_request(self):
  c=self.client(None);c._follow=NS(server_is_ready=lambda:True);c._parameters=NS(service_is_ready=lambda:True)
  c._read_parameters=Mock(side_effect=[dict(goal_checker_plugins=['goal_checker'],controller_plugins=['FollowPath'],progress_checker_plugins=['progress_checker'],**{'FollowPath.desired_linear_vel':.1}),{}])
  with patch('farm_navigation.nav2_client.validate_goal_checkers',return_value=[]):c.preflight(lambda:None)
  self.assertEqual(c._nominal_linear_speed_mps,.1)
  self.assertEqual(c._read_parameters.call_count,2)
  self.assertIn('FollowPath.desired_linear_vel',c._read_parameters.call_args_list[0].args[0])
