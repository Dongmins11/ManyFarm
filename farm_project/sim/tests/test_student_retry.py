"""실제 미션/세션 FSM으로 카메라 재관측·1회 재시도·레이저·물리 복귀를 검증한다."""
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'sim/ros_ws/src/farm_sim_devices'))
sys.path.insert(0, str(ROOT/'sim/assets/robotarm_student/manyfarm_robotarm/src/harvest_robot'))
from farm_sim_devices.student_session import StudentArmSession, mission_session
from harvest_runtime.student60 import encode_command


class StudentRetryTests(unittest.TestCase):
    def test_camera_prepare_error_uses_existing_arm_fault_handler(self):
        session = StudentArmSession.__new__(StudentArmSession)
        error = RuntimeError('sensor pose read failed')
        session.controller = SimpleNamespace(rig=SimpleNamespace(
            active=True, set_active=Mock(), prepare_capture=Mock(side_effect=error)))
        session.state = dict(status='RUNNING', stage='HARVEST')
        session._handle_error = Mock()
        session.prepare_capture(1.)
        session._handle_error.assert_called_once_with(1., error)
        session.state['status'] = 'IDLE'
        with self.assertRaises(RuntimeError):
            session.prepare_capture(2.)

    def test_return_pauses_camera_and_retry_inventory_resumes(self):
        session = StudentArmSession.__new__(StudentArmSession)
        rig = SimpleNamespace(active=True, prepare_capture=Mock())
        def set_active(active, *, reset_capture):
            self.assertFalse(reset_capture)
            rig.active = active
        rig.set_active = Mock(side_effect=set_active)
        session.controller = SimpleNamespace(rig=rig)
        session.state = dict(status='RUNNING', stage='RETURN_STOW')
        session.prepare_capture(1.)
        self.assertFalse(rig.active)
        session.state['stage'] = 'FINAL_STOP'
        session.prepare_capture(2.)
        self.assertEqual(rig.set_active.call_count, 1)
        session.state['stage'] = 'CAMERA_INVENTORY'
        session.prepare_capture(3.)
        self.assertTrue(rig.active)
        session.state['stage'] = 'HARVEST'
        session.prepare_capture(4.)
        self.assertEqual(rig.set_active.call_count, 2)

    def test_only_inventory_and_visual_policy_stages_enable_camera(self):
        session = StudentArmSession.__new__(StudentArmSession)
        rig = SimpleNamespace(active=False)
        def set_active(active, *, reset_capture):
            rig.active = active
        rig.set_active = Mock(side_effect=set_active)
        session.controller = SimpleNamespace(rig=rig)
        for status in ('RUNNING', 'IDLE', 'STOPPING'):
            for stage in ('CAMERA_INVENTORY','HARVEST','WAIT_BOX','PREPARE',
                          'STOW_WAIT','TO_HOME','RETURN_STOW','FINAL_STOP','STOPPING','DONE'):
                with self.subTest(status=status, stage=stage):
                    session.state = dict(status=status,stage=stage)
                    session._sync_camera_activity()
                    self.assertEqual(rig.active, status == 'RUNNING' and stage in
                                     ('CAMERA_INVENTORY','HARVEST','WAIT_BOX'))

    def test_policy_resumes_and_reads_fresh_capture_before_first_inference(self):
        session = StudentArmSession.__new__(StudentArmSession)
        stale, fresh = {'stamp': 0.}, {'stamp': 5.}
        rig = SimpleNamespace(active=False, last=stale)
        def set_active(active, *, reset_capture):
            rig.active = active
            rig.last = fresh
        rig.set_active = Mock(side_effect=set_active)
        rig.capture = lambda: rig.last
        camera = SimpleNamespace(contract={},start=Mock(),step=Mock(),acknowledge=Mock())
        session.controller = SimpleNamespace(rig=rig)
        adapter = mission_session(camera,np.eye(4),session._policy_capture)
        adapter.start('target',np.zeros(6))
        self.assertFalse(rig.active)
        adapter.step(stale,np.zeros(6),np.zeros(6),5.)
        self.assertIs(camera.step.call_args.args[0],fresh)
        rig.set_active.assert_called_once_with(True,reset_capture=False)
        adapter.step(stale,np.zeros(6),np.zeros(6),5.05)
        self.assertEqual(rig.set_active.call_count,1)

    def run_session(self, *, retry_visible=True, laser_for=(), two_targets=False, stuck=False, mapped=False,
                    evaluation_fault=''):
        """동역학 대역은 명령을 따라 움직인다. 제어/재시도/Action 완료 FSM은 실제 코드다."""
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        (Path(folder.name)/'session/ab').mkdir(parents=True)
        (Path(folder.name)/'session/ab/rear_initial.png').touch()
        config = dict(home_rad=[.1, 0, 0, 0, 0, 1.1], stow_rad=[.3, 0, 0, 0, 0, 1.1],
                      home_to_stow_via_rad=[], speed_rad_s=.3, max_command_lead_rad=.08,
                      position_tolerance_rad=.035, stop_speed_rad_s=.08,
                      instantaneous_speed_limit_rad_s=.5, settle_s=.4,
                      waypoint_timeout_s=20., harvest_timeout_s=60., joint_ttl_s=.1,
                      box_evidence_ttl_s=.15)
        q = np.array(config['stow_rad']); qd = np.zeros(6); goal = q.copy()
        applied = dict(joint_targets=goal.copy(), stiffness=[25.]*6, velocity_limits=[1.2]*6)
        def command(value):
            applied['joint_targets'] = np.array(value).copy()
        def actuator(value):
            applied.update(value)
        def candidates(excluded):
            if evaluation_fault == 'candidates':
                raise ValueError('평가 데이터 오류')
            return [dict(target_id='/target', color='red', root_arm_m=[.3,0,.2])] if mapped else []
        def evaluation_sample():
            if evaluation_fault == 'sample':
                raise RuntimeError('평가 좌표 조회 오류')
            return dict(fruit_position=np.array([.3,0,.7]))
        device = SimpleNamespace(
            home=np.array(config['home_rad']), travel=np.array(config['stow_rad']),
            lower=np.full(6, -2.), upper=np.full(6, 2.),
            joint_positions=lambda: q.copy(), joint_velocities=lambda: qd.copy(),
            command=command, configure_actuator=actuator, applied_command=lambda: applied,
            clear_target=Mock(), select_target=Mock(),
            candidates=candidates, sample=evaluation_sample,
            arm_world_transform=lambda: np.eye(4),
            travel_ready=lambda: bool(np.max(abs(q-config['stow_rad'])) < .1 and np.max(abs(qd)) < .5),
            paths=['/unrelated'], attachments=SimpleNamespace(attached=np.array([True])),
            observe_physics_tick=lambda dt, now: None,
            contacts_for_recovery=lambda: dict(finger_net_forces_world=np.zeros((2,3)), arm_forces_world=np.zeros((1,3))),
            config=dict(workspace_arm_min_m=[0, -1, -1], workspace_arm_max_m=[1, 1, 1],
                        home_tcp_arm_m=[0, 0, 0], near_home_min_m=.09, near_home_max_m=1.))
        starts = []
        contract = dict(lower_rad=[-2.]*6, upper_rad=[2.]*6, box_from_arm=np.eye(4).tolist(),
                        task=dict(max_contact_force=25.))
        camera = SimpleNamespace(contract=contract, roi=[[-1]*3,[1]*3], target=None,
                                 observe=lambda capture, now: ({}, []), acknowledge=lambda cmd: None)
        def start(target, previous):
            camera.target = target
            starts.append(target.target_id)
        camera.start = start
        camera.step = lambda capture, pos, vel, now: (
            encode_command(pos, [1., .3], [-2.]*6, [2.]*6),
            dict(visual_servo=dict(observed_tray_release_latched=True)))
        counter = SimpleNamespace(armed=False)
        counter.arm = lambda: setattr(counter, 'armed', True)
        counter.disarm = lambda: setattr(counter, 'armed', False)
        emitted = set()
        def sample(now):
            key = camera.target.target_id if camera.target is not None else ''
            if counter.armed and key in laser_for and key not in emitted:
                emitted.add(key)
                return dict(stamp_s=now, sequence=len(emitted))
            return None
        rig = SimpleNamespace(last=True, active=True, set_active=Mock(), capture=lambda: {},
                              robot_transform=lambda: np.eye(4), sequence=0, max_fk_error=0.)
        controller = SimpleNamespace(profile=dict(inventory_timeout_s=3., assignment_gate_m=.06,
                                                   assignment_ambiguity_m=.02),
            config=config, contract=contract, camera=camera, rig=rig, cancel=Mock(),
            kin=SimpleNamespace(fk=lambda q, link: np.eye(4)),
            basket_sensor=SimpleNamespace(counter=counter, sample=sample,
                                         last=dict(blocked=[False]*3, state='CLEAR')))
        arm = StudentArmSession('session', 'harvest_01', 'map', device, controller,
            SimpleNamespace(set_activity=Mock()),
            dict(control_dt_s=.05, lease_s=2., stop_hold_s=.15, stop_timeout_s=3.,
                 base_drift_limit_m=.02, base_yaw_drift_limit_rad=.05), Path(folder.name))
        self.addCleanup(lambda: arm._trace.close() if arm._trace is not None else None)
        request = dict(kind='harvest_arm', op='start', session='session', robot_id='harvest_01',
                       seq=0, sent=0., job_id='ab', map_id='map', task_id='task', window_id='W001',
                       expected_count=2 if two_targets else 1)
        self.assertTrue(arm.accept(request, now=0.))
        def snapshot(now):
            if arm._is_retry:
                target = arm._retry_target
                return {'retry': dict(valid=True, label=target.label,
                                     position_m=(np.asarray(target.anchor_arm_m)+[.005,0,0]).tolist())} if retry_visible else {}
            targets = {'first': dict(valid=True, label='Red', position_m=[.3, 0, .2])}
            if two_targets:
                targets['second'] = dict(valid=True, label='Yellow', position_m=[.4, 0, .3])
            return targets
        tracker = SimpleNamespace(update=lambda d, now: None, snapshot=snapshot)
        stages = []
        with patch('harvest_vision.student60_tracking.AssignedFruitTracker', return_value=tracker), \
                patch('harvest_runtime.student60_mission_session.lifted_return_path',
                      side_effect=lambda kin, contract, cfg, current, home: [home]):
            for i in range(7000):
                now = i*.05
                if i:
                    self.assertTrue(arm.accept(dict(request, op='keepalive', seq=i, sent=now), now=now))
                arm.tick(now, base_stationary=True, wall_now=now)
                stages.append(arm.state['stage'])
                if arm.state['status'] != 'RUNNING':
                    break
                previous = q.copy()
                if not (stuck and arm.state['stage']=='RETURN_STOW'):
                    q[:] = applied['joint_targets']
                qd[:] = (q-previous)/.05
                # 작업과 무관한 과실 이탈도 제어 중단 없이 성능 사건으로 남아야 한다.
                if arm.state['stage'] == 'HARVEST':
                    device.attachments.attached[0] = False
                arm.observe_physics_tick(.05, now)
            else:
                self.fail('재시도가 유한하게 종료되지 않음')
        report = json.loads((Path(folder.name)/'session/ab/performance.json').read_text())
        return arm, starts, stages, report

    def test_unresolved_id_still_harvests_by_laser_and_collateral_does_not_stop(self):
        arm, starts, _, report = self.run_session(laser_for={'first'})
        self.assertEqual(starts, ['first'])
        self.assertEqual((arm.state['status'], arm.state['success_count'], arm.state['failed_count']), ('SUCCESS',1,0))
        arm.device.select_target.assert_not_called()
        reasons = [e['reason'] for e in report['events']]
        self.assertIn('evaluation_id_unresolved', reasons)
        self.assertEqual(reasons.count('detachment_identity_unresolved'), 1)
        self.assertNotIn('unassigned_fruit_detached', reasons)

    def test_known_unassigned_detachment_is_performance_only(self):
        arm, starts, _, report = self.run_session(laser_for={'first'}, mapped=True)
        self.assertEqual(arm.state['status'], 'SUCCESS')
        self.assertEqual(arm.state['success_count'], 1)
        self.assertEqual([e['reason'] for e in report['events']], ['unassigned_fruit_detached'])

    def test_evaluation_exceptions_do_not_block_camera_and_laser(self):
        for fault in ('candidates', 'sample'):
            with self.subTest(fault=fault):
                arm, _, _, report = self.run_session(laser_for={'first'}, mapped=True, evaluation_fault=fault)
                self.assertEqual((arm.state['status'],arm.state['success_count']), ('SUCCESS',1))
                self.assertIn('evaluation_unavailable', [e['reason'] for e in report['events']])

    def test_two_full_timeouts_then_success_action_zero_harvest(self):
        arm, starts, stages, report = self.run_session()
        self.assertEqual(starts, ['first', 'retry'])
        self.assertEqual((arm.state['status'], arm.state['success_count'], arm.state['failed_count']), ('SUCCESS',0,1))
        self.assertTrue(arm.state['safe_stopped'])
        self.assertIn('RETURN_STOW', stages)
        self.assertEqual(sum(e['reason']=='harvest_or_box_timeout' for e in report['events']), 2)
        for mission in report['missions']:
            events = mission['events']
            begin = next(e['stamp_s'] for e in events if e['state']=='HARVEST')
            end = next(e['stamp_s'] for e in events if e['state']=='HARVEST_TIMEOUT')
            self.assertAlmostEqual(end-begin, 60., places=5)

    def test_missing_retry_target_skips_without_another_blind_attempt(self):
        arm, starts, _, report = self.run_session(retry_visible=False)
        self.assertEqual(starts, ['first'])
        self.assertEqual((arm.state['status'], arm.state['success_count'], arm.state['failed_count']), ('SUCCESS',0,1))
        self.assertIn('retry_target_not_observed', [e['reason'] for e in report['events']])

    def test_retry_success_and_next_original_target_are_preserved(self):
        arm, starts, _, _ = self.run_session(two_targets=True, laser_for={'retry','second'})
        self.assertEqual(starts, ['first', 'retry', 'second'])
        self.assertEqual((arm.state['status'], arm.state['success_count'], arm.state['failed_count']), ('SUCCESS',2,0))

    def test_exhausted_retry_does_not_skip_remaining_targets(self):
        arm, starts, _, _ = self.run_session(two_targets=True, laser_for={'second'})
        self.assertEqual(starts, ['first', 'retry', 'second'])
        self.assertEqual((arm.state['status'], arm.state['success_count'], arm.state['failed_count']), ('SUCCESS',1,1))

    def test_prior_harvest_is_not_reset_or_retried_after_later_timeout(self):
        arm, starts, _, _ = self.run_session(two_targets=True, laser_for={'first','retry'})
        self.assertEqual(starts, ['first', 'second', 'retry'])
        self.assertEqual((arm.state['status'], arm.state['success_count'], arm.state['failed_count']), ('SUCCESS',2,0))

    def test_failed_physical_return_is_still_action_failure(self):
        arm, starts, _, _ = self.run_session(stuck=True)
        self.assertEqual(starts, ['first'])
        self.assertEqual(arm.state['status'], 'FAILED')
        self.assertEqual(arm.state['error_code'], 'STUDENT_MISSION_FAILED')
        self.assertEqual(arm.state['error_message'], 'motion_tracking_timeout')


if __name__ == '__main__':
    unittest.main()
