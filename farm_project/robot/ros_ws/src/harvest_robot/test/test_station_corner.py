"""실물 복귀 코너의 기하·조립·실패 정리 계약. 운영 ROS 프로세스를 실행하지 않는다."""
from copy import deepcopy
from dataclasses import replace
import math
from pathlib import Path
import threading
from types import SimpleNamespace as NS
import unittest
from unittest.mock import Mock, patch
import numpy as np
from geometry_msgs.msg import Twist
from farm_navigation.arrival import validate_goal_checkers
from farm_navigation.arc_clearance import ObstacleBlocked
from farm_navigation.collision_recovery import Nav2ControlUnavailable, run_with_collision_recovery
from farm_navigation.configuration import load_nav2_parameters
from farm_navigation.navigation_types import NavigationSettings, RoutePlan
from farm_navigation.path_builder import build_path
from farm_navigation.route import RouteGraph, reverse_plan, Edge
from farm_navigation.transfer_arc import arc_path
from harvest_robot.station_corner_plan import split_corners, split_graph_corners, anchored_arc
from harvest_robot.station_corner_config import server_config, navigation_settings
from harvest_robot.station_corner_navigation import CornerNavigation, corner_control_error

ROOT = Path(__file__).resolve().parents[5]


def route(points: list) -> RoutePlan:
    return RoutePlan('test', 'hash', 'map', tuple(points), ('b','a'), 0.)


class GeometryTests(unittest.TestCase):
    def test_actual_graph_station_route_uses_tangent_arc(self) -> None:
        import yaml
        graph = RouteGraph(ROOT/'robot/config/maps/many_farm/graph.geojson')
        cfg = yaml.safe_load((ROOT/'robot/config/robots/vicpinky/station_return.yaml').read_text())
        station = cfg['stations']['harvest_01']
        plan = reverse_plan(graph.plan(tuple(station['xy_m']), graph.nodes[14], .1, .1))
        corners, tail = split_corners(plan, .2)
        self.assertEqual(len(corners), 1)
        corner = corners[0]
        poses = arc_path((*corner.approach.points[-1], corner.entry_yaw), corner.spec)
        np.testing.assert_allclose(poses[-1][:2], tail.points[0], atol=1e-12)
        self.assertEqual(tail.points[-1], tuple(station['xy_m']))
        self.assertAlmostEqual(poses[-1][2], station['yaw_rad'])
        self.assertAlmostEqual(corner.spec.radius, .2)
        self.assertEqual(corner.approach.graph_revision, plan.graph_revision)

    def test_graph_connectors_with_actual_position_errors(self) -> None:
        graph = RouteGraph(ROOT/'robot/config/maps/many_farm/graph.geojson')
        nominal = reverse_plan(graph.plan(graph.nodes[18], graph.nodes[14], .1, .1))
        reference = split_graph_corners(nominal, .2, graph)[0][0]
        x, y = graph.nodes[14]
        samples = [(3.57196397902015, -0.03514883961595464)]
        samples += [(x+dx, y+dy) for dx in (-.05, -.004, 0., .004, .05)
                    for dy in (-.05, -.001, -.00015, 0., .00015, .001, .05)]
        for actual in samples:
            with self.subTest(actual=actual):
                plan = reverse_plan(graph.plan(graph.nodes[18], actual, .1, .1))
                corners, tail = split_graph_corners(plan, .2, graph)
                self.assertEqual(len(corners), 1)
                corner = corners[0]
                self.assertEqual(corner.approach.points[0], actual)
                self.assertEqual(corner.approach.points[-1], reference.approach.points[-1])
                self.assertEqual(corner.entry_yaw, reference.entry_yaw)
                self.assertEqual(corner.spec, reference.spec)
                self.assertEqual(tail.points[-1], graph.nodes[18])

    def test_graph_short_real_corner_still_rejected(self) -> None:
        graph = NS(nodes={0:(0.,-.1),1:(0.,0.),2:(1.,0.)},
                   edges=[Edge('a',0,1),Edge('b',1,2)])
        with self.assertRaisesRegex(ValueError, '접선 길이'):
            split_graph_corners(route([(1.,-.00015),(1.,0.),(0.,0.),(0.,-.1)]), .2, graph)

    def test_goal_connector_and_no_corner_keep_actual_endpoints(self) -> None:
        graph = RouteGraph(ROOT/'robot/config/maps/many_farm/graph.geojson')
        x, y = graph.nodes[18]
        for goal in ((x-.01,y), (x+.01,y)):
            plan = reverse_plan(graph.plan(goal, graph.nodes[14], .1, .1))
            corners, tail = split_graph_corners(plan,.2,graph)
            self.assertEqual(len(corners),1)
            self.assertEqual(tail.points[-1],goal)
        plan = reverse_plan(graph.plan(graph.nodes[12], (3.572,-.03515), .1, .1))
        corners, tail = split_graph_corners(plan,.2,graph)
        self.assertEqual(corners,[])
        self.assertIs(tail,plan)

    def test_unsupported_corner_and_short_segment_fail_before_dispatch(self) -> None:
        for points in ([ (1.,0.),(0.,0.),(0.,1.) ], [(1.,0.),(0.,0.),(0.,-.1)],
                       [(1.,0.),(0.,0.),(0.,-.3),(1.,-.3)]):
            with self.subTest(points=points), self.assertRaises(ValueError):
                split_corners(route(points), .2)

    def test_straight_and_repeated_points(self) -> None:
        corners, tail = split_corners(route([(3.,0.),(2.,0.),(2.,0.),(1.,0.)]), .2)
        self.assertFalse(corners)
        self.assertEqual(tail.points, ((3.,0.),(1.,0.)))

    def test_anchored_path_keeps_body_headings_without_second_reverse(self) -> None:
        from builtin_interfaces.msg import Time
        corner = split_corners(route([(1.,0.),(0.,0.),(0.,-1.)]), .2)[0][0]
        actual = (4., 2., .03)
        plan = anchored_arc(corner.approach, actual, corner.spec, 'odom')
        path = build_path(plan, plan.headings[-1], Time(), .04)
        self.assertEqual(path.header.frame_id, 'odom')
        self.assertEqual(len(path.poses), len(plan.points))
        self.assertEqual(plan.points[0], actual[:2])
        self.assertAlmostEqual(plan.headings[0], actual[2])
        self.assertLess(path.poses[-1].pose.position.x, actual[0])


