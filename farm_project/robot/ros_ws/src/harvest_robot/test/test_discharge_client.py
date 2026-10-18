"""ROS Future 대역으로 실제 클라이언트·어댑터·공통 관제 연결을 검증한다."""
from concurrent.futures import Future
from pathlib import Path
from types import SimpleNamespace as S
from unittest.mock import patch
import sys
import unittest
import math
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from harvest_robot.discharge_client import DischargeClient, discharge_parameters
from harvest_robot.discharge_devices import DischargeDevices
from harvest_robot.discharge_result import DischargeEvidence
from harvest_robot.transfer_devices import DeviceResult


def done(value: object) -> Future:
    f = Future(); f.set_result(value); return f


class FakeAction:
    def __init__(self, *, status: int = 4, errors: tuple = (), rejected: bool = False) -> None:
        self.status, self.errors, self.rejected = status, errors, rejected
        self.sent = []; self.callbacks = []; self.cancels = 0
        self.pending = None; self.result = None
        self.defer_goal = self.defer_result = False

    def server_is_ready(self) -> bool: return True
    def destroy(self) -> None: pass
    def cancel(self) -> Future:
        self.cancels += 1
        if not self.result.done():
            self.result.set_result(S(status=5, result=S(transfer_id=self.sent[-1], error_codes=[], error_message='')))
        return done(S(return_code=0))
    def send_goal_async(self, goal: object, feedback_callback: object) -> Future:
        self.sent.append(goal.transfer_id); self.callbacks.append(feedback_callback)
        self.result = Future()
        if not self.defer_result:
            self.result.set_result(S(status=self.status, result=S(transfer_id=goal.transfer_id,
                error_codes=list(self.errors), error_message='mock')))
        self.handle = S(accepted=not self.rejected, get_result_async=lambda: self.result,
                        cancel_goal_async=self.cancel)
        self.pending = Future()
        if not self.defer_goal: self.pending.set_result(self.handle)
        return self.pending


def make_client(fake: FakeAction, feedback: object = None) -> DischargeClient:
    return DischargeClient(None, '/test_only/discharge', .02, .03,
                           client=fake, goal_factory=S, feedback=feedback)


class ClientTests(unittest.TestCase):
    def test_feedback_is_not_completion_and_success_is_cached(self) -> None:
        fake = FakeAction(); fake.defer_result = True
        phases = []; c = make_client(fake, phases.append); e = DischargeEvidence('A')
        ticket = c.start(e)
        for phase in ('OPENING','DISCHARGING','CLOSING'):
            fake.callbacks[-1](S(feedback=S(phase=phase)))
        self.assertEqual(phases, ['OPENING','DISCHARGING','CLOSING'])
        self.assertFalse(c.poll(ticket).completed); self.assertFalse(e.restore_check().ok)
        fake.result.set_result(S(status=4, result=S(transfer_id='A', error_codes=[], error_message='')))
        self.assertTrue(c.poll(ticket).ok); self.assertTrue(c.poll(ticket).ok)
        self.assertEqual(fake.sent, ['A'])

    def test_multiple_errors_and_failure_status(self) -> None:
        for status, errors in ((6, ('DISCHARGE_FAILED','CLOSE_FAILED')), (4, ('CLOSE_FAILED',)), (5, ()), (6, ())):
            with self.subTest(status=status, errors=errors):
                fake=FakeAction(status=status, errors=errors); c=make_client(fake); e=DischargeEvidence('A')
                self.assertFalse(c.poll(c.start(e)).ok); self.assertFalse(e.restore_check().ok)
                for code in errors: self.assertIn(code, c.poll(c._token).detail)

    def test_rejection(self) -> None:
        c=make_client(FakeAction(rejected=True)); e=DischargeEvidence('A')
        self.assertFalse(c.poll(c.start(e)).ok); self.assertFalse(c.has_goal)

    def test_missing_server_never_sends(self) -> None:
        fake=FakeAction();fake.server_is_ready=lambda:False;c=make_client(fake)
        with self.assertRaises(RuntimeError): c.start(DischargeEvidence('A'))
        self.assertEqual(fake.sent, [])

    def test_late_accepted_goal_is_canceled_after_response_timeout(self) -> None:
        fake=FakeAction();fake.defer_goal=fake.defer_result=True;c=make_client(fake);e=DischargeEvidence('A')
        ticket=c.start(e);c._deadline=0
        self.assertFalse(c.poll(ticket).ok);self.assertTrue(c.has_goal)
        fake.pending.set_result(fake.handle);c.cancel()
        self.assertEqual(fake.cancels,1);self.assertFalse(c.has_goal);self.assertFalse(e.restore_check().ok)

    def test_cancel_ack_without_terminal_is_not_completion(self) -> None:
        fake=FakeAction();fake.defer_result=True;c=make_client(fake);e=DischargeEvidence('A')
        ticket=c.start(e);c.poll(ticket)
        fake.handle.cancel_goal_async=lambda:done(S(return_code=0))
        with self.assertRaises(TimeoutError): c.cancel()
        self.assertTrue(c.has_goal);self.assertFalse(e.restore_check().ok)

    def test_unknown_send_failure_prevents_resubmit(self) -> None:
        fake=FakeAction()
        def fail(*args: object, **kwargs: object) -> None: raise RuntimeError('send failed')
        fake.send_goal_async=fail;c=make_client(fake)
        with self.assertRaises(RuntimeError): c.start(DischargeEvidence('A'))
        self.assertFalse(c.ready())
        with self.assertRaises(RuntimeError): c.cancel()

    def test_wrong_result_id_and_stale_feedback(self) -> None:
        fake=FakeAction();phases=[];c=make_client(fake,phases.append)
        first=c.start(DischargeEvidence('A'));self.assertTrue(c.poll(first).ok)
        second=c.start(DischargeEvidence('B'));fake.callbacks[0](S(feedback=S(phase='OPENING')))
        self.assertEqual(phases,[]);self.assertFalse(c.poll(first).ok)
        fake.result=done(S(status=4,result=S(transfer_id='A',error_codes=[],error_message='')))
        self.assertFalse(c.poll(second).ok)

    def test_stop_attempts_physical_service_even_if_cancel_fails(self) -> None:
        calls=[]
        def fail() -> None: raise RuntimeError('terminal unknown')
        c=S(ready=lambda:True,cancel=fail)
        d=DischargeDevices(S(ready=lambda:True,start=lambda op:calls.append(op) or op,
            poll=lambda ticket:DeviceResult(True,True)),c)
        d.begin('A');result=d.poll(d.start('stop'))
        self.assertEqual(calls,['stop']);self.assertFalse(result.ok);self.assertFalse(d.ready())

    def test_settings_require_explicit_action_config(self) -> None:
        self.assertEqual(discharge_parameters({})['discharge_mode'],'device_services')
        for value in ({'discharge_mode':'bad'}, {'discharge_mode':'action'},
                {'discharge_action':{'endpoint':'x'}},
                {'discharge_mode':'action','rotation_mode':'nav2_spin','discharge_action':
                 {'endpoint':'x','response_timeout_s':0,'cancel_timeout_s':1}}):
            with self.assertRaises(ValueError): discharge_parameters(value)


