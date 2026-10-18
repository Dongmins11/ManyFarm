"""공통 실행기·실물 설정·기존 인계 동작 연결 회귀. ROS/장치 I/O만 대역이다."""
from pathlib import Path
from types import SimpleNamespace as S
from unittest.mock import patch
import hashlib
import importlib.util
import json
import math
import sys
import tempfile
import threading
import unittest
import yaml

ROOT = Path(__file__).resolve().parents[5]
for package in ('farm_common', 'farm_navigation', 'farm_tag_localization', 'harvest_robot'):
    sys.path.insert(0, str(ROOT / 'robot/ros_ws/src' / package))
from farm_common.action_handoff import ActionHandoff
from farm_navigation.configuration import load_environment, load_nav2_parameters
from farm_navigation.navigation_types import NavigationSettings
from farm_tag_localization.runtime import validate_binding, load_observation_model
from farm_tag_localization.pixel_bias import load_profile
from harvest_robot.configuration import load_harvest_config, approach_navigation_settings, transfer_parameters
from harvest_robot.transfer_mission import TransferMission


class ConfigurationTests(unittest.TestCase):
    def test_real_overrides_leave_sim_and_shared_defaults_unchanged(self) -> None:
        shared = ROOT / 'robot/config/navigation/harvest_nav2.yaml'
        before = shared.read_bytes()
        real = load_nav2_parameters(ROOT/'robot/config/robots/vicpinky/nav2.yaml', ROOT)
        sim = load_nav2_parameters(ROOT/'sim/ros_ws/src/farm_sim_config/config/nav2_harvest.yaml', ROOT)
        for values, distance, resolution in ((real,.1,.025), (sim,.4,.05)):
            c=values['controller_server']['ros__parameters']
            self.assertEqual(c['HarvestApproach']['lookahead_dist'],distance)
            self.assertEqual(c['HarvestApproach']['curvature_lookahead_dist'],distance)
            self.assertEqual(c['progress_checker']['plugin'],'nav2_controller::PoseProgressChecker')
            self.assertEqual(c['progress_checker']['required_movement_angle'],.1)
            self.assertTrue(c['HarvestApproach']['use_collision_detection'])
            self.assertEqual(values['local_costmap']['local_costmap']['ros__parameters']['resolution'],resolution)
        for name in ('local_costmap','global_costmap'):
            c=real[name][name]['ros__parameters']
            self.assertEqual(json.loads(c['footprint']),[[.30,-.25],[.30,.25],[-.30,.25],[-.30,-.25]])
            self.assertEqual(c['footprint_padding'],.02)
        self.assertEqual(shared.read_bytes(),before)

    def test_approach_override_is_optional_and_does_not_change_work(self) -> None:
        settings=NavigationSettings(max_start_distance_m=.1)
        real=load_harvest_config(ROOT/'robot/config/harvest/harvest_real.json',ROOT)
        sim=load_harvest_config(ROOT/'sim/ros_ws/src/farm_sim_config/config/harvest_task.json',ROOT)
        self.assertEqual(approach_navigation_settings(settings,real,'HarvestApproach','general_goal_checker').max_start_distance_m,.2)
        self.assertEqual(approach_navigation_settings(settings,sim,'HarvestApproach','general_goal_checker').max_start_distance_m,.1)
        self.assertEqual(settings.max_start_distance_m,.1)
        for invalid in (True,0,-1,float('nan'),float('inf'),'0.2',None):
            with self.subTest(invalid=invalid),self.assertRaises(ValueError):
                approach_navigation_settings(settings,{'approach_max_start_distance_m':invalid},'RPP','general_goal_checker')

    def test_current_map_tag_and_pixel_bias_are_a_consistent_set(self) -> None:
        env=load_environment(ROOT/'robot/config/environments/harvest_real.yaml',ROOT,'real',require_survey=False)
        config=yaml.safe_load((ROOT/env['tag_localization_config']).read_text())
        validate_binding(config,env,ROOT)
        config['pixel_bias_profile']='robot/config/localization/bias_trial_20261014/profile.json'
        profile=load_profile(config,ROOT)
        self.assertTrue(profile['model_id'].endswith('map20261014'))
        self.assertIn('reference_20261014',config['assets_file'])
        self.assertEqual(config['model_file'],'robot/config/localization/common_observation_model.json')
        self.assertEqual(hashlib.sha256((ROOT/config['model_file']).read_bytes()).hexdigest(),profile['sha256']['model_file'])

    def test_launch_parameters_are_data_driven_and_default_off(self) -> None:
        self.assertFalse(transfer_parameters({})['transfer_enabled'])
        real=load_harvest_config(ROOT/'robot/config/harvest/harvest_real.json',ROOT)
        params=transfer_parameters(real)
        self.assertTrue(params['transfer_enabled'])
        self.assertEqual(json.loads(params['transfer_device_services']),{})
        for bad in (None,[],{'enabled':'true'},{'stage_timeout_s':True}):
            with self.subTest(bad=bad),self.assertRaises(ValueError):
                transfer_parameters({'transfer':bad})


