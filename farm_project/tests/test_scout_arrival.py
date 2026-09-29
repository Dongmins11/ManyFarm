"""Offline regressions for the recurrent Nav2/survey arrival mismatch.

ROS messages/services are replaced with small fakes. These tests execute the
actual server methods, but do not claim to test ROS transport or robot motion.
"""
import ast
from concurrent.futures import Future
from datetime import datetime, timezone
import importlib.util
import json
import math
from pathlib import Path
import sys
import tempfile
import threading
import time
from types import SimpleNamespace as NS
import unittest
import uuid

import numpy as np
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'robot/ros_ws/src/scout_robot'))
from scout_robot.arrival import (NavigationConfigurationError, validate_goal_checkers,
                                measure_arrival, arrival_description)
from scout_robot.survey_core import matrix_from_pose

spec = importlib.util.spec_from_file_location('apply_arrival', ROOT/'scripts/apply_scout_arrival_fix.py')
patcher = importlib.util.module_from_spec(spec)
spec.loader.exec_module(patcher)


def completed(value):
    future = Future()
    future.set_result(value)
    return future


def goal():
    return NS(pose=NS(header=NS(), pose=NS(position=NS(), orientation=NS())))


SERVER_PATH = ROOT/'robot/ros_ws/src/scout_robot/scout_robot/survey_server.py'
tree = ast.parse(SERVER_PATH.read_text())
tree.body = [node for node in tree.body if isinstance(node, (ast.ClassDef, ast.FunctionDef))]
server_namespace = dict(Node=object, json=json, math=math, Path=Path, time=time,
    uuid=uuid, datetime=datetime, timezone=timezone, np=np,
    NavigateToPose=NS(Goal=goal), GetParameters=NS(Request=NS),
    GoalStatus=NS(STATUS_SUCCEEDED=4, STATUS_CANCELED=5, STATUS_ABORTED=6),
    ScoutArea=NS(Result=NS), rclpy=NS(ok=lambda: True),
    parameter_value_to_python=lambda value: value,
    NavigationConfigurationError=NavigationConfigurationError,
    validate_goal_checkers=validate_goal_checkers, measure_arrival=measure_arrival,
    arrival_description=arrival_description)
exec(compile(tree, str(SERVER_PATH), 'exec'), server_namespace)
SurveyServer = server_namespace['SurveyServer']
MissionCanceled = server_namespace['MissionCanceled']


def parameters(xy=.05, yaw=.08):
    return {'goal_checker_plugins': ['general_goal_checker'],
            'general_goal_checker.plugin': 'nav2_controller::SimpleGoalChecker',
            'general_goal_checker.xy_goal_tolerance': xy,
            'general_goal_checker.yaw_goal_tolerance': yaw,
            'general_goal_checker.stateful': True,
            'general_goal_checker.symmetric_yaw_tolerance': None}


def server(params=None):
    node = SurveyServer.__new__(SurveyServer)
    node.cfg = {'arrival_tolerance_m': .08, 'heading_tolerance_rad': .12,
                'base_frame': 'scout_01/base_footprint', 'goal_timeout_s': 300.,
                'output_dir': 'runs/scout_survey'}
    node.shutdown_requested = False
    node.active_goal = node.nav_handle = node.pending_nav = None
    node.controller_node = 'controller_server'
    node.navigation_log = []
    node.busy = True
    node.lock = threading.Lock()
    node.get_clock = lambda: NS(now=lambda: NS(to_msg=lambda: NS(sec=10, nanosec=0)))
    node.get_logger = lambda: NS(info=lambda _: None, error=lambda _: None)
    stored = parameters() if params is None else params
    node.nav_parameters = NS(service_is_ready=lambda: True,
        call_async=lambda request: completed(NS(values=[stored.get(k) for k in request.names])))
    node.events = []

    def send(_):
        node.events.append('send')
        return completed(NS(accepted=True, get_result_async=lambda: completed(NS(status=4))))

    node.nav = NS(server_is_ready=lambda: True, send_goal_async=send)

    def settled():
        node.events.append('settled')
        return 90123456789

    node.settled = settled
    return node


