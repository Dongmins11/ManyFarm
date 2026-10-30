"""영상 제어와 평가 ID 분리, 실적 집계·정상 완료를 검증한다."""
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
import tempfile
import json
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'ros_ws/src/farm_sim_devices'))
from unittest.mock import Mock, patch
from farm_sim_devices.student_session import map_outcomes, StudentArmSession, mission_session


class StudentAssignmentTests(unittest.TestCase):
    def test_mount_drift_still_fails_and_records_measured_transform(self):
        import numpy as np
        arm = object.__new__(StudentArmSession)
        arm.state = dict(stage='TO_HOME')
        arm._fault = ''
        arm._pending_cancel = False
        arm._lease = 0.
        arm.config = dict(lease_s=2., base_drift_limit_m=.02, base_yaw_drift_limit_rad=.05)
        arm._dock_arm = np.eye(4)
        moved = np.eye(4);moved[0, 3] = .021
        arm.device = SimpleNamespace(arm_world_transform=lambda: moved)
        arm._stop, arm._log = Mock(), Mock()
        arm._tick(1., True, 1.)
        arm._stop.assert_called_once_with(1., 'FAILED', 'STUDENT_SUPERVISOR_FAULT', 'right_arm_mount_moved_from_dock')
        self.assertAlmostEqual(arm._log.call_args.kwargs['dock_displacement_m'], .021)
        self.assertEqual(arm._log.call_args.kwargs['translation_limit_m'], .02)

    def test_keeps_camera_coordinates_and_ids(self):
        target = SimpleNamespace(target_id='camera-id', label='Red', anchor_arm_m=(.3, 0., .2))
        original = target.anchor_arm_m
        candidates = [dict(target_id='/fruit', color='red', root_arm_m=[.31, 0, .2])]
        self.assertEqual(map_outcomes([target], candidates, .06, .02), {'camera-id': '/fruit'})
        self.assertEqual(target.anchor_arm_m, original)

    def test_missing_or_ambiguous_mapping_is_unresolved_without_rejecting_camera(self):
        target = SimpleNamespace(target_id='camera-id', label='Red', anchor_arm_m=(.3, 0., .2))
        self.assertEqual(map_outcomes([target], [], .06, .02), {'camera-id': None})
        candidates = [dict(target_id=str(i), color='red', root_arm_m=[.3+i*.01, 0, .2]) for i in range(2)]
        self.assertEqual(map_outcomes([target], candidates, .06, .02), {'camera-id': None})

    def test_duplicate_evaluation_id_is_not_arbitrarily_assigned(self):
        targets = [SimpleNamespace(target_id=str(i), label='Red', anchor_arm_m=(.3, 0., .2)) for i in range(2)]
        candidates = [dict(target_id='/fruit', color='red', root_arm_m=[.3, 0, .2])]
        self.assertEqual(map_outcomes(targets, candidates, .06, .02), {'0': None, '1': None})


class StudentGravityTests(unittest.TestCase):
    def test_gravity_sort_frame_does_not_change_policy_contract(self):
        import numpy as np
        camera = SimpleNamespace(contract=dict(box_from_arm=np.eye(4).tolist()), start=Mock(), step=Mock(), acknowledge=Mock())
        frame = np.array([[0,0,1,2],[0,1,0,3],[-1,0,0,1],[0,0,0,1]], float)
        adapter = mission_session(camera, frame)
        np.testing.assert_array_equal(camera.contract['box_from_arm'], np.eye(4))
        np.testing.assert_array_equal(adapter.contract['box_from_arm'], frame)
        self.assertIs(adapter.step, camera.step)
        first = (np.asarray(adapter.contract['box_from_arm']) @ [.3,0,.1,1])[2]
        second = (np.asarray(adapter.contract['box_from_arm']) @ [.5,0,.15,1])[2]
        self.assertLess(second, first)