class CommunicationTests(unittest.TestCase):
    def scenario(self, failed: bool) -> None:
        import test_harvest_load as fixtures
        fixture=fixtures.HarvestLoadTransferTests();fixture.setUp()
        try:
            fixture.add_window(4)
            fake=FakeAction(status=6 if failed else 4,
                            errors=('DISCHARGE_FAILED','CLOSE_FAILED') if failed else ())
            client=make_client(fake);angles=[];yaw=[0.]
            def spin(angle: float, allowance: float, check: object) -> None:
                check();angles.append(angle);yaw[0]+=angle
            def pose(check: object) -> np.ndarray:
                check();m=np.eye(4);m[0,0]=math.cos(yaw[0]);m[1,0]=math.sin(yaw[0]);return m
            import json
            fixture.params.update(transfer_rotation_mode='nav2_spin',transfer_discharge_mode='action',
                transfer_discharge_action=json.dumps(dict(endpoint='/test_only/discharge',response_timeout_s=1.,cancel_timeout_s=.1)),
                transfer_rotation=json.dumps(dict(endpoint='/test_only/spin',angle_rad=math.pi/2,time_allowance_s=1.,position_tolerance_m=.02,yaw_tolerance_rad=.03)),
                transfer_device_services=json.dumps({k:'/test_only/'+k for k in ('prepare_arm','stop')}),
                transfer_load_source='arm_feedback')
            fixture.node.poses=S(current=pose);fixture.node.motion=S(wait_stopped=lambda check:check())
            fixture.node.destroy_client=lambda client:None
            module=sys.modules.get(type(fixture.server).__module__)
            # fixture는 독립 모듈로 로드하므로 생성자의 globals에서 생성 심볼을 교체한다.
            globals_=type(fixture.server).__init__.__globals__
            with patch.dict(globals_,DischargeClient=lambda *a,**kw:client), patch('farm_navigation.spin_client.SpinClient',
                    return_value=S(ready=lambda:True,has_goal=False,execute=spin,cancel=lambda:None,close=lambda:None)):
                fixture.server=type(fixture.server)(fixture.node,S())
            try:
                self.assertEqual(fixture.server.accept(fixture.goal),1)
                result=fixture.server.execute(fixture.handle())
                self.assertEqual(fake.sent,['X1'])
                if failed:
                    self.assertEqual(result.result_code,'FAILED');self.assertTrue(fixture.node.blocked)
                    self.assertEqual(fixture.node.harvest_load.loaded_count,4)
                    self.assertEqual(angles,[math.pi/2])
                    self.assertIn('DISCHARGE_FAILED',result.error_message)
                    self.assertIn('CLOSE_FAILED',result.error_message)
                    self.assertEqual(fixture.calls,['/test_only/prepare_arm','/test_only/stop'])
                else:
                    self.assertEqual(result.result_code,'SUCCESS')
                    self.assertEqual(fixture.node.harvest_load.loaded_count,0)
                    self.assertEqual(angles,[math.pi/2,-math.pi/2])
                    self.assertEqual(fixture.calls,['/test_only/prepare_arm'])
            finally: fixture.server.devices.close(fixture.node)
        finally: fixture.doCleanups()

    def test_success_resets_load_and_does_not_send_close(self) -> None: self.scenario(False)
    def test_multiple_errors_block_reverse_and_preserve_load(self) -> None: self.scenario(True)


if __name__ == '__main__': unittest.main()
