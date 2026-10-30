"""외부 접속/종료 없이 시험 콘솔의 경계·프로세스 식별을 검증한다."""
from pathlib import Path
import io
import json
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from arm_session import ArmSession
from backend import Backend
import process_agent


class ConsoleUnitTests(unittest.TestCase):
    def config(self, directory: str) -> dict:
        return dict(state_dir=directory, robot_jetson_release='/robot/release',dummy_root='/pc/dummy')

    def test_raw_command_and_unconfirmed_hardware_request_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            session=ArmSession(self.config(directory))
            with self.assertRaises(ValueError):session.send('shell',{})
            with self.assertRaisesRegex(ValueError,'확인'):session.send('harvest',{})
            with self.assertRaisesRegex(ValueError,'대조'):session.send('recover',{'confirmed':True})

    def test_transfer_test_requires_confirmation_and_boolean(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            session=ArmSession(self.config(directory))
            with self.assertRaisesRegex(ValueError,'확인'):
                session.send('transfer_test',{'enabled':True})
            with self.assertRaisesRegex(ValueError,'bool'):
                session.send('transfer_test',{'confirmed':True,'enabled':'false'})

    def test_process_groups_are_fixed_and_source_paths_are_not_browser_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            backend=Backend(self.config(directory))
            with self.assertRaises(ValueError):backend.process_rules('/bin/anything')
            remote,rules=backend.process_rules('robot_arm_bridge')
            self.assertTrue(remote)
            self.assertIn('/robot/release/config/zenoh-pinky-jetson.json',[x['marker'] for x in rules])

    def test_changed_inventory_does_not_signal(self) -> None:
        with patch.object(process_agent,'collect',return_value={'4':{'ticks':'a'}}),patch.object(process_agent.os,'kill') as kill:
            with self.assertRaises(ValueError):process_agent.stop([], 'outdated')
            kill.assert_not_called()

    def test_pid_reuse_never_signaled(self) -> None:
        before={'4':{'ticks':'old','ppid':1,'args':['known']}}
        after={'4':{'ticks':'new','ppid':1,'args':['known']}}
        with patch.object(process_agent,'collect',side_effect=[before,after,{},after,{},{}]),patch.object(process_agent.os,'kill') as kill:
            result=process_agent.stop([],process_agent.fingerprint(before))
            kill.assert_not_called()
            self.assertTrue(result['ok'])

    def test_requested_and_received_events_are_distinct(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            session=ArmSession(self.config(directory))
            class Process:
                stdin=io.StringIO()
                def poll(self) -> None:return None
            session._process=Process();session._connected=True
            result=session.send('stop',{'confirmed':True})
            self.assertTrue(result['queued'])
            self.assertEqual(session.view()['events'][-1]['kind'],'requested')
            self.assertEqual(json.loads(session._process.stdin.getvalue())['action'],'stop')
            self.assertNotIn('success',result)

    def test_station_return_uses_config_and_unique_ids_not_browser_goal(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'station.json'
            path.write_text(json.dumps(dict(map_id='map',stations={'robot':dict(station_id='configured',node_id=18)})))
            cfg=dict(self.config(folder),robot_id='robot',station_return_config=str(path))
            session=ArmSession(cfg)
            class Process:
                stdin=io.StringIO()
                def poll(self) -> None:return None
            session._process=Process();session._connected=True
            with self.assertRaisesRegex(ValueError,'확인'):session.send('station_return',{})
            for _ in range(2):session.send('station_return',{'confirmed':True,'goal':{'station_id':'injected'}})
            goals=[json.loads(x)['body']['goal'] for x in session._process.stdin.getvalue().splitlines()]
            self.assertNotEqual(goals[0]['task_id'],goals[1]['task_id'])
            self.assertEqual(goals[0]['station_id'],'configured')
            self.assertEqual(session.view()['station']['node_id'],18)

    def test_move_target_uses_graph_and_ignores_browser_pose(self) -> None:
        root=Path(__file__).resolve().parents[4]
        with tempfile.TemporaryDirectory() as folder:
            cfg=dict(self.config(folder),project_root=str(root),
                navigation_trial_config=str(root/'robot/tools/terminal/dinit.json'))
            session=ArmSession(cfg)
            class Process:
                stdin=io.StringIO()
                def poll(self) -> None:return None
            session._process=Process();session._connected=True
            session.send('move_trial',{'confirmed':True,'goal':{'pose':'injected'}})
            goal=json.loads(session._process.stdin.getvalue())['body']['goal']
            self.assertEqual(session.view()['navigation']['node_id'],14)
            self.assertAlmostEqual(goal['pose']['pose']['position']['x'],3.576)
            self.assertEqual(goal['pose']['pose']['orientation']['w'],1.)


class ResultContractTests(unittest.TestCase):
    def test_wrong_task_cannot_be_reported_as_success(self) -> None:
        from arm_agent import result_success
        from types import SimpleNamespace as S
        goal=S(robot_id='test',harvest_task=S(task_id='expected',window_id='w',expected_count=0))
        payload=dict(robot_id='test',task_id='other',window_id='w',expected_count=0,result_code='SUCCESS',harvested_count=0,failed_count=0)
        with self.assertRaises(ValueError):result_success('harvest',goal,payload,4)

    def test_discharge_rejects_mismatched_transfer(self) -> None:
        from arm_agent import result_success
        from types import SimpleNamespace as S
        with self.assertRaises(ValueError):
            result_success('discharge',S(transfer_id='expected'),{'transfer_id':'other','error_codes':[]},4)

    def test_station_success_does_not_require_docked_and_checks_identity(self) -> None:
        from arm_agent import result_success
        from types import SimpleNamespace as S
        goal=S(robot_id='robot',task_id='task',station_id='station')
        payload=dict(robot_id='robot',task_id='task',station_id='station',result_code='SUCCESS',error_code='NONE',docked=False)
        self.assertTrue(result_success('station_return',goal,payload,4))
        payload['task_id']='wrong'
        with self.assertRaises(ValueError):result_success('station_return',goal,payload,4)

if __name__=='__main__':unittest.main()
