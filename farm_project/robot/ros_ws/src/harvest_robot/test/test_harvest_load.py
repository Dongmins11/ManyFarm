"""수량 집계와 실제 공통 통신·인계 경계 검증. ROS/장치 I/O는 대역이다."""
from pathlib import Path
from types import SimpleNamespace as S
from unittest.mock import patch
import importlib.util
import sys
import tempfile
import threading
import unittest

ROOT = Path(__file__).resolve().parents[5]
for package in ('farm_common', 'farm_navigation', 'harvest_robot'):
    sys.path.insert(0, str(ROOT / 'robot/ros_ws/src' / package))
from farm_common.action_handoff import ActionHandoff
from harvest_robot.harvest_load import HarvestLoad
from harvest_robot.configuration import transfer_parameters

class TransferTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.calls=[];self.params={};self.clients=[]
        operations=('prepare_arm','rotate_to_transfer','discharge','restore','stop')
        services={k:'/test/'+k for k in operations}
        self.node=S(config={'robot_id':'harvest_01','transfer':{'device_services':services,
            'journal_path':str(Path(self.temp.name)/'transfer.json')}},callbacks=None,
            lock=threading.Lock(),handoff=ActionHandoff(),busy=False,blocked=False,stopping=False,
            completed_ids=set(),get_clock=lambda:S(ros_time_is_active=False),get_logger=lambda:S(warning=lambda m:None,error=lambda m:None),
            declare_parameter=lambda k,v:self.params.setdefault(k,v),
            get_parameter=lambda k:S(value=self.params[k]),
            create_client=self.client,create_service=lambda *a,**k:S(),
            create_subscription=lambda *a,**k:S())
        action=S(Feedback=S,Result=S)
        modules={'rclpy.action':S(ActionServer=lambda *a,**k:S(),GoalResponse=S(ACCEPT=1,REJECT=0),
                                  CancelResponse=S(ACCEPT=1,REJECT=0)),
                 'farm_interfaces.action':S(DockTransfer=action),
                 'farm_interfaces.srv':S(TransferEvent=object),'std_msgs.msg':S(Int32=object),
                 'std_srvs.srv':S(Trigger=S(Request=S))}
        self.patcher=patch.dict(sys.modules,modules);self.patcher.start();self.addCleanup(self.patcher.stop)
        name='harvest_robot._transfer_integration_test'
        spec=importlib.util.spec_from_file_location(name,ROOT/'robot/ros_ws/src/harvest_robot/harvest_robot/transfer_communication.py')
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        self.server=module.TransferCommunication(self.node)
        self.goal=S(robot_id='harvest_01',task_id='T1',transfer_id='X1',transport_robot_id='transport_01',
                    expected_count=3,timestamp='2026-10-18T12:00:00+09:00')

    def client(self, _type: object, endpoint: str, **kwargs: object) -> object:
        def call(_request: object) -> object:
            self.calls.append(endpoint)
            return S(done=lambda:True,result=lambda:S(success=True,message='confirmed'))
        c=S(service_is_ready=lambda:True,call_async=call)
        self.clients.append(c)
        return c

    def handle(self, canceled: bool=False) -> object:
        def feedback(value: object) -> None:
            self.assertFalse(self.node.handoff.reserve('return','R1'))
            self.assertFalse(self.node.handoff.reserve('work','W1'))
            event={'DOCK_READY':'DOCK_STABLE','TRANSFER_COMPLETE':'TRANSPORT_CLEAR'}[value.event]
            request=S(robot_id='harvest_01',task_id='T1',transfer_id='X1',source_robot_id='transport_01',
                      timestamp=self.goal.timestamp,event=event)
            self.assertTrue(self.server.receive(request,S()).accepted)
        return S(request=self.goal,is_cancel_requested=canceled,publish_feedback=feedback,
                 succeed=lambda:None,canceled=lambda:None,abort=lambda:None)

    def test_real_sequence_waits_for_events_and_preserves_arbitration(self) -> None:
        self.server.loaded_count=3;self.server.transfer_required=True
        self.assertEqual(self.server.accept(self.goal),1)
        result=self.server.execute(self.handle())
        self.assertEqual(self.calls,['/test/'+k for k in ('prepare_arm','rotate_to_transfer','discharge','restore')])
        self.assertEqual(result.result_code,'SUCCESS')
        self.assertTrue(result.restore_complete)
        self.assertEqual(self.server.loaded_count,0)
        self.assertFalse(self.server.transfer_required)
        self.assertIsNone(self.node.handoff.current)
        self.assertFalse(self.node.busy)
        self.assertEqual(self.server.accept(self.goal),0)

    def test_return_reservation_blocks_transfer_without_journal_entry(self) -> None:
        self.node.handoff.reserve('return','R1')
        self.assertEqual(self.server.accept(self.goal),0)
        self.assertEqual(self.server.records,{})
        self.assertEqual(self.calls,[])

    def test_unconnected_devices_reject_without_fake_success(self) -> None:
        self.clients[0].service_is_ready=lambda:False
        self.assertEqual(self.server.accept(self.goal),0)
        self.assertIsNone(self.node.handoff.current)
        self.assertEqual(self.calls,[])

    def test_journal_failure_releases_reservation_but_keeps_motion_blocked(self) -> None:
        with patch.object(self.server,'_save',side_effect=OSError('disk full')):
            self.assertEqual(self.server.accept(self.goal),0)
        self.assertTrue(self.node.blocked)
        self.assertIsNone(self.node.handoff.current)

    def test_cancel_before_physical_operation_does_not_issue_commands(self) -> None:
        self.assertEqual(self.server.accept(self.goal),1)
        result=self.server.execute(self.handle(canceled=True))
        self.assertEqual(result.result_code,'CANCELED')
        self.assertEqual(self.calls,[])
        self.assertIsNone(self.node.handoff.current)

    def test_event_wait_has_no_device_timeout_and_cancel_keeps_recovery_block(self) -> None:
        self.server.stage_timeout_s=.01
        self.assertEqual(self.server.accept(self.goal),1)
        waiting=threading.Event();finished=threading.Event();results=[]
        handle=self.handle();handle.publish_feedback=lambda event:waiting.set()
        def execute():
            try: results.append(self.server.execute(handle))
            finally: finished.set()
        worker=threading.Thread(target=execute,daemon=True);worker.start()
        try:
            self.assertTrue(waiting.wait(1.))
            self.assertFalse(finished.wait(.04))
        finally:
            self.server.cancel(handle)
            handle.is_cancel_requested = True  # ROS가 cancel callback 수락 후 갱신하는 상태
            worker.join(1.)
        self.assertFalse(worker.is_alive())
        result=results[0]
        self.assertEqual(result.result_code,'CANCELED')
        self.assertEqual(result.error_code,'CANCELED')
        self.assertTrue(self.node.blocked)
        self.assertEqual(self.calls[-1],'/test/stop')
        self.assertNotIn('/test/discharge',self.calls)
        self.node.blocked=False
        type(self.server)(self.node)
        self.assertTrue(self.node.blocked)
        self.assertIsNone(self.node.handoff.current)



