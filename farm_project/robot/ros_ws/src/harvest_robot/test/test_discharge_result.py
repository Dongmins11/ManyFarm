"""PC 모의 응답 시험. 실제 공통 미션/회전 사용, ROS 통신·물리 장치는 미사용."""
from pathlib import Path
import sys
import math
import threading
from types import SimpleNamespace as S
import unittest
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from harvest_robot.discharge_result import DischargeEvidence, DischargeReply
from harvest_robot.transfer_devices import DeviceResult
from harvest_robot.transfer_mission import TransferMission
from harvest_robot.transfer_rotation import RotatingTransferDevices, RotationSettings


class EvidenceTests(unittest.TestCase):
    def test_success_and_no_resubmit(self) -> None:
        evidence = DischargeEvidence('test-A'); evidence.request_once()
        self.assertTrue(evidence.finish(DischargeReply('test-A', [], ''),
                        action_succeeded=True).ok)
        self.assertTrue(evidence.restore_check().ok)
        with self.assertRaises(RuntimeError): evidence.request_once()

    def test_invalid_combinations(self) -> None:
        for identity, errors, success in (
                ('test-B', [], True), ('test-A', [], False),
                ('test-A', ['CLOSE_FAILED'], True),
                ('test-A', ['DISCHARGE_FAILED', 'CLOSE_FAILED'], True),
                ('test-A', None, True), ('test-A', '', True),
                ('test-A', {}, True), ('test-A', ['NONE'], True)):
            with self.subTest(values=(identity, errors, success)):
                e = DischargeEvidence('test-A'); e.request_once()
                self.assertFalse(e.finish(DischargeReply(identity, errors, ''),
                                 action_succeeded=success).ok)
                self.assertFalse(e.restore_check().ok)

    def test_multiple_errors_preserved_in_detail(self) -> None:
        e = DischargeEvidence('test-A'); e.request_once()
        result = e.finish(DischargeReply('test-A',
            ['DISCHARGE_FAILED', 'CLOSE_FAILED'], 'mock details'), action_succeeded=False)
        for value in ('DISCHARGE_FAILED', 'CLOSE_FAILED', 'mock details'):
            self.assertIn(value, result.detail)
        self.assertFalse(e.restore_check().ok)

    def test_late_success_after_invalidation(self) -> None:
        e = DischargeEvidence('test-A'); e.request_once(); e.invalidate()
        self.assertFalse(e.finish(DischargeReply('test-A', [], ''),
                         action_succeeded=True).ok)
        self.assertFalse(e.restore_check().ok)

    def test_new_transfer_has_no_old_evidence(self) -> None:
        self.assertFalse(DischargeEvidence('test-B').restore_check().ok)

    def test_reply_before_request(self) -> None:
        e = DischargeEvidence('test-A')
        self.assertFalse(e.finish(DischargeReply('test-A', [], ''),
                         action_succeeded=True).ok)
        self.assertFalse(e.restore_check().ok)


