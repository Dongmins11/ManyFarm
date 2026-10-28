"""명시적 경로와 기존 주행 계약의 회귀 검사. 이동 장치는 사용하지 않는다."""
import math
import unittest
from dataclasses import replace
from types import SimpleNamespace as NS
from builtin_interfaces.msg import Time
from farm_navigation.navigation_types import RoutePlan, NavigationSettings
from farm_navigation.path_builder import build_path
from farm_navigation.navigator import Navigator
from farm_navigation.arrival import validate_goal_checkers, NavigationConfigurationError
from farm_navigation.nav2_client import Nav2Client
from farm_navigation.transfer_arc import arc_path, ArcSpec

class ExplicitNavigationTests(unittest.TestCase):
    def route(self):
        return RoutePlan('id','','odom',((0.,0.),(.1,0.)),(),.1,(0.,0.))

    def fixture(self, *, accepted=True, failure=False, stop_failure=False):
        self.events=[];self.entries=[]
        def execute(*args):
            self.events.append('goal')
            if failure:raise RuntimeError('goal failure')
            return 4
        def stopped(check):
            check();self.events.append('stopped')
            if stop_failure:raise RuntimeError('stale odom')
            return 123
        client=NS(has_goal=False,execute=execute,cancel=lambda:self.events.append('cancel'))
        node=NS(get_clock=lambda:NS(now=lambda:NS(to_msg=lambda:Time())))
        nav=Navigator(node,NavigationSettings(mode='follow_path',map_frame='odom'),client,None,
            NS(wait_stopped=stopped),lambda:None,explicit_routes=True,
            stop_output=lambda:self.events.append('zero'),
            arrival_validator=lambda stamp,check:self.validate(stamp,accepted),record=self.entries.append)
        return nav

    def validate(self,stamp,accepted):
        self.events.append('validate');self.assertEqual(stamp,123)
        return {'accepted':accepted,'final_angle_error':.03}

    def test_success_order(self):
        nav=self.fixture();result=nav.navigate((.1,0),0,route_plan=self.route())
        self.assertEqual(self.events,['goal','zero','stopped','validate'])
        self.assertTrue(result.measurement['accepted']);self.assertEqual(nav.status.phase,'ARRIVED')

    def test_failed_arrival_records_and_blocks_next(self):
        nav=self.fixture(accepted=False)
        with self.assertRaisesRegex(RuntimeError,'목표 오차'):nav.navigate((.1,0),0,route_plan=self.route())
        self.assertEqual(self.entries[0]['final_angle_error'],.03)
        with self.assertRaisesRegex(RuntimeError,'종료'):nav.navigate((.1,0),0,route_plan=self.route())
        nav.cancel_nav();self.assertEqual(self.events[-3:],['zero','cancel','stopped'])

    def test_goal_failure_closes_gate_before_cancel(self):
        nav=self.fixture(failure=True)
        with self.assertRaisesRegex(RuntimeError,'goal failure'):nav.navigate((.1,0),0,route_plan=self.route())
        self.assertEqual(self.events,['goal','zero'])
        nav.cancel_nav();self.assertEqual(self.events[-3:],['zero','cancel','stopped'])

    def test_stop_failure_not_success(self):
        nav=self.fixture(stop_failure=True)
        with self.assertRaisesRegex(RuntimeError,'stale odom'):nav.navigate((.1,0),0,route_plan=self.route())
        self.assertNotIn('validate',self.events)
        with self.assertRaisesRegex(RuntimeError,'stale odom'):nav.cancel_nav()
        with self.assertRaisesRegex(RuntimeError,'종료'):nav.navigate((.1,0),0,route_plan=self.route())

    def test_output_failure_still_cancels_owned_goal(self):
        nav=self.fixture(failure=True)
        def broken():raise RuntimeError('output failure')
        nav._stop_output=broken
        with self.assertRaisesRegex(RuntimeError,'goal failure'):nav.navigate((.1,0),0,route_plan=self.route())
        self.assertEqual(self.entries[0]['stop_output_error'],'output failure')
        with self.assertRaisesRegex(RuntimeError,'output failure'):nav.cancel_nav()
        self.assertEqual(self.events[-2:],['cancel','stopped'])
        with self.assertRaisesRegex(RuntimeError,'종료'):nav.navigate((.1,0),0,route_plan=self.route())

    def test_settling_uses_separate_check_after_execution(self):
        nav=self.fixture();seen=[]
        nav._settling_check=lambda:seen.append('settle')
        nav.navigate((.1,0),0,route_plan=self.route())
        self.assertEqual(seen,['settle'])

    def test_missing_mismatched_path_never_sends(self):
        for route in (None,replace(self.route(),frame_id='map'),replace(self.route(),points=((0,0),(.2,0)))):
            nav=self.fixture()
            with self.assertRaises(ValueError):nav.navigate((.1,0),0,route_plan=route)
            self.assertEqual(self.events,[])

    def test_arc_exact_samples_wrap_and_quaternion(self):
        for origin in ((0,0,0),(1.25,-2.2,-1.52),(0,0,3.13)):
            samples=arc_path(origin,ArcSpec())
            route=RoutePlan('a','','odom',tuple(p[:2] for p in samples),(),.2,tuple(p[2] for p in samples))
            path=build_path(route,samples[-1][2],Time(sec=12),.04)
            self.assertEqual(len(path.poses),len(samples))
            for msg,(x,y,yaw) in zip(path.poses,samples):
                self.assertEqual((msg.pose.position.x,msg.pose.position.y),(x,y))
                self.assertEqual((msg.pose.orientation.z,msg.pose.orientation.w),(math.sin(yaw/2),math.cos(yaw/2)))

    def test_bad_headings_never_sends(self):
        for route in (replace(self.route(),headings=(0.,)),replace(self.route(),headings=(0.,math.nan)),
                      replace(self.route(),headings=(0.,.2)),replace(self.route(),points=((math.nan,0),(.1,0)))):
            nav=self.fixture()
            with self.assertRaises(ValueError):nav.navigate((.1,0),0,route_plan=route)
            self.assertEqual(self.events,[])
        with self.assertRaises(ValueError):build_path(self.route(),0,Time(),reverse=True)

    def test_no_implicit_graph_fallback(self):
        with self.assertRaises(ValueError):Navigator(NS(),NavigationSettings(mode='follow_path'),NS(),NS(),NS(),lambda:None)
        nav=self.fixture()
        with self.assertRaises(ValueError):nav.plan((0,0))