class HarvestLoadTests(unittest.TestCase):
    def test_two_windows_duplicate_result_and_failed_counts(self):
        load = HarvestLoad()
        load.begin()
        for counts in [(1, 0), (1, 1), (2, 1), (2, 1)]:
            load.observe(*counts)
        load.end()
        self.assertEqual(load.loaded_count, 2)
        load.begin()
        load.observe(1, 2)
        load.end()
        self.assertEqual(load.loaded_count, 3)
        load.reset_after_transfer()
        self.assertEqual(load.loaded_count, 0)
        load.begin(); load.observe(1, 0)
        self.assertEqual(load.loaded_count, 1)

    def test_invalid_samples_do_not_change_total(self):
        load = HarvestLoad(); load.begin(); load.observe(2, 1)
        for counts in [(1, 1), (2, 0), (True, 1), (2147483648, 1)]:
            with self.assertRaises(ValueError):
                load.observe(*counts)
            self.assertEqual(load.loaded_count, 2)
        with self.assertRaises(ValueError):
            load.reset_after_transfer()
        load.end()
        with self.assertRaises(ValueError):
            load.observe(3, 1)

    def test_source_config_and_threshold_validation(self):
        self.assertEqual(transfer_parameters({})['transfer_load_source'], 'external_topic')
        for value in ({'load_source':'bad'}, {'request_count':True},
                      {'request_count':-1}, {'load_source':'arm_feedback','loaded_count_topic':'/load'}):
            with self.assertRaises(ValueError):
                transfer_parameters({'transfer':value})
        self.assertEqual(transfer_parameters({'transfer':{'load_source':'arm_feedback',
                         'request_count':3}})['transfer_request_count'], 3)