class StudentBoxEvidenceTests(unittest.TestCase):
    def test_coordinates_inside_box_cannot_create_success(self):
        import numpy as np
        arm = object.__new__(StudentArmSession)
        arm._reset_window_metrics()
        sample = dict(fruit_position=np.array([.5,.5,.5]), fruit_quaternion=np.array([1.,0.,0.,0.]),
            fruit_linear_velocity=np.zeros(3), collision_vertices=np.array([[-.05,-.05,-.05],[.05,.05,.05]]),
            fixed_force=np.zeros(3), moving_force=np.zeros(3), fixed_net_force=np.zeros(3), moving_net_force=np.zeros(3), attached=False)
        arm.device = SimpleNamespace(sample=lambda: sample)
        arm.controller = SimpleNamespace(contract=dict(task=dict(box_min=[0,0,0], box_max=[1,1,1],
            sequence=False, box_contact_tolerance=.003, box_bottom_contact_tolerance=.01,
            contact_threshold=.08, max_contact_force=25., place_hold_s=.6)))
        arm._physical_target, arm._fault = '/fruit', ''
        arm._successful_ids = set()
        arm._box_evidence = None
        arm.mission = SimpleNamespace(target=SimpleNamespace(target_id='camera-fruit'))
        arm._log = Mock()
        arm._update_box(1/60, 1.)
        self.assertIsNone(arm._box_evidence)
        sample['fruit_position'][1] = 1.2
        arm._update_box(1/60, 1.+1/60)
        self.assertIsNone(arm._box_evidence)
        sample['fruit_position'][2] = .2
        arm._update_box(1/60, 2.)
        arm._update_box(1/60, 3.)
        self.assertEqual(arm._fault, '')
        self.assertEqual([e['reason'] for e in arm._performance_events], ['target_dropped_below_box'])

    def test_anonymous_passage_counts_without_position_or_identity_input(self):
        arm = object.__new__(StudentArmSession)
        arm._reset_window_metrics()
        arm._physical_target, arm._laser_armed = '/active-attempt', True
        arm._successful_ids, arm._attempts = set(), []
        arm.state = dict(success_count=0, event_seq=0)
        arm.mission = SimpleNamespace(target=SimpleNamespace(target_id='camera-attempt'))
        arm._log = Mock()
        event = dict(sequence=1, stamp_s=3., entered_s=2.8, beams_seen=[1, 2], direction_confirmed=False,
                     source='basket_parallel_lasers', identity_confirmed=False)
        arm._record_laser_passage(event)
        self.assertEqual(arm.state['success_count'], 1)
        self.assertFalse(arm._attempts[0]['identity_confirmed'])
        self.assertNotIn('physical_in_box', arm._attempts[0])
        self.assertEqual(arm._box_evidence['source'], 'basket_parallel_lasers')
        self.assertEqual(arm.lost_deposits(), [])
        with self.assertRaises(RuntimeError): arm._record_laser_passage(event)
        self.assertEqual(arm.state['success_count'], 1)


class StudentCompletionTests(unittest.TestCase):
    def test_stop_disarms_sensor_and_preserves_completed_counts(self):
        from farm_sim_devices.arm_session import ArmSession
        from farm_sim_devices.basket_laser import PassageCounter
        arm = object.__new__(StudentArmSession)
        arm._reset_window_metrics()
        counter = PassageCounter(.05, 2.)
        counter.arm()
        arm.controller = SimpleNamespace(basket_sensor=SimpleNamespace(counter=counter),
            rig=SimpleNamespace(set_active=Mock()))
        arm._laser_armed = True
        arm.state = dict(success_count=1)
        with patch.object(ArmSession, '_stop'):
            arm._stop(5., 'CANCELED', '', 'operator_cancel')
        self.assertFalse(arm._laser_armed)
        self.assertEqual(counter.state, 'DISARMED')
        self.assertIsNone(counter.update([True, True, True], 5.1))
        self.assertEqual(arm.state['success_count'], 1)

    def test_outer_stop_failure_keeps_deposit_but_rejects_mission_completion(self):
        from farm_sim_devices.arm_session import ArmSession
        arm = object.__new__(StudentArmSession)
        arm._reset_window_metrics()
        arm._physical_target = None
        arm.job = dict(window_id='W001', expected_count=1)
        arm.state = dict(success_count=1, failed_count=0)
        arm.mission = SimpleNamespace(report=lambda: dict(mission_complete=True, harvest_successes=1))
        arm.controller = SimpleNamespace(rig=SimpleNamespace(sequence=30, max_fk_error=0., set_active=Mock()), config={})
        with tempfile.TemporaryDirectory() as folder:
            arm._directory = Path(folder)
            with patch.object(ArmSession, '_finish'):
                arm._finish(1., 'FAILED', 'CANCEL_UNCONFIRMED', 'measured_stop_not_confirmed', safe=False)
            result = json.loads((arm._directory/'student_mission.json').read_text())
        self.assertFalse(result['mission_complete'])
        self.assertTrue(result['controller_mission_complete'])
        self.assertEqual(result['harvest_successes'], 1)
        self.assertEqual(result['session_status'], 'FAILED')


