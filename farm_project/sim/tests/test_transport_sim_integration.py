"""운송 환경 경계·마커 없는 복귀 검사. 센서/주행은 대역이며 Isaac 시험이 아니다."""
import json
from pathlib import Path
import tempfile
import threading
import time
from types import SimpleNamespace as NS
import unittest
from unittest.mock import Mock

from rclpy.action import GoalResponse
from farm_interfaces.action import ReturnToStation
from transport_robot.configuration import load_profile, require_execution
from transport_robot.docking_port import UnavailableDocking
from transport_robot.mission_types import Request
from transport_robot.transport_communication import TransportCommunication
from transport_robot.transport_mission import TransportMission
from transport_robot.transport_state_controller import TransportStateController


class EnvironmentTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def profile(self, mode='sim', **options):
        folder = self.root / ('sim' if mode == 'sim' else 'robot')
        folder.mkdir(exist_ok=True)
        for name in ('map.yaml', 'graph.json', 'nav.yaml'):
            (folder/name).write_text('{}')
        device = dict(robot_id='transport_01', map_id='test_map', model='waffle',
                      use_sim_time=mode == 'sim', hardware_configured=True)
        (folder/'device.json').write_text(json.dumps(device))
        (folder/'destinations.json').write_text(json.dumps(dict(mode=mode, map_id='test_map')))
        config = dict(schema_version=1, mode=mode, robot_id='transport_01', map_id='test_map',
            navigation=dict(mode='follow_path', tf_recovery_enabled=False), execution_enabled=True,
            device_config=str(folder/'device.json'), map_yaml=str(folder/'map.yaml'),
            nav_params=str(folder/'nav.yaml'), route_graph=str(folder/'graph.json'),
            destinations=str(folder/'destinations.json'), **options)
        env = folder/'environment.json'
        env.write_text(json.dumps(config))
        return load_profile(self.root, str(env), mode)

    def test_sim_return_without_hardware(self):
        profile = self.profile(station_return_mode='navigation_only')
        profile['device'].pop('hardware_configured')
        require_execution(profile)

    def test_real_default_still_requires_hardware(self):
        profile = self.profile('real')
        require_execution(profile)
        profile['device']['hardware_configured'] = False
        with self.assertRaises(ValueError):
            require_execution(profile)

    def test_real_cannot_skip_marker(self):
        with self.assertRaisesRegex(ValueError, 'sim에서만'):
            self.profile('real', station_return_mode='navigation_only')

    def test_invalid_return_policy(self):
        with self.assertRaises(ValueError):
            self.profile(station_return_mode='skip_everything')

    def test_sim_requires_clock(self):
        profile = self.profile()
        profile['device']['use_sim_time'] = False
        with self.assertRaises(ValueError):
            require_execution(profile)

    def test_no_unpermitted_traffic_fallback(self):
        with self.assertRaisesRegex(ValueError, '교통 허가'):
            self.profile(traffic={'enabled': True})


class ReturnTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.nav = Mock()
        self.mission = TransportMission(Path(self.temp.name)/'tasks.json')
        self.controller = TransportStateController(self.nav, self.mission, UnavailableDocking())
        self.controller.station_return_mode = 'navigation_only'
        self.events = []
        self.request = Request('R1', 'return', (2., 13.25), -1.57,
                               station_id='STATION_TRANSPORT_01')

    def tearDown(self):
        self.controller.cancel()
        self.until(lambda: not self.controller.busy)
        self.controller.close()
        self.temp.cleanup()

    def until(self, predicate):
        deadline = time.monotonic()+2.
        while not predicate() and time.monotonic() < deadline:
            self.controller.update()
            time.sleep(.001)
        self.assertTrue(predicate())

    def start(self):
        self.controller.start(self.request, self.events.append)

    def test_arrival_and_stop_precede_success(self):
        entered, release = threading.Event(), threading.Event()
        def navigate(*args):
            entered.set()
            if not release.wait(1.):
                raise TimeoutError('test navigation not released')
        self.nav.navigate.side_effect = navigate
        self.start()
        self.assertTrue(entered.wait(1.))
        self.controller.update()
        self.assertTrue(self.controller.busy)
        release.set()
        self.until(lambda: not self.controller.busy)
        result = self.controller.last_outcome
        self.assertEqual(result.result_code, 'SUCCESS')
        self.assertTrue(result.arrived and result.docked)
        self.assertEqual(self.events, ['RETURNING', 'ARRIVED'])
        stage = self.mission.records['R1']['stages'][-1]
        self.assertEqual(stage['detail'], 'marker_stage=SKIPPED_SIM_POLICY')

    def test_navigation_failure_is_failure(self):
        self.nav.navigate.side_effect = RuntimeError('FollowPath 105')
        self.start()
        self.until(lambda: not self.controller.busy)
        result = self.controller.last_outcome
        self.assertEqual(result.result_code, 'FAILED')
        self.assertFalse(result.arrived or result.docked)
        self.nav.cancel_nav.assert_called_once()

    def test_cancel_does_not_report_parking(self):
        entered = threading.Event()
        def navigate(*args):
            entered.set()
            self.controller._cancel.wait(1.)
            self.controller.check()
        self.nav.navigate.side_effect = navigate
        self.start()
        self.assertTrue(entered.wait(1.))
        self.controller.cancel()
        self.until(lambda: not self.controller.busy)
        self.assertEqual(self.controller.last_outcome.result_code, 'CANCELED')
        self.assertFalse(self.controller.last_outcome.docked)

    def test_default_return_and_pickup_still_need_docking(self):
        self.controller.station_return_mode = 'marker_docking'
        with self.assertRaises(ValueError):
            self.start()
        self.controller.station_return_mode = 'navigation_only'
        for kind in ('pickup', 'unload'):
            with self.assertRaises(ValueError):
                self.controller.start(Request(kind, kind, (0., 0.), 0.), self.events.append)

    def test_restart_contact_blocks_return(self):
        self.assertFalse(self.controller.docking.pending)
        self.mission.set_contact(True)
        restored = TransportMission(self.mission._journal)
        self.controller.blocked = restored.recovery_required
        with self.assertRaises(RuntimeError):
            self.start()

    def test_return_goal_without_marker_and_duplicate_rejected(self):
        communication = object.__new__(TransportCommunication)
        communication._lock = threading.Lock()
        communication._reservation = None
        communication._node = NS(stopping=False, controller=self.controller,
            mission=self.mission, docking=UnavailableDocking(), route_ready=lambda: True,
            profile=dict(robot_id='transport_01', map_id='farm_map_v1',
                station_return_mode='navigation_only', registry={'destinations':{
                    'STATION_TRANSPORT_01':dict(configured=True, approach_node_id=8003,
                                               approach_yaw_rad=-1.57)}}),
            graph=NS(nodes={8003:(2.,13.25)}), get_logger=Mock())
        goal = ReturnToStation.Goal(robot_id='transport_01', task_id='R1',
            station_id='STATION_TRANSPORT_01', map_id='farm_map_v1',
            timestamp='2026-10-27T18:00:00+09:00')
        self.assertEqual(communication._goal(goal, 'return'), GoalResponse.ACCEPT)
        self.assertEqual(communication._reservation.xy, (2.,13.25))
        self.assertEqual(communication._goal(goal, 'return'), GoalResponse.REJECT)


if __name__ == '__main__':
    unittest.main()
