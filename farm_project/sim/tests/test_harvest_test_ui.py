"""Isaac 없이 시험 UI의 요청 경계·배치 안전 조건·기존 ArmSession 계약을 검사한다.

가짜 장치에서는 물리를 실행하지 않는다. 메시지 수락 검사는 실제 ArmSession을
사용하며, 실제 60Hz 물리과 접촉·수확 결과는 별도 Isaac 시험 범위다.
"""
from copy import deepcopy
import json
import math
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import numpy as np


ROOT = Path(__file__).resolve().parents[2]
for package in ('farm_sim_runtime', 'farm_sim_devices'):
    sys.path.insert(0, str(ROOT / 'sim/ros_ws/src' / package))
from farm_sim_devices.arm_session import ArmSession
from farm_sim_runtime import harvest_test_ui as ui


class FakeDevice:
    """실제 측정값과 후보가 프레임 사이 바뀌는 장치를 표현한다."""

    def __init__(self, config: dict) -> None:
        self.config = config
        self.home = np.array([0., -1.39, .77, .62, .0488, 1.1])
        self.q, self.qd = self.home.copy(), np.zeros(6)
        self.targets = ['/Bed/red', '/Bed/yellow']
        self.exclusion_queries: list[frozenset[str]] = []
        self.command = Mock()

    def arm_world_transform(self) -> np.ndarray:
        return np.eye(4)

    def joint_positions(self) -> np.ndarray:
        return self.q.copy()

    def joint_velocities(self) -> np.ndarray:
        return self.qd.copy()

    def candidates(self, excluded: frozenset[str]) -> list[dict]:
        self.exclusion_queries.append(frozenset(excluded))
        return [dict(target_id=target) for target in self.targets if target not in excluded]


class FakeMatrix4d:
    """배치 시험에 필요한 USD 행벡터 행렬의 yaw quaternion 변환만 제공한다."""

    def __init__(self, *values: float) -> None:
        self.matrix = np.asarray(values).reshape(4, 4)

    def ExtractRotationQuat(self) -> SimpleNamespace:
        yaw = math.atan2(self.matrix[0, 1], self.matrix[0, 0])
        return SimpleNamespace(GetReal=lambda: math.cos(yaw / 2.),
                               GetImaginary=lambda: [0., 0., math.sin(yaw / 2.)])


class HarvestTestControllerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.profile = json.loads((ROOT / 'sim/ros_ws/src/farm_sim_config/config/teacher_policy.json').read_text())
        (self.root / 'survey.json').write_text(json.dumps({'sections': {'WEST': {'harvest_route': {}}}}))
        self.device = FakeDevice(self.profile['device'])
        self.articulation = SimpleNamespace(
            get_linear_velocity=Mock(return_value=np.zeros(3)),
            get_angular_velocity=Mock(return_value=np.zeros(3)),
            set_world_pose=Mock(), set_linear_velocity=Mock(), set_angular_velocity=Mock())
        self.base = SimpleNamespace(robot=self.articulation,
            pose=Mock(return_value=(np.zeros(3), np.array([1., 0., 0., 0.]))), command=Mock())
        self.attachments = SimpleNamespace(records=[{'prim_path': '/Bed/red'}],
            attached=np.array([True]), active=np.array([False]), paths=['/Bed/red'],
            current_positions=Mock(return_value=np.array([[3., 4., 1.]])))
        self.physics = SimpleNamespace(adaptive=True,
            regions=SimpleNamespace(settings=SimpleNamespace(idle_hz=60, harvest_hz=60)),
            profile={'render_hz': 30, 'survey_config': 'survey.json'},
            directory=self.root / 'physics', attachments=self.attachments, set_activity=Mock(),
            arm_reports={'/Robot': {'home_positions_rad': self.device.home.tolist()}})
        self.device.robot_path = '/Robot'
        self.device.escaped_deposits = Mock(return_value=[])
        self.home_initializer = patch('farm_sim_runtime.harvest_physics.initialize_arm_home')
        self.initialize_home = self.home_initializer.start()
        self.addCleanup(self.home_initializer.stop)
        self.arm = ArmSession('offline-session', 'harvester', 'test-map', self.device, Mock(),
                              self.physics, self.profile['session'], self.root / 'teacher')
        self.addCleanup(self.arm.close)
        self.arm.accept = Mock(wraps=self.arm.accept)
        self.robot = dict(arm=self.arm, arm_device=self.device, base=self.base, gate=SimpleNamespace(stop=Mock()),
                          T_asset_control=np.eye(4), arm_profile=self.profile, cfg={'map_yaml': 'offline.yaml'})
        self.task = {'evaluation': {'T_map_world': np.eye(4).tolist()},
                     'harvest_robot': {'scene_snapshot_file': str(self.root / 'run/snapshot.json')}}
        self.clearance = Mock(return_value=True)
        self.clearance_loader = patch.object(ui, 'load_clearance_check', return_value=self.clearance)
        self.clearance_loader.start()
        self.addCleanup(self.clearance_loader.stop)
        self.controller = ui.HarvestTestController(self.robot, self.physics, self.task, self.root, seed=7)
        self.addCleanup(self.controller.close)
        self.placement = dict(section_id='WEST', source_target_id='/Bed/red', target_ids=['/Bed/red'],
            x=3., y=4., yaw=math.pi / 2., target_world_m=[3., 4., 1.],
            T_world_base=[[0., -1., 0., 3.], [1., 0., 0., 4.], [0., 0., 1., .2], [0., 0., 0., 1.]])

    def events(self) -> list[dict]:
        """컨트롤러가 실제로 기록한 이벤트를 읽는다."""
        return [json.loads(line) for line in (self.root / 'run/ui_events.jsonl').read_text().splitlines()]

    def make_ready(self) -> None:
        """기존 배치에서 0.5초 연속 정지를 관측한다."""
        self.controller.placement = deepcopy(self.placement)
        self.controller.after_frame(10., 60.)
        self.controller.after_frame(10.5, 60.)
        self.assertTrue(self.controller.ready)

    def harvest(self) -> None:
        """수확 버튼과 재생 중 프레임 경계를 거친다."""
        self.controller.request('harvest')
        self.controller.before_frame(10.6, playing=True)

    def test_callbacks_only_queue_one_request_and_do_not_mutate_physics(self) -> None:
        self.controller.request('unknown')
        self.assertEqual(self.controller.pending, '')
        for action in ('place', 'place', 'harvest', 'cancel'):
            self.controller.request(action)
        self.assertEqual(self.controller.pending, 'place')
        self.arm.accept.assert_not_called()
        self.base.command.assert_not_called()
        self.articulation.set_world_pose.assert_not_called()
        self.physics.set_activity.assert_not_called()
        self.device.command.assert_not_called()
        self.assertEqual([event['event'] for event in self.events()], ['OPEN'])

    def test_paused_frames_drop_requests_and_require_a_new_settling_interval(self) -> None:
        self.make_ready()
        for action in ('place', 'harvest'):
            with self.subTest(action=action), patch.object(ui, 'find_placements') as placements:
                self.controller.request(action)
                self.controller.before_frame(10.6, playing=False)
                placements.assert_not_called()
                self.assertFalse(self.controller.ready)
                self.assertIsNone(self.controller.stable_since)
                self.assertEqual(self.controller.pending, '')
        self.articulation.set_world_pose.assert_not_called()
        self.arm.accept.assert_not_called()
        self.controller.after_frame(11., 60.)
        self.assertFalse(self.controller.ready)
        self.controller.after_frame(11.5, 60.)
        self.assertTrue(self.controller.ready)

    def test_busy_and_unsafe_arm_block_placement(self) -> None:
        self.assertTrue(self.controller.can_place)
        for state, deposited in (({'status': 'RUNNING'}, set()),
                                 ({'safe_stopped': False}, set())):
            with self.subTest(state=state, deposited=deposited):
                saved = dict(self.arm.state)
                self.arm.state.update(state)
                self.arm._successful_ids = deposited
                self.controller.request('place')
                with patch.object(ui, 'find_placements') as placements:
                    self.controller.before_frame(1., playing=True)
                    placements.assert_not_called()
                self.assertEqual(self.events()[-1]['event'], 'REJECTED')
                self.assertFalse(self.controller.can_place)
                self.arm.state = saved
                self.arm._successful_ids = set()
        self.articulation.set_world_pose.assert_not_called()

    def test_motion_and_nonfinite_measurements_block_placement(self) -> None:
        cases = ('linear', 'angular', 'joint_position', 'joint_velocity', 'nan_linear', 'nan_joint')
        for condition in cases:
            with self.subTest(condition=condition):
                self.articulation.get_linear_velocity.return_value = np.zeros(3)
                self.articulation.get_angular_velocity.return_value = np.zeros(3)
                self.device.q, self.device.qd = self.device.home.copy(), np.zeros(6)
                if condition == 'linear':
                    self.articulation.get_linear_velocity.return_value[0] = .02
                elif condition == 'angular':
                    self.articulation.get_angular_velocity.return_value[2] = .04
                elif condition == 'joint_position':
                    self.device.q[0] += .07
                elif condition == 'joint_velocity':
                    self.device.qd[0] = .6
                elif condition == 'nan_linear':
                    self.articulation.get_linear_velocity.return_value[0] = np.nan
                else:
                    self.device.q[0] = np.nan
                self.assertEqual(self.controller.can_place, condition == 'joint_position')
                self.assertFalse(self.controller.can_harvest)

    def test_readiness_requires_candidates_and_uninterrupted_stationary_half_second(self) -> None:
        self.controller.after_frame(1., 60.)
        self.assertFalse(self.controller.ready)
        self.controller.placement = self.placement
        self.controller.after_frame(2., 60.)
        self.controller.after_frame(2.49, 60.)
        self.assertFalse(self.controller.ready)
        self.device.qd[0] = 1.
        self.controller.after_frame(2.5, 60.)
        self.assertIsNone(self.controller.stable_since)
        self.device.qd[0] = 0.
        self.controller.after_frame(3., 60.)
        self.controller.after_frame(3.5, 60.)
        self.assertTrue(self.controller.ready)
        self.device.targets = []
        self.controller.after_frame(3.6, 60.)
        self.assertFalse(self.controller.ready)
        self.assertIsNone(self.controller.stable_since)

    def test_start_uses_real_arm_contract_and_fresh_excluded_candidate_count(self) -> None:
        self.make_ready()
        self.assertEqual(len(self.controller.candidates), 2)
        self.arm._all_attempted.add('/Bed/red')
        self.device.targets.extend(['/Bed/red2', '/Bed/red3'])
        self.harvest()
        message = self.arm.accept.call_args.args[0]
        self.assertEqual(self.arm.state['status'], 'RUNNING')
        self.assertEqual(self.arm.state['stage'], 'PREPARE')
        self.assertEqual(message['kind'], 'harvest_arm')
        self.assertEqual(message['op'], 'start')
        self.assertEqual(message['session'], self.arm.session)
        self.assertEqual(message['robot_id'], self.arm.robot_id)
        self.assertEqual(message['map_id'], self.arm.map_id)
        self.assertEqual(message['window_id'], 'WEST')
        self.assertEqual(message['expected_count'], 3)
        self.assertEqual(message['goal_pose'], {'x': 3., 'y': 4., 'yaw': math.pi / 2.})
        self.assertEqual(message['task_id'], 'harvest_test_ui_' + message['job_id'])
        self.assertRegex(message['job_id'], r'^[0-9a-f]{32}$')
        self.assertEqual(message['sent'], self.arm.accept.call_args.kwargs['now'])
        self.assertFalse(self.controller.ready)
        self.assertEqual(self.device.exclusion_queries[-1], frozenset({'/Bed/red'}))
        self.assertEqual(self.events()[-1]['candidate_ids'], ['/Bed/yellow', '/Bed/red2', '/Bed/red3'])
        self.physics.set_activity.assert_not_called()
        self.device.command.assert_not_called()

    def test_stale_ready_state_cannot_start_without_current_candidates_or_stationarity(self) -> None:
        for condition in ('no_candidates', 'moving', 'unsafe', 'busy', 'not_home'):
            with self.subTest(condition=condition):
                self.device.targets = ['/Bed/red']
                self.device.q = self.device.home.copy()
                self.device.qd[:] = 0.
                self.arm.state.update(status='IDLE', safe_stopped=True, job_id='')
                self.make_ready()
                if condition == 'no_candidates':
                    self.device.targets = []
                elif condition == 'moving':
                    self.device.qd[0] = 1.
                elif condition == 'unsafe':
                    self.arm.state['safe_stopped'] = False
                elif condition == 'not_home':
                    self.device.q[0] += .2
                else:
                    self.arm.state['status'] = 'RUNNING'
                self.arm.accept.reset_mock()
                self.harvest()
                self.assertFalse(any(call.args[0]['op'] == 'start' for call in self.arm.accept.call_args_list))
                self.assertEqual(self.events()[-1]['event'], 'REJECTED')

    def test_running_session_gets_valid_heartbeat_and_cancel_without_fake_completion(self) -> None:
        self.make_ready()
        self.harvest()
        job = self.arm.state['job_id']
        self.arm.accept.reset_mock()
        self.controller.before_frame(11., playing=False)
        self.assertEqual(self.arm.accept.call_args.args[0]['op'], 'keepalive')
        self.controller.request('cancel')
        self.controller.before_frame(11.1, playing=True)
        calls = [call.args[0] for call in self.arm.accept.call_args_list]
        self.assertEqual([message['op'] for message in calls], ['keepalive', 'keepalive', 'cancel'])
        self.assertTrue(all(message['job_id'] == job for message in calls))
        self.assertEqual(len({message['seq'] for message in calls}), len(calls))
        self.assertTrue(self.arm._pending_cancel)
        self.assertEqual(self.arm.state['status'], 'RUNNING')
        self.assertEqual(self.events()[-1]['event'], 'CANCEL')
        self.device.command.assert_not_called()

    def test_arm_rejection_does_not_log_a_harvest_or_claim_to_be_running(self) -> None:
        self.make_ready()
        self.arm.accept.return_value = False
        self.harvest()
        self.assertEqual(self.arm.state['status'], 'IDLE')
        self.assertEqual(self.events()[-1]['event'], 'REJECTED')
        self.assertNotIn('HARVEST', [event['event'] for event in self.events()])
        self.assertIn('rejected', self.controller.notice)
        self.physics.set_activity.assert_not_called()

    def test_zero_deposit_completion_remains_explicitly_zero_in_notice_and_log(self) -> None:
        self.make_ready()
        self.harvest()
        self.arm.state.update(status='SUCCESS', stage='DONE', success_count=0, failed_count=2,
                              safe_stopped=True, event_seq=1)
        self.controller.after_frame(20., 60.)
        self.assertIn('Job SUCCESS', self.controller.notice)
        self.assertIn('Deposited 0 / Failed 2', self.controller.notice)
        self.assertNotIn('Harvest succeeded', self.controller.notice)
        event = self.events()[-1]
        self.assertEqual(event['arm']['success_count'], 0)
        self.assertEqual(event['arm']['failed_count'], 2)
        self.assertEqual(event['physics_hz'], 60.)

    def test_missing_placements_reject_without_touching_robot_and_pass_exclusions(self) -> None:
        self.controller.placement = self.placement
        self.arm._all_attempted.add('/Bed/red')
        self.controller.request('place')
        with patch.object(ui, 'find_placements', return_value=[]) as placements:
            self.controller.before_frame(1., playing=True)
        self.assertEqual(placements.call_args.args[3], frozenset({'/Bed/red'}))
        self.assertIs(placements.call_args.kwargs['pose_is_clear'], self.clearance)
        self.assertIsNone(self.controller.placement)
        self.assertFalse(self.controller.ready)
        self.articulation.set_world_pose.assert_not_called()
        self.assertEqual(self.events()[-1]['event'], 'REJECTED')

    def test_placement_moves_whole_asset_and_preserves_fruit_and_joint_state(self) -> None:
        self.controller.placement = deepcopy(self.placement)
        alternative = dict(self.placement, source_target_id='/Bed/yellow')
        self.robot['T_asset_control'][0, 3] = .3
        before_joints, before_attached = self.device.q.copy(), self.attachments.attached.copy()
        self.controller.request('place')
        pxr = SimpleNamespace(Gf=SimpleNamespace(Matrix4d=FakeMatrix4d))
        with patch.dict(sys.modules, {'pxr': pxr}), \
                patch.object(ui, 'find_placements', return_value=[self.placement, alternative]):
            self.controller.before_frame(1., playing=True)
        self.assertIs(self.controller.placement, alternative)
        placed = self.articulation.set_world_pose.call_args.kwargs
        np.testing.assert_allclose(placed['position'], [3., 3.7, .2])
        np.testing.assert_allclose(placed['orientation'], [math.sqrt(.5), 0., 0., math.sqrt(.5)])
        self.robot['gate'].stop.assert_called_once()
        self.base.command.assert_called_once_with(0., 0.)
        np.testing.assert_array_equal(self.articulation.set_linear_velocity.call_args.args[0], np.zeros(3))
        np.testing.assert_array_equal(self.articulation.set_angular_velocity.call_args.args[0], np.zeros(3))
        self.assertEqual(self.robot['initial_z'], .2)
        self.initialize_home.assert_called_once_with(self.articulation, self.physics.arm_reports['/Robot'])
        self.assertFalse(self.controller.ready)
        np.testing.assert_array_equal(self.device.q, before_joints)
        np.testing.assert_array_equal(self.attachments.attached, before_attached)
        self.device.command.assert_not_called()
        self.assertEqual(self.events()[-1]['event'], 'PLACE')

    def test_stopped_non_home_arm_can_place_and_prepare_another_harvest(self) -> None:
        self.make_ready()
        self.harvest()
        self.device.q[0] += .2
        self.arm.state.update(status='CANCELED', stage='DONE', safe_stopped=True)
        self.controller.after_frame(20., 60.)
        self.assertTrue(self.controller.can_place)
        self.assertFalse(self.controller.ready)
        self.assertIn('Click Place robot', self.controller.notice)

        def initialize_home(articulation: object, report: dict) -> None:
            self.device.q = np.asarray(report['home_positions_rad'])

        self.initialize_home.side_effect = initialize_home
        self.controller.request('place')
        with patch.dict(sys.modules, {'pxr': SimpleNamespace(Gf=SimpleNamespace(Matrix4d=FakeMatrix4d))}), \
                patch.object(ui, 'find_placements', return_value=[self.placement]):
            self.controller.before_frame(21., playing=True)
        self.controller.after_frame(21.1, 60.)
        self.controller.after_frame(21.6, 60.)
        self.assertTrue(self.controller.ready)
        self.harvest()
        self.assertEqual(self.arm.state['status'], 'RUNNING')

    def test_successful_deposit_moves_with_next_placement_without_changing_result(self) -> None:
        self.arm.state.update(status='SUCCESS', stage='DONE', success_count=1, safe_stopped=True)
        self.arm._successful_ids = {'/Bed/previous'}
        self.arm._all_attempted = {'/Bed/previous'}
        self.attachments.paths.append('/Bed/previous')
        self.attachments.attached = np.array([True, False])
        self.attachments.view = SimpleNamespace(
            get_world_poses=Mock(return_value=(np.array([[1., 0., .3]]), np.array([[1., 0., 0., 0.]]))),
            get_velocities=Mock(return_value=np.array([[1., 0., 0., 0., 1., 0.]])),
            set_world_poses=Mock(), set_velocities=Mock())
        self.assertTrue(self.controller.can_place)
        self.controller.request('place')
        with patch.dict(sys.modules, {'pxr': SimpleNamespace(Gf=SimpleNamespace(Matrix4d=FakeMatrix4d))}), \
                patch.object(ui, 'find_placements', return_value=[self.placement]):
            self.controller.before_frame(21., playing=True)
        pose = self.attachments.view.set_world_poses.call_args.kwargs
        np.testing.assert_allclose(pose['positions'], [[3., 5., .5]])
        np.testing.assert_allclose(pose['orientations'], [[math.sqrt(.5), 0., 0., math.sqrt(.5)]])
        np.testing.assert_array_equal(pose['indices'], [1])
        np.testing.assert_allclose(self.attachments.view.set_velocities.call_args.args[0], [[0., 1., 0., -1., 0., 0.]])
        np.testing.assert_array_equal(self.attachments.attached, [True, False])
        self.assertEqual(self.arm.deposited_target_ids, frozenset({'/Bed/previous'}))
        self.assertEqual(self.arm.attempted_target_ids, frozenset({'/Bed/previous'}))
        self.assertEqual(self.arm.state['success_count'], 1)
        self.assertEqual(self.events()[-1]['transported_deposit_ids'], ['/Bed/previous'])
        self.controller.after_frame(21.1, 60.)
        self.controller.after_frame(21.6, 60.)
        self.assertTrue(self.controller.ready)

    def test_new_placement_clears_previous_terminal_notice(self) -> None:
        self.make_ready()
        self.harvest()
        self.arm.state.update(status='SUCCESS', stage='DONE', success_count=0, failed_count=2, safe_stopped=True)
        self.controller.after_frame(20., 60.)
        self.controller.request('place')
        with patch.dict(sys.modules, {'pxr': SimpleNamespace(Gf=SimpleNamespace(Matrix4d=FakeMatrix4d))}), \
                patch.object(ui, 'find_placements', return_value=[self.placement]):
            self.controller.before_frame(21., playing=True)
        self.controller.after_frame(21.1, 60.)
        self.assertNotIn('Job SUCCESS', self.controller.notice)
        self.controller.after_frame(21.6, 60.)
        self.assertTrue(self.controller.ready)
        self.assertIn('Click Harvest', self.controller.notice)

    def test_physics_only_activates_local_physics_without_policy_or_teleport(self) -> None:
        self.make_ready()
        self.controller.request('physics')
        self.controller.before_frame(10.6, playing=True)
        self.assertTrue(self.controller.physics_only)
        self.physics.set_activity.assert_called_once_with('harvester', True)
        self.assertFalse(self.controller.can_place)
        self.assertFalse(self.controller.ready)
        self.arm.accept.assert_not_called()
        self.articulation.set_world_pose.assert_not_called()
        self.device.command.assert_not_called()
        self.controller.request('harvest')
        self.controller.before_frame(10.7, playing=True)
        self.arm.accept.assert_not_called()
        self.controller.request('physics')
        self.controller.before_frame(10.8, playing=True)
        self.assertFalse(self.controller.physics_only)
        self.physics.set_activity.assert_called_with('harvester', False)
        self.assertEqual(self.events()[-1]['event'], 'PHYSICS_ONLY')

    def test_physics_only_requires_placement_and_never_overrides_busy_arm(self) -> None:
        self.controller.request('physics')
        self.controller.before_frame(1., playing=True)
        self.physics.set_activity.assert_not_called()
        self.make_ready()
        self.harvest()
        self.controller.request('physics')
        self.controller.before_frame(10.7, playing=True)
        self.physics.set_activity.assert_not_called()
        self.assertFalse(self.controller.physics_only)


if __name__ == '__main__':
    unittest.main()