class ArrivalTests(unittest.TestCase):
    def test_original_mismatch_is_rejected_with_runtime_values(self):
        for xy, yaw in [(.12, .15), (.05, .15), (.08, .08)]:
            with self.subTest(xy=xy, yaw=yaw):
                with self.assertRaisesRegex(NavigationConfigurationError, 'tolerance mismatch'):
                    validate_goal_checkers(parameters(xy, yaw), .08, .12)
        self.assertEqual(validate_goal_checkers(parameters(), .08, .12)[0]['xy_goal_tolerance'], .05)

    def test_invalid_or_opposite_heading_configuration_is_rejected(self):
        for value in [float('nan'), 0., -1., True, None]:
            with self.assertRaises(NavigationConfigurationError):
                validate_goal_checkers(parameters(value), .08, .12)
        opposite = parameters()
        opposite['general_goal_checker.symmetric_yaw_tolerance'] = True
        with self.assertRaisesRegex(NavigationConfigurationError, 'camera direction'):
            validate_goal_checkers(opposite, .08, .12)

    def test_angle_wrap_and_distance_limit(self):
        yaw = -math.pi + .02
        pose = matrix_from_pose([.04, 0, 0], [0, 0, math.sin(yaw/2), math.cos(yaw/2)])
        result = measure_arrival(pose, [0, 0], math.pi-.02, .08, .12)
        self.assertTrue(result['accepted'])
        self.assertAlmostEqual(result['heading_error_rad'], .04)
        pose[0, 3] = .09
        result = measure_arrival(pose, [0, 0], math.pi-.02, .08, .12)
        self.assertFalse(result['accepted'])
        self.assertIn('distance=0.0900m (limit=0.0800m)', arrival_description(result))

    def test_navigation_uses_settled_timestamp_before_acceptance(self):
        node = server()

        def lookup(target, source, stamp):
            node.events.append('pose')
            self.assertEqual((target, source, stamp), ('map', node.cfg['base_frame'], 90123456789))
            return matrix_from_pose([.04, 0, 0], [0, 0, 0, 1])

        node.lookup = lookup
        self.assertEqual(node.navigate([0, 0], 0), 90123456789)
        self.assertEqual(node.events, ['send', 'settled', 'pose'])
        self.assertEqual(node.navigation_log[0]['status'], 'ARRIVED')

    def test_nav2_success_does_not_override_bad_settled_position(self):
        node = server()
        node.lookup = lambda *_: matrix_from_pose([.11, 0, 0], [0, 0, 0, 1])
        with self.assertRaisesRegex(RuntimeError, 'distance=0.1100m'):
            node.navigate([0, 0], 0)
        self.assertEqual(node.navigation_log[0]['status'], 'OUTSIDE_TOLERANCE')

    def test_cancel_during_settling_does_not_accept_arrival(self):
        node = server()

        def cancel():
            raise MissionCanceled('cancel during settling')

        node.settled = cancel
        node.lookup = lambda *_: self.fail('Do not query/accept pose after cancellation')
        with self.assertRaises(MissionCanceled):
            node.navigate([0, 0], 0)
        self.assertNotIn('accepted', node.navigation_log[0])

    def test_preflight_reads_live_service_values(self):
        node = server()
        report = {}
        node.preflight_navigation(report)
        self.assertEqual(report['navigation_preflight']['status'], 'OK')
        self.assertEqual(report['navigation_preflight']['parameters'], parameters())
        self.assertEqual(node.events, [])

    def test_bad_preflight_aborts_mission_before_motion_or_worker(self):
        node = server(parameters(.12, .15))
        node.vcfg = {}
        request = NS(robot_id='scout_01', task_id='test', section_ids=['BED_01'],
                     map_id='farm_map_v1', frame_id='map', crop_type='PAPRIKA', target_ripeness='RIPE')
        terminal = []
        action = NS(request=request, is_cancel_requested=False, abort=lambda: terminal.append('abort'))
        original_worker = server_namespace['Worker']
        server_namespace['Worker'] = lambda *_: self.fail('Do not start vision before preflight passes')
        try:
            with tempfile.TemporaryDirectory() as tmp:
                node.root = Path(tmp)
                result = node.execute(action)
                reports = list(node.root.glob('runs/scout_survey/*/survey.json'))
                self.assertEqual(len(reports), 1)
                report = json.loads(reports[0].read_text())
                self.assertEqual(report['navigation_preflight']['status'], 'FAILED')
                self.assertEqual(report['navigation'], [])
                self.assertEqual(result.error_code, 'NAV_CONFIG_MISMATCH')
                self.assertEqual(terminal, ['abort'])
                self.assertEqual(node.events, [])
                self.assertFalse(node.busy)
        finally:
            server_namespace['Worker'] = original_worker

    def test_persistent_patch_preserves_tuning_comments_and_is_idempotent(self):
        source = '''# User tuning must survive.
controller_server:
  ros__parameters:
    goal_checker_plugins: [general_goal_checker]
    general_goal_checker:
      plugin: nav2_controller::SimpleGoalChecker
      stateful: true
      xy_goal_tolerance: 0.12 # original distance
      yaw_goal_tolerance: 0.15
    FollowPath:
      max_angular_accel: 10.0
      desired_linear_vel: 0.137 # custom user speed
amcl:
  ros__parameters:
    initial_pose: {x: -6.2842, y: 12.0611, yaw: -1.5708}
'''
        after, old, changed = patcher.updated_text(source)
        self.assertTrue(changed)
        self.assertEqual(old, {'xy_goal_tolerance': .12, 'yaw_goal_tolerance': .15})
        self.assertEqual(after, source.replace('xy_goal_tolerance: 0.12', 'xy_goal_tolerance: 0.05')
                         .replace('yaw_goal_tolerance: 0.15', 'yaw_goal_tolerance: 0.08'))
        self.assertEqual(yaml.safe_load(after)['controller_server']['ros__parameters']['FollowPath']['max_angular_accel'], 10.)
        self.assertFalse(patcher.updated_text(after)[2])
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'nav2.yaml'
            path.write_text(source)
            patcher.apply(path, Path(tmp)/'backups')
            backups = list((Path(tmp)/'backups').glob('*.yaml'))
            self.assertEqual(len(backups), 1)
            self.assertEqual(backups[0].read_text(), source)
            self.assertEqual(path.read_text(), after)

    def test_patch_refuses_alias_that_would_change_another_setting(self):
        source = '''controller_server:
  ros__parameters:
    goal_checker_plugins: [general_goal_checker]
    general_goal_checker:
      plugin: nav2_controller::SimpleGoalChecker
      xy_goal_tolerance: &shared 0.12
      yaw_goal_tolerance: 0.15
    unrelated: *shared
'''
        with self.assertRaises((ValueError, yaml.YAMLError)):
            patcher.updated_text(source)


if __name__ == '__main__':
    unittest.main()