class PassageFeedbackTests(unittest.TestCase):
    def test_partial_or_zero_result_keeps_advisory_expected_count(self):
        from test_arm_ros import ArmRosTests
        for actual, missed in ((0, 0), (1, 0), (2, 0), (1, 2)):
            with self.subTest(actual=actual, missed=missed):
                bridge = ArmRosTests()
                bridge.setUp()
                def peer(message):
                    if message['op'] == 'start':
                        bridge.observe()
                    elif message['op'] == 'keepalive':
                        bridge.observe('SUCCESS', counts=(actual, missed))
                bridge.hook = peer
                self.assertTrue(bridge.server.accept(bridge.handle.request))
                result = bridge.server.execute(bridge.handle)
                self.assertEqual(result.expected_count, 9)
                self.assertEqual((result.result_code, result.harvested_count, result.failed_count),
                                 ('SUCCESS', actual, missed))

    def test_three_beam_passage_reaches_feedback_and_result_once(self):
        from farm_sim_devices.basket_laser import PassageCounter
        from test_arm_ros import ArmRosTests
        bridge = ArmRosTests()
        bridge.setUp()
        arm = object.__new__(StudentArmSession)
        arm._reset_window_metrics()
        arm._physical_target, arm._laser_armed = '/active-attempt', True
        arm._successful_ids, arm._attempts = set(), []
        arm.state = bridge.state()
        arm.mission = SimpleNamespace(target=SimpleNamespace(target_id='camera-attempt'))
        arm._log = Mock()
        counter = PassageCounter(.05, 2.)
        counter.arm()

        def peer(message):
            if message['op'] == 'start':
                # 세 빔 동시 차단에도 레이저 → 세션 → 서버 누적량은 한 개다.
                for now, blocked in [(0., [False]*3), (.06, [False]*3),
                                     (.1, [True]*3), (.15, [False]*3), (.21, [False]*3)]:
                    event = counter.update(blocked, now)
                    if event is not None: arm._record_laser_passage(event)
                bridge.server.observe('session', arm.state)
            elif message['op'] == 'keepalive':
                bridge.server.observe('session', dict(arm.state, status='SUCCESS', safe_stopped=True))

        bridge.hook = peer
        self.assertTrue(bridge.server.accept(bridge.handle.request))
        result = bridge.server.execute(bridge.handle)
        self.assertEqual(bridge.handle.feedbacks, [(0, 0), (1, 0)])
        self.assertEqual((result.result_code, result.harvested_count, result.failed_count), ('SUCCESS', 1, 0))
        self.assertEqual(len(arm._attempts), 1)


class StudentInventoryTests(unittest.TestCase):
    def test_camera_workspace_targets_are_independent_of_scout_count(self):
        root = Path(__file__).resolve().parents[2]
        sys.path.insert(0, str(root/'sim/assets/robotarm_student/manyfarm_robotarm/src/harvest_robot'))
        for expected, count, inside in ((1, 0, True), (1, 1, False), (3, 1, True),
                                        (1, 2, True), (0, 1, True)):
            with self.subTest(expected=expected, visible=count, inside=inside):
                arm = object.__new__(StudentArmSession)
                arm._reset_window_metrics()
                arm.controller = SimpleNamespace(
                    rig=SimpleNamespace(last=True, capture=lambda: {}),
                    camera=SimpleNamespace(roi=[[-1]*3, [1]*3], observe=lambda c, t: ({}, [])),
                    profile=dict(inventory_timeout_s=3., assignment_gate_m=.06, assignment_ambiguity_m=.02),
                    config={}, kin=Mock(), contract={})
                arm.job = dict(expected_count=expected)
                arm._directory = None
                arm._inventory_start = 0.
                arm._log, arm._stop = Mock(), Mock()
                arm._all_attempted = set()
                arm._successful_ids = set()
                arm._dock_arm = None
                arm.state = dict(success_count=0, failed_count=0)
                arm.device = SimpleNamespace(candidates=Mock(return_value=[]),
                    config=dict(workspace_arm_min_m=[0, -1, -1], workspace_arm_max_m=[1, 1, 1],
                                home_tcp_arm_m=[0, 0, 0], near_home_min_m=.09, near_home_max_m=1.))
                tracks = {str(i): dict(valid=True, label='Red', position_m=[.3, 0 if inside else 1.1, .2])
                          for i in range(count)}
                tracker = SimpleNamespace(update=lambda d, t: None, snapshot=lambda t: tracks)
                with patch('harvest_vision.student60_tracking.AssignedFruitTracker', return_value=tracker), \
                        patch('farm_sim_devices.student_session.map_outcomes',
                              return_value={str(i): '/fruit'+str(i) for i in range(count)}) as mapping, \
                        patch('farm_sim_devices.student_session.mission_session'), \
                        patch('harvest_runtime.student60_mission.StudentHarvestMission') as mission:
                    arm._inventory(1.)
                    mission.assert_not_called()
                    arm._stop.assert_not_called()
                    arm.device.candidates.assert_not_called()
                    mission.return_value.targets = [SimpleNamespace(target_id=str(i)) for i in range(count)]
                    arm._inventory(3.1)
                self.assertEqual(arm.job['expected_count'], expected)
                self.assertEqual((arm.state['success_count'], arm.state['failed_count']), (0, 0))
                if count and inside:
                    arm._stop.assert_not_called()
                    self.assertEqual(len(mission.call_args.args[1]), count)
                    self.assertTrue(mission.call_args.kwargs['task_list_complete'])
                    self.assertEqual(arm.state['stage'], 'STOW_WAIT')
                else:
                    self.assertEqual(arm._stop.call_args.args[1:],
                        ('SUCCESS', '', 'student_no_reachable_targets_arms_stowed'))
                    arm.device.candidates.assert_not_called()
                    mission.assert_not_called()
                    mapping.assert_not_called()


if __name__ == '__main__':
    unittest.main()
