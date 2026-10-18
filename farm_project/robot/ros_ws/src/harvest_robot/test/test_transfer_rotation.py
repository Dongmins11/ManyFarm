"""공통 인계 미션과 제자리 정/역회전 어댑터. 실제 ROS·모터는 사용하지 않는다."""
from pathlib import Path
import math
import sys
import threading
import time
from types import SimpleNamespace as S
import unittest
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from harvest_robot.transfer_devices import DeviceResult
from harvest_robot.transfer_mission import TransferMission
from harvest_robot.transfer_rotation import RotationSettings, RotatingTransferDevices, rotation_parameters


class RotationTests(unittest.TestCase):
    def setUp(self):
        # 시험 전용 허용값/주소이며 운영 설정이 아니다.
        self.settings=RotationSettings('test_only/spin',math.pi/2,1.,.02,.03)
        self.xyz=[0.,0.,.4];self.calls=[];self.angles=[]
        self.fail='';self.drift=0.;self.yaw_error=0.;self.stop_fails=False
        def pose(check):
            check();x,y,a=self.xyz;m=np.eye(4);m[0,3]=x;m[1,3]=y
            m[0,0]=math.cos(a);m[1,0]=math.sin(a);return m
        def start(operation):
            self.calls.append(operation);return operation
        def poll(operation):
            return DeviceResult(True,operation!=self.fail,'test device failure')
        devices=S(ready=lambda:True,start=start,poll=poll,close=lambda _:None)
        def turn(angle,allowance,check):
            check();self.calls.append('spin');self.angles.append(angle)
            self.xyz[2]+=angle+self.yaw_error;self.xyz[0]+=self.drift;check()
        def stopped(check):
            check();self.calls.append('stopped')
            if self.stop_fails:raise RuntimeError('odom stale')
        self.spin=S(ready=lambda:True,has_goal=False,execute=turn,
                    cancel=lambda:self.calls.append('cancel_spin'),close=lambda:None)
        self.adapter=RotatingTransferDevices(devices,self.spin,S(current=pose),S(wait_stopped=stopped),
                                            self.settings,1.,.1)
        self.addCleanup(self.adapter.close,None)

    def perform(self, operation):
        ticket=self.adapter.start(operation)
        try:ticket.result(timeout=2.)
        except Exception:pass
        return self.adapter.poll(ticket)

    def test_exact_opposite_angle_and_original_heading(self):
        for operation in ('prepare_arm','rotate_to_transfer','discharge','restore'):
            self.assertTrue(self.perform(operation).ok,operation)
        self.assertEqual(self.angles,[math.pi/2,-math.pi/2])
        self.assertAlmostEqual(self.xyz[2],.4)
        self.assertLess(self.calls.index('restore_devices'),len(self.calls)-1)
        self.assertTrue(self.adapter.ready())

    def test_heading_error_does_not_retry(self):
        self.yaw_error=.1
        self.assertFalse(self.perform('rotate_to_transfer').ok)
        self.assertEqual(len(self.angles),1)
        self.assertFalse(self.perform('restore').ok)
        self.assertEqual(len(self.angles),1)

    def test_translation_drift_is_failure_without_move_correction(self):
        self.drift=.03
        self.assertFalse(self.perform('rotate_to_transfer').ok)
        self.assertEqual(self.angles,[math.pi/2])

    def test_restore_error_does_not_add_correction_spin(self):
        self.assertTrue(self.perform('rotate_to_transfer').ok)
        self.yaw_error=.1
        self.assertFalse(self.perform('restore').ok)
        self.assertEqual(self.angles,[math.pi/2,-math.pi/2])

    def test_gate_restore_failure_prevents_reverse_rotation(self):
        self.assertTrue(self.perform('rotate_to_transfer').ok)
        self.fail='restore_devices'
        self.assertFalse(self.perform('restore').ok)
        self.assertEqual(len(self.angles),1)

    def test_stale_odom_prevents_rotation(self):
        self.stop_fails=True
        self.assertFalse(self.perform('rotate_to_transfer').ok)
        self.assertFalse(self.angles)

    def test_mission_waits_transport_clear_before_reverse(self):
        dock,loaded=threading.Event(),threading.Event();feedback=[];out=[]
        def report(value):
            feedback.append(value)
            (dock if value=='DOCK_READY' else loaded).set()
        mission=TransferMission(self.adapter,report,lambda:False,lambda:False,1.,.2)
        worker=threading.Thread(target=lambda:out.append(mission.run()));worker.start()
        try:
            self.assertTrue(dock.wait(1.));self.assertEqual(self.angles,[math.pi/2])
            self.assertNotIn('discharge',self.calls)
            self.assertTrue(mission.receive('DOCK_STABLE')[0])
            self.assertTrue(loaded.wait(1.));self.assertEqual(self.angles,[math.pi/2])
            self.assertNotIn('restore_devices',self.calls)
            self.assertTrue(mission.receive('TRANSPORT_CLEAR')[0])
        finally:worker.join(2.)
        self.assertFalse(worker.is_alive());self.assertEqual(out[0].result_code,'SUCCESS')
        self.assertTrue(out[0].restore_complete)
        self.assertEqual(self.angles,[math.pi/2,-math.pi/2])

    def test_rotation_failure_never_sends_dock_ready(self):
        self.yaw_error=.1;feedback=[]
        result=TransferMission(self.adapter,feedback.append,lambda:False,lambda:False,1.,.2).run()
        self.assertEqual(result.result_code,'FAILED');self.assertTrue(result.recovery_required)
        self.assertFalse(feedback);self.assertIn('cancel_spin',self.calls)
        self.assertNotIn('restore_devices',self.calls);self.assertFalse(self.adapter.ready())

    def test_stop_also_calls_device_stop_if_spin_cancel_fails(self):
        def fail():raise RuntimeError('cancel missing')
        self.spin.cancel=fail
        self.assertFalse(self.perform('stop').ok)
        self.assertIn('stop',self.calls)
        self.assertFalse(self.adapter.ready())

    def test_shared_communication_selects_rotation_and_rejects_missing_devices(self):
        # 기존 통신 fixture를 재사용하여 실제 생성자/설정 전달도 확인한다.
        import test_harvest_load as fixtures
        from unittest.mock import patch
        fixture=fixtures.TransferTests()
        fixture.setUp()
        try:
            fixture.params['transfer_rotation_mode']='nav2_spin'
            import json
            fixture.params['transfer_rotation']=json.dumps(vars(self.settings))
            fixture.params['transfer_device_services']='{}'
            fixture.node.poses=self.adapter.poses;fixture.node.motion=self.adapter.motion
            with patch('farm_navigation.spin_client.SpinClient',return_value=self.spin):
                server=type(fixture.server)(fixture.node,S())
            self.addCleanup(server.devices.close,fixture.node)
            self.assertIsInstance(server.devices,RotatingTransferDevices)
            self.assertEqual(server.accept(fixture.goal),0)
            self.assertFalse(self.angles)
            self.assertEqual(fixture.calls,[])
        finally:fixture.doCleanups()

    def test_shared_communication_runs_body_and_device_operations_separately(self):
        import test_harvest_load as fixtures
        from unittest.mock import patch
        import json
        fixture=fixtures.TransferTests();fixture.setUp()
        try:
            fixture.params['transfer_rotation_mode']='nav2_spin'
            fixture.params['transfer_rotation']=json.dumps(vars(self.settings))
            operations=('prepare_arm','discharge','restore_devices','stop')
            fixture.params['transfer_device_services']=json.dumps({k:'/test_only/'+k for k in operations})
            fixture.node.poses=self.adapter.poses;fixture.node.motion=self.adapter.motion
            fixture.node.destroy_client=lambda _:None
            with patch('farm_navigation.spin_client.SpinClient',return_value=self.spin):
                fixture.server=type(fixture.server)(fixture.node,S())
            try:
                self.assertEqual(fixture.server.accept(fixture.goal),1)
                result=fixture.server.execute(fixture.handle())
                self.assertEqual(result.result_code,'SUCCESS')
                self.assertEqual(self.angles,[math.pi/2,-math.pi/2])
                self.assertEqual(fixture.calls,['/test_only/'+k for k in operations[:3]])
            finally:fixture.server.devices.close(fixture.node)
        finally:fixture.doCleanups()

    def test_settings_require_explicit_values_and_preserve_legacy(self):
        self.assertEqual(rotation_parameters({})['rotation_mode'],'device_services')
        values=dict(vars(self.settings))
        self.assertEqual(RotationSettings.from_mapping(values),self.settings)
        for config in ({'rotation_mode':'bad'}, {'rotation_mode':'nav2_spin'},
                       {'rotation':values}, {'rotation_mode':'nav2_spin','rotation':dict(values,angle_rad=-1)}):
            with self.assertRaises(ValueError):rotation_parameters(config)


if __name__=='__main__':unittest.main()
