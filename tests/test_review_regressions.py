"""실제 제어 메서드에 대역 입력을 공급한다. ROS 노드·장치·주행은 시작하지 않는다."""
import math
import threading
import unittest
from concurrent.futures import Future
from contextlib import nullcontext
from pathlib import Path
from queue import Queue
from types import SimpleNamespace as N
from unittest.mock import Mock, patch
import yaml
from farm_docking.precision_server import PrecisionServer
from farm_docking.clients import PrecisionClient
from farm_docking.recovery import RecoveryWait
from farm_docking.initial_marker_recovery import InitialMarkerRecovery
from farm_docking.lidar_approach import ScanFreshnessError
from farm_docking.distance_heading import HeadingCapture
from transport_robot.transport_node import TransportNode
from transport_robot.harvest_approach import HarvestApproach
ROOT=Path(__file__).resolve().parents[1]/'farm_project'
PROFILES=yaml.safe_load((ROOT/'robot/config/docking/waffle_profiles.yaml').read_text())['profiles']

class Lifecycle(unittest.TestCase):
    def ending(self,stopped=True):
        s=dict(handle=N(request=N(profile_id='test',operation='DOCK')),ending_at=1.,started=0.,candidate=True,error='',done=threading.Event(),lidar_stage=True)
        o=N(_session=s,_pending=Queue(),profiles={'test':{}},sensor_inputs=lambda:{},update_legacy_sensors=lambda x:None,
            drive=Mock(),lidar_status=Mock(side_effect=ScanFreshnessError('stale')),stopped=lambda:stopped)
        o.complete=lambda:s['done'].set()
        return o,s
    def test_final_scan_loss_terminates_failure(self):
        o,s=self.ending()
        PrecisionServer.control_tick(o)
        self.assertTrue(s['done'].is_set());self.assertFalse(s['candidate']);self.assertIn('stale',s['error'])
    def test_final_scan_loss_without_stop_times_out(self):
        o,s=self.ending(False)
        PrecisionServer.control_tick(o)
        self.assertTrue(s['done'].is_set());self.assertIn('정지 odom',s['error'])
    def test_cancel_during_settling_invalidates_success(self):
        o,s=self.ending()
        PrecisionServer.finish(o,'FAILED','cancelled')
        self.assertFalse(s['candidate']);self.assertEqual(s['error'],'cancelled')
    def test_complete_signals_even_if_camera_close_fails(self):
        o,s=self.ending()
        o.lease=N(release=Mock());o.cam_off=Mock(side_effect=RuntimeError('camera close'))
        PrecisionServer.complete(o)
        self.assertTrue(s['done'].is_set());self.assertIsNone(o._session);self.assertIn('camera close',s['error'])
    def test_successful_final_validation_unchanged(self):
        o,s=self.ending();o.lidar_status=lambda *a:(0,0,True,.2)
        PrecisionServer.control_tick(o)
        self.assertTrue(s['candidate']);self.assertEqual(s['error'],'');self.assertTrue(s['done'].is_set())