class HarvestLoadTransferTests(TransferTests):
    def setUp(self):
        super().setUp()
        self.node.harvest_load = HarvestLoad()
        self.server.load_source = 'arm_feedback'
        self.server.request_count = 3
        self.server.update_harvest_load()

    def add_window(self, success, failed=0):
        with self.node.lock:
            self.node.harvest_load.begin()
            self.node.harvest_load.observe(success, failed)
        self.server.update_harvest_load()
        with self.node.lock:
            self.node.harvest_load.end()

    def test_threshold_continues_harvest_and_successful_handoff_resets(self):
        self.add_window(2, 1)
        self.assertFalse(self.server.snapshot()['transfer_required'])
        self.add_window(1)
        self.assertTrue(self.server.snapshot()['transfer_required'])
        self.assertFalse(self.node.busy)
        self.assertIsNone(self.node.handoff.current)
        self.add_window(2)
        self.assertEqual(self.server.snapshot()['loaded_count'], 5)
        self.server.update_loaded_count(99)
        self.assertEqual(self.server.snapshot()['loaded_count'], 5)
        self.assertEqual(self.server.accept(self.goal), 1)
        result = self.server.execute(self.handle())
        self.assertEqual(result.result_code, 'SUCCESS')
        self.assertEqual(self.node.harvest_load.loaded_count, 0)
        self.assertFalse(self.server.snapshot()['transfer_required'])
        self.add_window(1)
        self.assertEqual(self.server.snapshot()['loaded_count'], 1)

    def test_failed_transfer_preserves_load_and_request(self):
        self.add_window(4)
        self.assertEqual(self.server.accept(self.goal), 1)
        # 원격 인계 계약은 허가를 무기한 기다린다. 실제 장치 실패로 수량 보존을 검사한다.
        original_poll = self.server.devices.poll
        def poll(ticket):
            result = original_poll(ticket)
            if self.calls[-1] == '/test/discharge':
                return S(completed=True, ok=False, detail='test discharge failure')
            return result
        with patch.object(self.server.devices, 'poll', side_effect=poll):
            result = self.server.execute(self.handle())
        self.assertEqual(result.result_code, 'FAILED')
        self.assertEqual(result.error_code, 'DEVICE_FAILED')
        self.assertEqual(self.node.harvest_load.loaded_count, 4)
        self.assertEqual(self.server.snapshot()['loaded_count'], 4)
        self.assertTrue(self.server.snapshot()['transfer_required'])

    def test_default_capacity_policy_and_disabled_threshold(self):
        self.server.request_count = 0
        self.server.capacity = 10
        self.add_window(7)
        self.assertFalse(self.server.transfer_required)
        self.add_window(1)
        self.assertTrue(self.server.transfer_required)
        self.server.capacity = 0; self.server.transfer_required = False
        self.add_window(10)
        self.assertFalse(self.server.transfer_required)

if __name__ == '__main__':
    unittest.main()