class MissionTests(unittest.TestCase):
    def scenario(self, *, errors: tuple[str, ...] = (), success: bool = True,
                 identity: str = 'test-A',
                 cancel: bool = False, timeout: bool = False) -> None:
        # 아래 장치 접수/정지/결과는 전부 시험용이다. 운영 어댑터로 설치하지 않는다.
        evidence = DischargeEvidence('test-A')
        sent = []; angles = []; reports = []; yaw = [0.0]
        requested = threading.Event(); deliver = threading.Event(); canceled = threading.Event()
        ready = threading.Event(); completed = threading.Event(); output = []
        def start(operation: str) -> str:
            sent.append(operation)
            if operation == 'discharge':
                evidence.request_once(); requested.set()
            if operation == 'stop': evidence.invalidate()
            return operation
        def poll(operation: str) -> DeviceResult:
            if operation == 'discharge':
                if not deliver.is_set(): return DeviceResult(False)
                return evidence.finish(DischargeReply(identity, list(errors), 'mock'),
                    action_succeeded=success)
            if operation == 'restore_devices': return evidence.restore_check()
            return DeviceResult(True, True)
        def pose(check: object) -> np.ndarray:
            check(); matrix = np.eye(4)
            matrix[0, 0] = math.cos(yaw[0]); matrix[1, 0] = math.sin(yaw[0])
            return matrix
        def spin(angle: float, allowance: float, check: object) -> None:
            check(); angles.append(angle); yaw[0] += angle; check()
        devices = S(ready=lambda: True, start=start, poll=poll, close=lambda _: None)
        rotation = RotatingTransferDevices(devices,
            S(ready=lambda: True, has_goal=False, execute=spin, cancel=lambda: None, close=lambda: None),
            S(current=pose), S(wait_stopped=lambda check: check()),
            RotationSettings('/test_only/spin', math.pi/2, 1., .02, .03), .3 if timeout else 2., .3)
        def report(value: str) -> None:
            reports.append(value)
            (ready if value == 'DOCK_READY' else completed).set()
        mission = TransferMission(rotation, report, canceled.is_set, lambda: False, 2., .5)
        worker = threading.Thread(target=lambda: output.append(mission.run()))
        worker.start()
        try:
            self.assertTrue(ready.wait(1.))
            self.assertNotIn('discharge', sent)
            self.assertTrue(mission.receive('DOCK_STABLE')[0])
            self.assertTrue(requested.wait(1.))
            # 모의 진행 Feedback이 있어도 terminal 전에는 완료 증거가 없다.
            self.assertFalse(evidence.restore_check().ok)
            self.assertNotIn('TRANSFER_COMPLETE', reports)
            if cancel: canceled.set()
            elif not timeout: deliver.set()
            ok = success and not errors and identity == 'test-A' and not cancel and not timeout
            if ok:
                self.assertTrue(completed.wait(1.))
                self.assertEqual(angles, [math.pi/2])
                self.assertNotIn('restore_devices', sent)
                self.assertTrue(mission.receive('TRANSPORT_CLEAR')[0])
            worker.join(3.)
            self.assertFalse(worker.is_alive())
            self.assertEqual(sent.count('discharge'), 1)
            if ok:
                self.assertEqual(output[0].result_code, 'SUCCESS')
                self.assertTrue(output[0].restore_complete)
                self.assertEqual(angles, [math.pi/2, -math.pi/2])
                self.assertEqual(sent, ['prepare_arm', 'discharge', 'restore_devices'])
            else:
                self.assertNotEqual(output[0].result_code, 'SUCCESS')
                self.assertTrue(output[0].recovery_required)
                self.assertFalse(output[0].transfer_complete)
                self.assertFalse(output[0].restore_complete)
                self.assertNotIn('TRANSFER_COMPLETE', reports)
                self.assertEqual(angles, [math.pi/2])
                self.assertIn('stop', sent)
                self.assertFalse(evidence.restore_check().ok)
        finally:
            canceled.set(); worker.join(3.); rotation.close(None)

    def test_normal_single_request_and_clear_before_reverse(self) -> None:
        self.scenario()
    def test_incomplete_discharge(self) -> None:
        self.scenario(success=False, errors=('DISCHARGE_FAILED',))
    def test_close_failure_after_discharge(self) -> None:
        self.scenario(success=False, errors=('CLOSE_FAILED',))
    def test_inconsistent_success_with_error(self) -> None:
        self.scenario(errors=('CLOSE_FAILED',))
    def test_discharge_and_close_both_fail(self) -> None:
        self.scenario(success=False, errors=('DISCHARGE_FAILED', 'CLOSE_FAILED'))
    def test_wrong_transfer(self) -> None:
        self.scenario(identity='test-B')
    def test_action_failure_even_without_error(self) -> None:
        self.scenario(success=False)
    def test_cancellation(self) -> None:
        self.scenario(cancel=True)
    def test_no_terminal_result_timeout(self) -> None:
        self.scenario(timeout=True)


if __name__ == '__main__': unittest.main()