class Acquisition(unittest.TestCase):
    def test_detection_is_not_acquisition(self):
        p=InitialMarkerRecovery(PROFILES['sort_01_distance_trial']['initial_marker_recovery'],0.)
        self.assertFalse(p.step(3.,(0,0,0),True,True)[2])
        v,w,done,phase=p.step(5.1,(0,0,0),True,True)
        self.assertFalse(done);self.assertLess(v,0)
        self.assertTrue(p.step(5.2,(0,0,0),True,True,True)[2])
    def test_invalid_bearing_never_confirms(self):
        c=HeadingCapture(PROFILES['sort_01_distance_trial']['distance_heading_trial'])
        for i in range(1,11):
            r=dict(stamp_ns=i*100000000,markers=[dict(marker_id=40,marker_position_in_base_m=[1.,math.tan(.24),0.])])
            self.assertIsNone(c.add(r,0.,r['stamp_ns']))
    def test_capture_gap_does_not_reuse_old_samples(self):
        c=HeadingCapture(PROFILES['sort_01_distance_trial']['distance_heading_trial'])
        for stamp in (1000000000,1100000000,1200000000,1300000000,5000000000):
            report=dict(stamp_ns=stamp,markers=[dict(marker_id=40,marker_position_in_base_m=[1.,0.,0.])])
            self.assertIsNone(c.add(report,0.,stamp))
        self.assertEqual(len(c.samples),1)

    def test_distance_recovery_does_not_require_pose_preview(self):
        p=PROFILES['sort_01_distance_trial'];now=[10.]
        s=dict(recovery_wait=RecoveryWait('SENSORS',10.,15.,.5),observation_start_ns=1,heading_capture=object())
        o=N(sensor_inputs=lambda:dict(odom_at=now[0],scan_at=now[0]),departure_locked=lambda p:False,odom_transit=lambda p:False,
            _image_at=10.,_tracking_enabled=True,_tracking_preview=None,odom_max_age_s=.5,scan_max_age_s=.5,
            image_receive_timeout_s=.5,image_header_max_age_s=.3,tf=N(lookup_transform=lambda *a,**k:N()),
            get_parameter=lambda n:N(value='odom'),fresh=lambda t:True,drive=Mock(),phase_feedback=Mock(),
            check_footprint_motion=Mock(),stopped=lambda:True,_pose_lock=nullcontext(),
            _pose_controller=N(reset=Mock()),get_logger=lambda:N(info=Mock()))
        with patch('farm_docking.precision_server.time.monotonic',side_effect=lambda:now[0]):
            PrecisionServer.run_recovery(o,s,p)
            now[0]=10.6;o._image_at=now[0]
            PrecisionServer.run_recovery(o,s,p)
        self.assertNotIn('recovery_wait',s);self.assertNotIn('heading_capture',s)
        self.assertEqual(s['distance_acquire_started'],10.6)
    def test_capture_uses_current_session_and_distinct_frames(self):
        p=PROFILES['sort_01_distance_trial'];now=[1000000000]
        s={'observation_start_ns':now[0]}
        o=N(get_clock=lambda:N(now=lambda:N(nanoseconds=now[0])),get_parameter=lambda n:N(value='odom'),
            tf=N(lookup_transform=lambda *a,**k:N(transform=N(rotation=N(w=1.,x=0.,y=0.,z=0.)))))
        o._raw_reports=[dict(stamp_ns=900000000,markers=[dict(marker_id=40,marker_position_in_base_m=[1.,0.,0.])])]
        self.assertIsNone(PrecisionServer.capture_distance_heading(o,s,p))
        for i in range(5):
            now[0]=1000000000+i*100000000
            o._raw_reports=[dict(stamp_ns=now[0],markers=[dict(marker_id=40,marker_position_in_base_m=[1.,0.,0.])])]
            result=PrecisionServer.capture_distance_heading(o,s,p)
            if i<4:self.assertIsNone(result)
        self.assertIsNotNone(result)