class HandoffTests(unittest.TestCase):
    def test_transfer_excludes_work_return_and_duplicate_without_interrupting(self) -> None:
        h=ActionHandoff()
        self.assertTrue(h.reserve('transfer','T1',preempt=False,interruptible=False))
        token=h.acquire('transfer','T1',lambda:None)
        for kind in ('work','return','transfer'):
            self.assertFalse(h.reserve(kind,'other'))
        self.assertFalse(token.interrupted.is_set())
        h.release('transfer','T1')
        self.assertTrue(h.reserve('return','R1'))

    def test_work_return_preemption_still_waits_for_cleanup(self) -> None:
        h=ActionHandoff();h.reserve('work','W1')
        token=h.acquire('work','W1',lambda:None)
        self.assertTrue(h.reserve('return','R1'))
        self.assertTrue(token.interrupted.is_set())
        self.assertEqual(h.current,('work','W1'))
        self.assertFalse(h.reserve('transfer','T1',preempt=False,interruptible=False))
        h.release('work','W1')
        self.assertEqual(h.acquire('return','R1',lambda:None).task_id,'R1')

    def test_transfer_does_not_preempt_active_work_or_return(self) -> None:
        for kind in ('work','return'):
            h=ActionHandoff();h.reserve(kind,'A')
            token=h.acquire(kind,'A',lambda:None)
            self.assertFalse(h.reserve('transfer','T',preempt=False,interruptible=False))
            self.assertFalse(token.interrupted.is_set())


class TransferTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.calls=[];self.params={};self.clients=[]
        operations=('prepare_arm','rotate_to_transfer','discharge','restore','stop')
        services={k:'/test/'+k for k in operations}
        self.node=S(config={'robot_id':'harvest_01','transfer':{'device_services':services,
            'journal_path':str(Path(self.temp.name)/'transfer.json')}},callbacks=None,
            lock=threading.Lock(),handoff=ActionHandoff(),busy=False,blocked=False,stopping=False,
            completed_ids=set(),get_logger=lambda:S(warning=lambda m:None,error=lambda m:None),
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

    def test_event_timeout_stops_and_keeps_recovery_block_after_restart(self) -> None:
        self.server.stage_timeout_s=.01
        self.assertEqual(self.server.accept(self.goal),1)
        handle=self.handle();handle.publish_feedback=lambda event:None
        result=self.server.execute(handle)
        self.assertEqual(result.result_code,'FAILED')
        self.assertEqual(result.error_code,'EVENT_TIMEOUT')
        self.assertTrue(self.node.blocked)
        self.assertEqual(self.calls[-1],'/test/stop')
        self.assertNotIn('/test/discharge',self.calls)
        self.node.blocked=False
        type(self.server)(self.node)
        self.assertTrue(self.node.blocked)
        self.assertIsNone(self.node.handoff.current)


if __name__=='__main__':
    unittest.main()