class SettingsTests(unittest.TestCase):
    def test_launch_derives_profile_without_changing_original_or_starting_nodes(self) -> None:
        import importlib.util
        import yaml
        from launch import LaunchContext
        from launch.actions import IncludeLaunchDescription
        from launch_ros.actions import Node
        path = ROOT/'robot/ros_ws/src/harvest_robot/launch/station_return.launch.py'
        spec = importlib.util.spec_from_file_location('station_corner_launch', path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        environment = ROOT/'robot/config/environments/harvest_station_return_jetson_real.yaml'
        original = environment.read_bytes()
        context = LaunchContext()
        context.launch_configurations.update(project_root=str(ROOT), environment_config=str(environment),
            handoff_config='existing-handoff-config', corner_radius_m='0.20', devices='true',
            tag_correction='true', tag_camera='auto', capture_directory='')
        outputs = []
        real_save = module.save_parameters
        def save(values: dict) -> str:
            outputs.append(deepcopy(values))
            return real_save(values)
        with patch.object(module, 'save_parameters', save):
            actions = module.setup(context)
        self.assertEqual(environment.read_bytes(), original)
        self.assertEqual(outputs[0]['station_corner_radius_m'], .2)
        selected = dict(outputs[0]); selected.pop('station_corner_radius_m')
        self.assertEqual(selected, yaml.safe_load(original))
        self.assertEqual(sum(isinstance(a, IncludeLaunchDescription) for a in actions), 1)
        self.assertEqual(sum(isinstance(a, Node) for a in actions), 3)

    def test_isolated_server_preserves_originals_and_real_footprint(self) -> None:
        nav = load_nav2_parameters('robot/config/robots/vicpinky/nav2.yaml', ROOT)
        original = deepcopy(nav)
        values = server_config(nav, 'harvest_01')
        self.assertEqual(nav, original)
        cp = values['/harvest_01/station_corner/controller_server']['ros__parameters']
        cm = values['/harvest_01/station_corner/local_costmap/local_costmap']['ros__parameters']
        self.assertEqual(cp['controller_plugins'], ['TransferArc', 'StationReverse'])
        self.assertTrue(cp['StationReverse.skip_position_approach_rotation'])
        self.assertTrue(cp['StationReverse.use_work_curvature'])
        for key in ('use_fixed_curvature_lookahead', 'curvature_lookahead_dist',
                    'interpolate_curvature_after_goal'):
            self.assertEqual(cp['StationReverse.'+key], original['controller_server']['ros__parameters']['HarvestWork'][key])
        self.assertNotIn('use_work_curvature', original['controller_server']['ros__parameters']['StationReverse'])
        self.assertNotIn('skip_position_approach_rotation', original['controller_server']['ros__parameters']['StationReverse'])
        for name, value in original['controller_server']['ros__parameters']['StationReverse'].items():
            expected = .006 if name in ('min_approach_linear_velocity', 'regulated_linear_scaling_min_speed') else value
            if name in ('use_fixed_curvature_lookahead', 'curvature_lookahead_dist',
                        'interpolate_curvature_after_goal'):
                expected = original['controller_server']['ros__parameters']['HarvestWork'][name]
            self.assertEqual(cp['StationReverse.'+name], expected)
        self.assertEqual(cm['footprint_padding'], .02)
        self.assertEqual(cm['voxel_layer.scan.topic'], '/harvest_01/scan_filtered')
        for arc in (False, True):
            settings = navigation_settings(NavigationSettings(collision_retry_count=5), 'harvest_01', arc=arc)
            selected = dict(cp, goal_checker_plugins=[settings.goal_checker_id])
            validate_goal_checkers(selected, settings.arrival_tolerance_m, settings.heading_tolerance_rad)
            self.assertEqual(settings.collision_retry_count, 5)
        self.assertEqual(cp['TransferArc.desired_linear_vel'], .05)
        self.assertEqual(cp['TransferArc.arc_max_linear_vel'], .05)
        self.assertEqual(cp['TransferArc.arc_max_angular_vel'], .30)
        from farm_navigation.transfer_arc import trial_profile
        self.assertEqual(trial_profile()['TransferArc']['desired_linear_vel'], .01)
        self.assertNotIn('arc_max_linear_vel', trial_profile()['TransferArc'])

    def test_collision_only_retry(self) -> None:
        self.assertTrue(corner_control_error('Collision on transfer arc'))
        self.assertTrue(corner_control_error('Collision on reverse route'))
        self.assertFalse(corner_control_error('Arc deviation exceeded'))


class CompositionTests(unittest.TestCase):
    def test_precheck_collision_uses_existing_recovery_and_rechecks_grid(self) -> None:
        component = self.component()
        component._node = Mock()
        component._settings = replace(NavigationSettings(), collision_retry_count=1)
        component._poses.recovery_ready = Mock(return_value=True)
        component._motion = NS(stationary_now=lambda:True)
        component._recovery_stop = Mock()
        component._clearance = Mock(side_effect=[ObstacleBlocked('blocked'), .04])
        clock = [0.]
        def run(*args: object) -> float:
            return run_with_collision_recovery(*args, clock=lambda:clock[0],
                sleep=lambda dt:clock.__setitem__(0, clock[0]+dt))
        with patch('harvest_robot.station_corner_navigation.run_with_collision_recovery', run):
            self.assertEqual(CornerNavigation._clearance_with_retry(component, Mock()), .04)
        self.assertEqual(component._clearance.call_count, 2)
        self.assertTrue(component._recovery_stop.called)

    def component(self) -> CornerNavigation:
        result = object.__new__(CornerNavigation)
        result._radius = .2
        result._graph = NS(nodes={0:(0.,-1.),1:(0.,0.),2:(1.,0.)},
                           edges=[Edge('a',0,1),Edge('b',1,2)])
        result._settings = NavigationSettings()
        result._check = Mock()
        result._alignment_needs_stop = False
        result._spin = Mock()
        result._motion = Mock()
        result._enable, result._disable, result._record = Mock(), Mock(), Mock()
        result._clearance_with_retry = Mock(return_value=.001)
        result._approach, result._arc, result._straight = Mock(), Mock(), Mock()
        result._navigators = [result._approach, result._arc]
        result._approach.navigate.return_value = NS(stamp_ns=123, measurement={})
        result._arc.navigate.return_value = NS(stamp_ns=456, measurement={})
        origin = np.eye(4); origin[0,3], origin[1,3] = .202, .003
        end = np.eye(4); end[0,3], end[1,3] = .002, -.197
        result._poses = NS(lookup=Mock(return_value=origin), current=Mock(return_value=end))
        return result

    def test_sequence_anchors_at_stopped_pose_and_rejoins_actual_map(self) -> None:
        component = self.component()
        component.navigate((0.,-1.), math.pi/2,
            route_plan=route([(1.,0.),(0.,0.),(0.,-1.)]), reverse=True)
        self.assertEqual(component._poses.lookup.call_count, 2)
        component._spin.execute.assert_not_called()
        arc = component._arc.navigate.call_args.kwargs['route_plan']
        self.assertEqual(arc.points[0], (.202,.003))
        self.assertNotIn('reverse', component._arc.navigate.call_args.kwargs)
        self.assertEqual(component._straight.navigate.call_args.kwargs['route_plan'].points,
                         ((.002,-.197),(0.,-1.)))
        self.assertEqual(component._enable.call_count, 2)
        self.assertEqual(component._disable.call_count, 2)

    def test_actual_offset_route_dispatches_one_corner_and_keeps_tag_checks(self) -> None:
        component = self.component()
        graph = RouteGraph(ROOT/'robot/config/maps/many_farm/graph.geojson')
        component._graph = graph
        actual = (3.57196397902015, -.03514883961595464)
        plan = reverse_plan(graph.plan(graph.nodes[18], actual, .1, .1))
        component.navigate(graph.nodes[18], math.pi/2, route_plan=plan, reverse=True)
        approach = component._approach.navigate.call_args.kwargs['route_plan']
        self.assertEqual(approach.points[0], actual)
        component._approach.navigate.assert_called_once()
        component._arc.navigate.assert_called_once()
        component._straight.navigate.assert_called_once()
        component._clearance_with_retry.assert_called_once()

    def test_alignment_uses_frozen_odom_and_stops_before_arc(self) -> None:
        component = self.component()
        origin = np.eye(4)
        mapped = np.eye(4)
        a = -.08
        mapped[:2,:2] = [[math.cos(a),-math.sin(a)],[math.sin(a),math.cos(a)]]
        aligned = np.eye(4)
        aligned[:2,:2] = [[math.cos(-a),-math.sin(-a)],[math.sin(-a),math.cos(-a)]]
        component._poses.lookup.side_effect = [origin, mapped, aligned]
        component._motion.wait_stopped.return_value = 999
        result = component._align(NS(stamp_ns=123),0.,route([(1.,0.),(0.,0.)]))
        self.assertAlmostEqual(result[2],.08)
        self.assertAlmostEqual(component._spin.execute.call_args.args[0],.08)
        self.assertIs(component._spin.execute.call_args.args[2],component._check)
        component._motion.wait_stopped.assert_called_once_with(component._check)
        self.assertEqual(component._poses.lookup.call_args.args[:3],('odom','base_footprint',999))
        component._clearance_with_retry.assert_called_once()

    def test_alignment_collision_prevents_spin(self) -> None:
        component = self.component()
        pose = np.eye(4);a=.08
        pose[:2,:2]=[[math.cos(a),-math.sin(a)],[math.sin(a),math.cos(a)]]
        component._poses.lookup.side_effect=[np.eye(4),pose]
        component._clearance_with_retry.side_effect=RuntimeError('collision')
        with self.assertRaisesRegex(RuntimeError,'collision'):
            component._align(NS(stamp_ns=123),0.,route([(1.,0.),(0.,0.)]))
        component._spin.execute.assert_not_called()

    def test_collision_precheck_blocks_arc_and_tail(self) -> None:
        component = self.component()
        component._clearance_with_retry.side_effect = RuntimeError('collision')
        with self.assertRaisesRegex(RuntimeError, 'collision'):
            component.navigate((0.,-1.), math.pi/2,
                route_plan=route([(1.,0.),(0.,0.),(0.,-1.)]), reverse=True)
        component._arc.navigate.assert_not_called()
        component._straight.navigate.assert_not_called()

    def test_arc_failure_disables_output_and_cleans_all_navigators(self) -> None:
        component = self.component()
        component._arc.navigate.side_effect = RuntimeError('tracking')
        with self.assertRaisesRegex(RuntimeError, 'tracking'):
            component.navigate((0.,-1.), math.pi/2,
                route_plan=route([(1.,0.),(0.,0.),(0.,-1.)]), reverse=True)
        component._straight.navigate.assert_not_called()
        component._approach.cancel_nav.side_effect = RuntimeError('cancel')
        with self.assertRaisesRegex(RuntimeError, 'cancel'):
            component.cancel_nav()
        for navigator in (*component._navigators, component._straight):
            navigator.cancel_nav.assert_called_once()

    def test_late_output_and_owner_loss_are_not_forwarded(self) -> None:
        component = self.component()
        component._lock = threading.RLock()
        component._publisher = Mock()
        component._owns_output = Mock(return_value=True)
        component._enabled = False
        component._relay(Twist())
        component._enabled = True
        component._relay(Twist())
        component._owns_output.return_value = False
        component._relay(Twist())
        component._publisher.publish.assert_called_once()

    def test_constructor_reuses_check_for_tags_and_existing_recovery(self) -> None:
        node, check, stop = Mock(), Mock(), Mock()
        with patch('harvest_robot.station_corner_navigation.SpinClient'), \
             patch('harvest_robot.station_corner_navigation.Nav2Client') as client, \
             patch('harvest_robot.station_corner_navigation.Navigator') as navigator:
            component = CornerNavigation(node, straight=Mock(), settings=NavigationSettings(), radius=.2, graph=Mock(),
                robot_id='harvest_01', poses=Mock(), motion=Mock(), callbacks=Mock(),
                check=check, owns_output=lambda:False, recovery_stop=stop)
            self.assertEqual(navigator.call_count, 2)
            for call in navigator.call_args_list:
                self.assertIs(call.args[5], check)
            self.assertEqual(client.return_value.set_recovery_stop.call_count, 2)
            component.close()


if __name__ == '__main__':
    unittest.main()