class Ownership(unittest.TestCase):
    def client(self):
        c=object.__new__(PrecisionClient);f=Future()
        h=N(get_result_async=lambda:f,cancel_goal_async=Mock(return_value=Future()))
        c.handle=h;c.result_future=f;c.client=N(server_is_ready=lambda:True)
        c._goal_lock=threading.RLock();c._accept_future=None;c._late_error=''
        return c,h,f
    def test_cancel_timeout_retains_handle_then_can_retry(self):
        c,h,f=self.client()
        with patch('farm_docking.clients.wait',side_effect=TimeoutError('no response')):
            with self.assertRaises(TimeoutError):c.stop()
        self.assertIs(c.handle,h);self.assertFalse(c.available())
        f.set_result(N(status=5,result=N(stopped=True)))
        c.stop();self.assertIsNone(c.handle);self.assertTrue(c.available())
    def test_terminal_without_stop_is_not_cleared(self):
        c,h,f=self.client();f.set_result(N(status=6,result=N(stopped=False)))
        with self.assertRaises(RuntimeError):c.stop()
        self.assertIs(c.handle,h)
    def test_manual_stop_confirmation_clears_terminal_only(self):
        c,h,f=self.client()
        with patch('farm_docking.clients.wait',side_effect=TimeoutError('no terminal result')):
            with self.assertRaises(TimeoutError):c.stop(stationary_confirmed=lambda:True)
        self.assertIs(c.handle,h)
        f.set_result(N(status=6,result=N(stopped=False)))
        with self.assertRaises(RuntimeError):c.stop(stationary_confirmed=lambda:False)
        self.assertIs(c.handle,h)
        c.stop(stationary_confirmed=lambda:True)
        self.assertIsNone(c.handle)

    def test_run_keeps_unresolved_handle_on_input_failure(self):
        c,h,f=self.client();c.handle=None;c.timeout=120.;c.pre_entry_stopped=False
        c.client.wait_for_server=lambda **kw:True
        c.check=Mock(side_effect=RuntimeError('cancel requested'));h.accepted=True
        r=N(task_id='review',profile_id='harvest_dock_41',target_marker_id=41,docking_marker_id=41,clearance_xy=None,xy=(0.,0.),clearance_yaw=None,yaw=0.)
        def accept(q):c.handle=h;return h
        with patch.object(c,'_accept',side_effect=accept),patch('farm_docking.clients.wait',side_effect=TimeoutError('no response')):
            with self.assertRaisesRegex(RuntimeError,'종료 미확인'):c.run(r,'DOCK')
        self.assertIs(c.handle,h)
    def late_client(self):
        c,h,result=self.client();c.handle=None;c.result_future=None;h.accepted=True
        acceptance=Future();c.client.send_goal_async=Mock(return_value=acceptance)
        with patch('farm_docking.clients.wait',side_effect=TimeoutError('accept timeout')):
            with self.assertRaises(TimeoutError):c._accept(object())
        return c,h,result,acceptance
    def test_late_acceptance_cancelled_and_tracked_until_stopped(self):
        c,h,result,acceptance=self.late_client()
        self.assertTrue(c.pending);self.assertFalse(c.available())
        with self.assertRaisesRegex(RuntimeError,'접수 응답'):c.stop()
        with self.assertRaisesRegex(RuntimeError,'종료 미확인'):c._accept(object())
        self.assertEqual(c.client.send_goal_async.call_count,1)
        acceptance.set_result(h)
        h.cancel_goal_async.assert_called_once()
        self.assertIs(c.handle,h);self.assertIs(c.result_future,result)
        self.assertFalse(c.available())
        result.set_result(N(status=5,result=N(stopped=True)))
        self.assertFalse(c.pending);self.assertTrue(c.available())
    def test_late_rejection_releases_pending(self):
        c,h,result,acceptance=self.late_client();h.accepted=False
        acceptance.set_result(h)
        self.assertFalse(c.pending);h.cancel_goal_async.assert_not_called()
    def test_late_terminal_without_stop_is_retained(self):
        c,h,result,acceptance=self.late_client();acceptance.set_result(h)
        result.set_result(N(status=6,result=N(stopped=False)))
        self.assertTrue(c.pending)
        c.stop(stationary_confirmed=lambda:True)
        self.assertFalse(c.pending)
    def test_late_cancel_send_error_retains_goal_for_retry(self):
        c,h,result,acceptance=self.late_client()
        h.cancel_goal_async.side_effect=RuntimeError('send failed')
        acceptance.set_result(h)
        self.assertIs(c.handle,h);self.assertIn('send failed',c._late_error)
        result.set_result(N(status=6,result=N(stopped=True)))
        self.assertFalse(c.pending)
    def test_result_subscription_error_does_not_prevent_cancel(self):
        c,h,result,acceptance=self.late_client()
        h.get_result_async=Mock(side_effect=RuntimeError('result subscription'))
        acceptance.set_result(h)
        h.cancel_goal_async.assert_called_once();self.assertTrue(c.pending)
        result.set_result(N(status=5,result=N(stopped=True)))
        h.get_result_async=lambda:result
        c.stop();self.assertFalse(c.pending)
    def test_acceptance_finishes_at_timeout_boundary(self):
        c,h,result=self.client();c.handle=None;c.result_future=None;h.accepted=True
        acceptance=Future();acceptance.set_result(h)
        c.client.send_goal_async=lambda q:acceptance
        result.set_result(N(status=5,result=N(stopped=True)))
        with patch('farm_docking.clients.wait',side_effect=TimeoutError('boundary')):
            with self.assertRaises(TimeoutError):c._accept(object())
        h.cancel_goal_async.assert_called_once();self.assertFalse(c.pending)

    def test_precision_check_does_not_require_map(self):
        o=N(controller=N(check=Mock()),device=None,_pose=None)
        TransportNode.check_precision(o);o.controller.check.assert_called_once()
        o.controller.check.side_effect=RuntimeError('cancel')
        with self.assertRaisesRegex(RuntimeError,'cancel'):TransportNode.check_precision(o)

