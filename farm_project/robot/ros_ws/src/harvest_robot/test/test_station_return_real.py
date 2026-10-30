"""실물 복귀 어댑터의 오프라인 계약 시험. ROS 노드·차체 명령은 실행하지 않는다."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace as NS
import unittest
from unittest.mock import Mock, patch

import numpy as np
from farm_common.action_handoff import ActionHandoff, ActionInterrupted
from farm_navigation.navigator import Navigator
from farm_common.station_return import Station
from farm_navigation.navigation_types import NavigationSettings, RoutePlan
from harvest_robot.station_return_real import (
    RealStationReturn, return_profile, tag_section)

ROOT = Path(__file__).resolve().parents[5]


class ConfigurationTests(unittest.TestCase):
    def test_repository_station_uses_existing_navigation_settings(self) -> None:
        import yaml
        profile = yaml.safe_load((ROOT/'robot/config/environments/harvest_station_return_jetson_real.yaml').read_text())
        original = NavigationSettings()
        selected, settings = return_profile(ROOT, profile, original)
        self.assertEqual(selected['station_config'], profile['station_return_config'])
        self.assertIs(settings, original)

    def test_constructor_reuses_one_action_server_and_client(self) -> None:
        import yaml
        profile = yaml.safe_load((ROOT/'robot/config/environments/harvest_station_return_jetson_real.yaml').read_text())
        profile['route_graph'] = str(ROOT/profile['route_graph'])
        node = Mock()
        node.config = json.loads((ROOT/'robot/config/harvest/harvest_handoff_jetson_real.json').read_text())
        with patch('farm_common.station_return.ActionServer') as action, \
                patch('farm_common.station_return.Nav2Client') as client:
            server = RealStationReturn(node, root=ROOT, profile=profile, settings=NavigationSettings(),
                poses=Mock(), motion=Mock(), callbacks=Mock(), handoff=ActionHandoff(),
                unavailable=lambda:False, block=Mock(), prepare=Mock(), tag_control=Mock())
            self.assertEqual(server._station.station_id, 'STATION_HARVEST_01')
            self.assertIs(type(server._navigator), Navigator)
            self.assertEqual(server._navigator._settings.controller_id, 'StationReverse')
            action.assert_called_once()
            client.assert_called_once()
            server.close()

    def test_profile_keeps_existing_device_navigation_and_tag_configuration(self) -> None:
        import yaml
        path = ROOT/'robot/config/environments'
        original = yaml.safe_load((path/'harvest_handoff_jetson_real.yaml').read_text())
        selected = yaml.safe_load((path/'harvest_station_return_jetson_real.yaml').read_text())
        selected.pop('navigation_trial_config')
        selected.pop('station_return_config')
        self.assertIs(selected.pop('station_return_skip_arm_status'), True)
        self.assertEqual(selected, original)

    def test_retry_client_factory_and_existing_output_are_connected(self) -> None:
        import yaml
        from dataclasses import replace
        profile = yaml.safe_load((ROOT/'robot/config/environments/harvest_station_return_jetson_real.yaml').read_text())
        profile['route_graph'] = str(ROOT/profile['route_graph'])
        node = Mock()
        node.config = {}
        client = Mock()
        factory = Mock(return_value=client)
        with patch('farm_common.station_return.ActionServer'):
            server = RealStationReturn(node, root=ROOT, profile=profile,
                settings=replace(NavigationSettings(), collision_retry_count=5),
                poses=Mock(), motion=Mock(), callbacks=Mock(), handoff=ActionHandoff(),
                unavailable=lambda:False, block=Mock(), prepare=Mock(), tag_control=Mock(),
                client_factory=factory, recovery_output=Mock())
            selected = factory.call_args.args[1]
            self.assertEqual(selected.controller_id, 'StationReverse')
            self.assertEqual(selected.collision_retry_count, 5)
            client.set_recovery_stop.assert_called_once_with(server._stop_for_recovery)
            client.set_recovery_probe.assert_called_once()
            server.close()

    def test_unset_target_remains_unavailable(self) -> None:
        with TemporaryDirectory() as folder:
            root = Path(folder)
            data = dict(map_id='test', stations={'robot':dict(station_id='station', node_id=None,
                        xy_m=None, yaw_rad=None)})
            profile = dict(map_id='test', robot_id='robot', station_return_config='station.json')
            (root/'station.json').write_text(json.dumps(data))
            original = NavigationSettings()
            selected, settings = return_profile(root, profile, original)
            self.assertNotIn('station_config', selected)
            self.assertIs(settings, original)

    def test_tag_section_preserves_body_heading_and_does_not_guess(self) -> None:
        corridors = {'A':dict(entry=(0, 0), exit=(2, 0), yaw=0)}
        self.assertEqual(tag_section(corridors, (1, 0), 0, .1, .1), 'A')
        self.assertIsNone(tag_section(corridors, (1, 0), 3.14, .1, .1))
        self.assertIsNone(tag_section(corridors, (3, 0), 0, .1, .1))
        self.assertIsNone(tag_section(dict(corridors, B=corridors['A']), (1, 0), 0, .1, .1))



class ActionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.server = object.__new__(RealStationReturn)
        s = self.server
        s._node = Mock()
        s._map_aliases = {}
        s._real_node = NS(staged_navigation=Mock(), jetson_connection=None,
                          section_resolution={'corridors':{'A':dict(entry=(0,0), exit=(2,0), yaw=0)}})
        s._prepare_existing = Mock()
        s._prepare = s._prepare_real
        s._settings = s._tag_settings = NavigationSettings()
        s._profile = dict(mode='real', robot_id='robot', map_id='test')
        s._station = Station('station', (0.,0.), 0.)
        s._handoff = ActionHandoff()
        s._unavailable = lambda:False
        s._block = Mock()
        s._handle = s._token = None
        s._mission = s._controller = None
        s._corner_navigation = None
        s._docking = None
        s._docked = False
        s._tag_active, s._tag_section, s._next_tag_update = False, None, 0.
        s._tag_control = Mock()
        transform = np.eye(4)
        transform[0,3] = 1
        s._poses = NS(current=lambda check:transform)
        s._graph = Mock()
        s._graph.plan.return_value = RoutePlan('old', 'hash', 'map', ((0,0),(.5,0),(1,0)), ('a','b'), 1.)
        s._navigator = Mock()
        s._navigator.navigate.side_effect = lambda *args, **kwargs:s._check()
        self.handle = Mock(request=NS(robot_id='robot', task_id='task', station_id='station', map_id='test'),
                           is_cancel_requested=False)
        self.assertTrue(s._handoff.reserve('return', 'task'))

    def execute(self) -> object:
        with patch('farm_common.station_return.rclpy.ok', return_value=True):
            return self.server.execute(self.handle)

    def test_docked_true_only_after_docking_and_cleanup_success(self) -> None:
        self.server._docking = Mock()
        result = self.execute()
        self.assertEqual(result.result_code, 'SUCCESS')
        self.assertTrue(result.docked)
        self.server._docking.execute.assert_called_once()
        self.server._docking.cleanup.assert_called_once()

    def test_docking_cleanup_failure_cannot_report_docked(self) -> None:
        self.server._docking = Mock()
        self.server._docking.cleanup.side_effect = RuntimeError('stop unconfirmed')
        result = self.execute()
        self.assertEqual(result.result_code, 'FAILED')
        self.assertFalse(result.docked)

    def test_docking_cancel_cannot_report_docked(self) -> None:
        self.server._docking = Mock()
        self.server._docking.execute.side_effect = ActionInterrupted('cancel docking')
        result = self.execute()
        self.assertEqual(result.result_code, 'CANCELED')
        self.assertFalse(result.docked)
        self.server._docking.cleanup.assert_called_once()

    def test_real_wire_map_alias_preserves_goal_and_navigation(self) -> None:
        from farm_interfaces.action import ReturnToStation
        from rclpy.action import GoalResponse
        s = self.server
        s._profile['map_id'] = 'many_farm_v1'
        s._map_aliases = json.loads((ROOT/'robot/config/harvest/harvest_handoff_jetson_real.json').read_text())['control_aliases']['map_ids']
        s._handoff.release('return', 'task')
        goal = ReturnToStation.Goal(robot_id='robot', task_id='task', station_id='station',
                                    map_id='farm_map_v1', timestamp='2026-10-28T00:00:00+09:00')
        self.assertEqual(s.accept(goal), GoalResponse.ACCEPT)
        self.assertEqual(goal.map_id, 'farm_map_v1')
        self.assertEqual(s._profile['map_id'], 'many_farm_v1')
        self.handle.request = goal
        self.assertEqual(self.execute().result_code, 'SUCCESS')
        self.assertEqual(s._navigator.navigate.call_args.args, ((0., 0.), 0.))
        s._tag_control.begin.assert_any_call('A')

    def test_map_alias_does_not_bypass_other_goal_checks(self) -> None:
        from rclpy.action import GoalResponse
        s = self.server
        s._handoff.release('return', 'task')
        s._profile['map_id'] = 'many_farm_v1'
        s._map_aliases = {'farm_map_v1':'many_farm_v1'}
        for changes in ({'map_id':'unknown'}, {'robot_id':'wrong'}, {'station_id':'wrong'}):
            goal = NS(robot_id='robot', task_id='task', station_id='station', map_id='farm_map_v1')
            for name, value in changes.items():
                setattr(goal, name, value)
            self.assertEqual(s.accept(goal), GoalResponse.REJECT)
            self.assertFalse(s._handoff.busy)
        self.handle.request.map_id = 'many_farm_v1'
        self.assertEqual(s.accept(self.handle.request), GoalResponse.ACCEPT)

    def test_success_reverses_route_and_keeps_tag_active(self) -> None:
        result = self.execute()
        self.assertEqual(result.result_code, 'SUCCESS')
        self.assertFalse(result.docked)
        s = self.server
        options = s._navigator.navigate.call_args.kwargs
        self.assertTrue(options['reverse'])
        self.assertEqual(options['route_plan'].points, ((1,0),(.5,0),(0,0)))
        self.assertEqual(options['route_plan'].edge_ids, ('b','a'))
        s._tag_control.begin.assert_any_call('A')
        s._tag_control.end.assert_called_once()
        s._real_node.staged_navigation.cancel_nav.assert_called_once()
        self.assertFalse(s._handoff.busy)

    def test_tag_section_is_cleared_outside_work_corridor_without_stopping(self) -> None:
        s = self.server
        def move(*args: object, **kwargs: object) -> None:
            s._check()
            outside = np.eye(4)
            outside[0,3] = 3
            s._poses = NS(current=lambda check:outside)
            s._mission._next_update = 0
            s._check()
        s._navigator.navigate.side_effect = move
        self.assertEqual(self.execute().result_code, 'SUCCESS')
        s._tag_control.begin.assert_called_once_with('A')
        s._tag_control.end.assert_called_once()

    def test_transfer_cannot_be_preempted(self) -> None:
        from rclpy.action import GoalResponse
        s = self.server
        s._handoff.release('return', 'task')
        self.assertTrue(s._handoff.reserve('transfer', 'transfer', preempt=False, interruptible=False))
        self.assertEqual(s.accept(self.handle.request), GoalResponse.REJECT)

    def test_arrival_diagnostic_does_not_override_nav_success_or_claim_docking(self) -> None:
        self.server._navigator.navigate.side_effect = None
        self.server._navigator.navigate.return_value = NS(measurement={'accepted':False})
        result = self.execute()
        self.assertEqual(result.result_code, 'SUCCESS')
        self.assertEqual(result.error_code, 'NONE')
        self.assertFalse(result.docked)
        self.server._navigator.cancel_nav.assert_called_once()

    def test_navigation_failure_cleans_up_and_releases(self) -> None:
        self.server._navigator.navigate.side_effect = RuntimeError('collision')
        result = self.execute()
        self.assertEqual(result.result_code, 'FAILED')
        self.server._navigator.cancel_nav.assert_called_once()
        self.server._tag_control.end.assert_called_once()
        self.assertFalse(self.server._handoff.busy)

    def test_cancel_and_failed_cancel_are_distinct(self) -> None:
        self.server._navigator.navigate.side_effect = ActionInterrupted('cancel')
        self.handle.is_cancel_requested = True
        result = self.execute()
        self.assertEqual(result.result_code, 'CANCELED')
        self.handle.canceled.assert_called_once()
        self.assertFalse(self.server._handoff.busy)

    def test_stop_unconfirmed_blocks_existing_owner(self) -> None:
        self.server._navigator.cancel_nav.side_effect = RuntimeError('stop unconfirmed')
        result = self.execute()
        self.assertEqual(result.error_code, 'CANCEL_UNCONFIRMED')
        self.server._block.assert_called_once()

    def test_jetson_start_checks_pose_not_arm_request_ready(self) -> None:
        s = self.server
        snapshot = dict(stale=False, status=dict(device_state_valid=True, arm_stowed=True,
                                                 arm_stopped=True, ready=False))
        s._real_node.jetson_connection = NS(snapshot=lambda:snapshot)
        self.assertEqual(self.execute().result_code, 'SUCCESS')

    def test_unstowed_arm_never_starts_navigation(self) -> None:
        s = self.server
        s._real_node.jetson_connection = NS(snapshot=lambda:dict(stale=False,
                status=dict(device_state_valid=True, arm_stowed=False, arm_stopped=True)))
        self.assertEqual(self.execute().result_code, 'FAILED')
        s._navigator.navigate.assert_not_called()

    def test_chassis_trial_skips_missing_arm_status_and_preserves_tags(self) -> None:
        s = self.server
        s._profile['station_return_skip_arm_status'] = True
        connection = Mock()
        connection.snapshot.return_value = dict(stale=True, status=None)
        s._real_node.jetson_connection = connection
        result = self.execute()
        self.assertEqual(result.result_code, 'SUCCESS')
        self.assertFalse(result.docked)
        connection.snapshot.assert_not_called()
        self.assertTrue(s._navigator.navigate.call_args.kwargs['reverse'])
        s._tag_control.begin.assert_any_call('A')
        s._tag_control.end.assert_called_once()

    def test_default_rejects_missing_arm_status(self) -> None:
        s = self.server
        s._real_node.jetson_connection = NS(snapshot=lambda:dict(stale=True, status=None))
        self.assertEqual(self.execute().result_code, 'FAILED')
        s._navigator.navigate.assert_not_called()

    def test_unset_station_rejects_goal(self) -> None:
        from rclpy.action import GoalResponse
        self.server._station = None
        self.assertEqual(self.server.accept(self.handle.request), GoalResponse.REJECT)


    def test_heading_oscillation_keeps_one_tag_session(self) -> None:
        import math
        s = self.server
        def move(*args: object, **kwargs: object) -> None:
            for degrees in (0, 14, -13, 2, 9, 0):
                pose = np.eye(4)
                angle = math.radians(degrees)
                pose[:2, :2] = [[math.cos(angle), -math.sin(angle)],
                               [math.sin(angle), math.cos(angle)]]
                pose[0, 3] = 1
                s._poses.current = lambda check, value=pose:value
                s._mission._next_update = 0
                s._check()
        s._navigator.navigate.side_effect = move
        self.assertEqual(self.execute().result_code, 'SUCCESS')
        s._tag_control.begin.assert_called_once_with('A')
        s._tag_control.end.assert_called_once()

    def test_tag_exit_and_reentry_do_not_restart_in_same_update(self) -> None:
        s = self.server
        def move(*args: object, **kwargs: object) -> None:
            for x, begins, ends in [(3., 1, 1), (1., 2, 1), (1., 2, 1)]:
                pose = np.eye(4)
                pose[0, 3] = x
                s._poses.current = lambda check, value=pose:value
                s._mission._next_update = 0
                s._check()
                self.assertEqual(s._tag_control.begin.call_count, begins)
                self.assertEqual(s._tag_control.end.call_count, ends)
        s._navigator.navigate.side_effect = move
        self.assertEqual(self.execute().result_code, 'SUCCESS')
        self.assertEqual(s._tag_control.end.call_count, 2)

    def test_optional_tag_connection_does_not_add_navigation_gate(self) -> None:
        self.server._tag_control = None
        self.assertEqual(self.execute().result_code, 'SUCCESS')
        self.server._navigator.navigate.assert_called_once()

    def test_retry_stop_uses_existing_output_only_for_active_return(self) -> None:
        from threading import RLock
        s = self.server
        s._recovery_output = NS(lock=RLock(), publisher=Mock(), error=None)
        def move(*args: object, **kwargs: object) -> None:
            s._stop_for_recovery()
            msg = s._recovery_output.publisher.publish.call_args.args[0]
            self.assertEqual(msg.linear.x, 0.)
            self.assertEqual(msg.angular.z, 0.)
            s._recovery_output.error = 'output fault'
            with self.assertRaisesRegex(RuntimeError, '소유권'):
                s._stop_for_recovery()
            s._recovery_output.error = None
        s._navigator.navigate.side_effect = move
        self.assertEqual(self.execute().result_code, 'SUCCESS')
        s._recovery_output.publisher.publish.assert_called_once()

    def test_cancel_during_cleanup_is_not_reported_as_success(self) -> None:
        self.server._navigator.cancel_nav.side_effect = lambda:setattr(self.handle, 'is_cancel_requested', True)
        self.assertEqual(self.execute().result_code, 'CANCELED')
        self.handle.succeed.assert_not_called()

    def test_new_request_does_not_reuse_previous_mission_or_tag_session(self) -> None:
        self.assertEqual(self.execute().result_code, 'SUCCESS')
        s = self.server
        self.assertIsNone(s._mission)
        self.handle.request.task_id = 'task2'
        self.assertTrue(s._handoff.reserve('return', 'task2'))
        self.assertEqual(self.execute().result_code, 'SUCCESS')
        self.assertEqual(s._tag_control.begin.call_count, 2)
        self.assertEqual(s._navigator.cancel_nav.call_count, 2)

    def test_legacy_common_entry_keeps_result_and_path_contract(self) -> None:
        from farm_common.station_return import StationReturn
        for mode, docked in [('sim', True), ('real', False)]:
            with self.subTest(mode=mode):
                legacy = object.__new__(StationReturn)
                legacy.__dict__.update(self.server.__dict__)
                legacy._profile = dict(self.server._profile, mode=mode)
                legacy._prepare = Mock()
                legacy._navigator = Mock()
                legacy._graph.section_at.return_value = 'A'
                legacy._tag_control = Mock()
                legacy._handoff = ActionHandoff()
                legacy._handoff.reserve('return', 'task')
                with patch('farm_common.station_return.rclpy.ok', return_value=True):
                    result = legacy.execute(self.handle)
                self.assertEqual(result.result_code, 'SUCCESS')
                self.assertIs(result.docked, docked)
                self.assertEqual([call.args for call in legacy._tag_control.begin.call_args_list],
                                 [(), ('A',)])
                legacy._tag_control.end.assert_called_once()
                legacy._navigator.cancel_nav.assert_called_once()
                self.assertEqual(legacy._navigator.navigate.call_args.kwargs['route_plan'].points,
                                 ((1,0),(.5,0),(0,0)))


if __name__ == '__main__':
    unittest.main()