class WallPreflightTests(unittest.TestCase):
    def setUp(self):
        self.config={'target_distance':.4325,'target_angle':.04276,'distance_tolerance':.005,
            'angle_tolerance':math.radians(.5),'stopped_linear':.005,'stopped_angular':.02,'dwell':.5}
        self.params={'goal_checker_plugins':['wall_goal'],'wall_goal.plugin':'farm_wall_controller::WallGoalChecker'}
        self.params.update({'wall_alignment.'+k:v for k,v in self.config.items()})
    def validate(self,**kw):
        return validate_goal_checkers(self.params,.005,math.radians(.5),**kw)
    def test_requires_explicit_optin(self):
        with self.assertRaises(NavigationConfigurationError):self.validate()
        self.assertEqual(self.validate(wall_parameters=self.config)[0]['plugin'],'farm_wall_controller::WallGoalChecker')
    def test_every_parameter_mismatch_fails(self):
        for key in self.config:
            old=self.params['wall_alignment.'+key];self.params['wall_alignment.'+key]=old+.001
            with self.assertRaises(NavigationConfigurationError):self.validate(wall_parameters=self.config)
            self.params['wall_alignment.'+key]=old
    def test_wrong_plugin_rejected(self):
        self.params['wall_goal.plugin']='unknown'
        with self.assertRaises(NavigationConfigurationError):self.validate(wall_parameters=self.config)
    def test_live_preflight_reads_shared_wall_prefix(self):
        c=Nav2Client.__new__(Nav2Client);c._settings=NavigationSettings(mode='follow_path',goal_checker_id='wall_goal')
        c._follow=NS(server_is_ready=lambda:True);c._parameters=NS(service_is_ready=lambda:True)
        params=dict(self.params,controller_plugins=['FollowPath'],progress_checker_plugins=['progress_checker'])
        names=[]
        def read(keys,check):
            names.extend(keys)
            # 실제 ROS처럼 미선언 항목 하나라도 포함되면 요청 전체가 실패한다.
            missing=[k for k in keys if k not in params]
            if missing:raise RuntimeError('Nav2 설정 응답 누락: '+','.join(missing))
            return {k:params[k] for k in keys}
        c._read_parameters=read
        self.assertEqual(c.preflight(lambda:None,wall_parameters=self.config)['status'],'OK')
        self.assertIn('wall_alignment.target_angle',names)
        self.assertNotIn('wall_goal.target_angle',names)

    def test_standard_checker_preflight_keeps_existing_contract(self):
        for plugin in ('nav2_controller::SimpleGoalChecker','nav2_controller::StoppedGoalChecker'):
            with self.subTest(plugin=plugin):
                c=Nav2Client.__new__(Nav2Client);c._settings=NavigationSettings(mode='follow_path')
                c._follow=NS(server_is_ready=lambda:True);c._parameters=NS(service_is_ready=lambda:True)
                params={'goal_checker_plugins':['goal_checker'],'controller_plugins':['FollowPath'],
                    'FollowPath.desired_linear_vel':.1,
                    'progress_checker_plugins':['progress_checker'],'goal_checker.plugin':plugin,
                    'goal_checker.xy_goal_tolerance':.02,'goal_checker.yaw_goal_tolerance':.03,
                    'goal_checker.stateful':False,'goal_checker.symmetric_yaw_tolerance':False}
                if plugin.endswith('StoppedGoalChecker'):
                    params.update({'goal_checker.trans_stopped_velocity':.005,'goal_checker.rot_stopped_velocity':.02,
                        'min_x_velocity_threshold':.001,'min_y_velocity_threshold':.001,'min_theta_velocity_threshold':.001})
                c._read_parameters=lambda keys,check:{k:params[k] for k in keys}
                self.assertEqual(c.preflight(lambda:None)['status'],'OK')
                params['goal_checker.xy_goal_tolerance']=.1
                with self.assertRaises(NavigationConfigurationError):c.preflight(lambda:None)

    def test_missing_wall_parameter_remains_failure(self):
        c=Nav2Client.__new__(Nav2Client);c._settings=NavigationSettings(mode='follow_path',goal_checker_id='wall_goal')
        c._follow=NS(server_is_ready=lambda:True);c._parameters=NS(service_is_ready=lambda:True)
        params=dict(self.params,controller_plugins=['FollowPath'],progress_checker_plugins=['progress_checker'])
        del params['wall_alignment.target_angle']
        c._read_parameters=lambda keys,check:{k:params[k] for k in keys}
        with self.assertRaises(KeyError):c.preflight(lambda:None,wall_parameters=self.config)

if __name__=='__main__':unittest.main()