class Observer(unittest.TestCase):
    def test_expiry_report_repeated_and_stops_handoff(self):
        route=dict(expires_at=0.,observer_id='one',profile='harvest_approach_42')
        pub=Mock();o=N(_harvest_route=route,_harvest_ready_pub=pub,get_clock=lambda:N(now=lambda:N(nanoseconds=10000000000)))
        PrecisionServer.update_harvest_route(o);PrecisionServer.update_harvest_route(o)
        self.assertEqual(pub.publish.call_count,2)
        import json
        report=json.loads(pub.publish.call_args.args[0].data)
        a=N(lock=threading.Lock(),armed=True,ready=report,profile=route['profile'],c={'max_ready_age_s':.5},node=o)
        with self.assertRaisesRegex(RuntimeError,'expired'):HarvestApproach.check_handoff(a)
    def test_configuration_single_source_and_yaw_preserved(self):
        env=yaml.safe_load((ROOT/'robot/config/environments/transport_docking_trial.yaml').read_text())
        self.assertNotIn('initial_marker_recovery',env)
        self.assertEqual(PROFILES['sort_departure_distance_trial']['distance_departure']['map_yaw_rad'],0.)

class UpstreamHarvestCompletion(unittest.TestCase):
    def fixture(self, explicit=True):
        import json
        from harvest_robot.handoff_planning import CompletionPolicy,HandoffPlanner
        from harvest_robot.transfer_restore import RestoreReference
        from farm_navigation.transfer_arc import ArcSpec,arc_path
        cfg=json.loads((ROOT/'robot/config/robots/vicpinky/transfer/handoff_fsm.json').read_text())
        policy=CompletionPolicy(**cfg['completion']) if explicit else CompletionPolicy()
        spec=ArcSpec();position=[arc_path((0.,0.,0.),spec)[-1]]
        ref=RestoreReference('farm','w','s','map','odom','base_footprint',10,(0.,0.),(1.,0.),(0.,0.,0.),spec)
        planner=HandoffPlanner(poses=None,motion=None,inputs=N(context=lambda:('farm','w','s'),pose=lambda *a:position[0]),
            guard=lambda *a:lambda:None,wall={},spec=spec,window_xy=(0.,0.),map_frame='map',odom_frame='odom',base_frame='base_footprint',
            policy=policy,window_correction=True)
        return planner.plan('return',ref,lambda:None),position,policy
    def test_config_load_and_motion_limit(self):
        step,position,policy=self.fixture()
        self.assertAlmostEqual(policy.return_heading,math.radians(6))
        self.assertAlmostEqual(policy.motion_heading,math.radians(3))
        self.assertEqual(policy.return_endpoint_position,.05)
    def test_explicit_completion_accepts_but_motion_monitor_rejects_offset(self):
        step,position,policy=self.fixture();position[0]=(.04,0.,math.radians(5))
        self.assertTrue(step.validate(123,lambda:None)['accepted'])
        with self.assertRaises(RuntimeError):step.monitor()
    def test_completion_rejects_over_limit_and_unconfirmed_stop(self):
        step,position,policy=self.fixture()
        for pose in ((.051,0.,0.),(0.,0.,math.radians(6.01))):
            position[0]=pose
            with self.assertRaises(RuntimeError):step.validate(123,lambda:None)
        position[0]=(0.,0.,0.)
        with self.assertRaisesRegex(RuntimeError,'not stopped'):
            step.validate(123,Mock(side_effect=RuntimeError('not stopped')))
    def test_default_profile_keeps_strict_completion(self):
        step,position,policy=self.fixture(False);position[0]=(.009,0.,0.)
        self.assertIsNone(policy.return_endpoint_position)
        with self.assertRaises(RuntimeError):step.validate(123,lambda:None)

if __name__=='__main__':unittest.main()
