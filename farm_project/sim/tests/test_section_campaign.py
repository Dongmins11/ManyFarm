"""반복 감독자의 SEC 진행/실패 보존/재개를 실제 ROS 없이 검사한다."""
import argparse
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location(
    'section_campaign', Path(__file__).resolve().parents[1] / 'tools/run_section_campaign.py')
CAMPAIGN = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CAMPAIGN)


class CampaignTest(unittest.TestCase):
    def test_parameter_dump_failure_does_not_abort_ready_robot_test(self):
        from unittest.mock import Mock
        with tempfile.TemporaryDirectory() as tmp:
            events = Mock()
            with patch.object(CAMPAIGN.subprocess, 'run', side_effect=[
                    CAMPAIGN.subprocess.TimeoutExpired('ros2 param dump', 20),
                    argparse.Namespace(returncode=1)]) as run:
                CAMPAIGN.dump_parameters(Path(tmp), ('harvest_01',), events)
            self.assertEqual(run.call_count, 2)
            self.assertEqual(events.call_count, 2)
            self.assertTrue(all(call.args[0] == 'diagnostic_error' for call in events.call_args_list))

    def scout_result(self, count=2):
        return dict(status=4, result=dict(
            section_id='SEC01', result_code='SUCCESS', harvest_task_count=count,
            harvest_tasks=[dict(window_id=f'W{i+1:03d}', expected_count=i+1,
                                goal_pose=dict(position=dict(x=i, y=2, z=0)))
                           for i in range(count)]))

    def test_harvest_failure_reuses_all_windows_and_preserves_source(self):
        """완료한 window도 포함해 원래 예찰 결과를 그대로 복원한다."""
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)
            attempt = output / 'SEC01_attempt_0001'
            attempt.mkdir()
            data = self.scout_result()
            CAMPAIGN.save(attempt / 'result.json', dict(
                status='FAILED', phase='harvest', scout_result=data,
                harvest_results=[dict(window_id='W001', result_code='SUCCESS')]))
            cache = CAMPAIGN.load_scout_cache(output, 'SEC01')
            self.assertEqual(cache['scout_result'], data)
            self.assertEqual(cache['source_attempt'], attempt.name)
            self.assertEqual(len(cache['scout_result']['result']['harvest_tasks']), 2)
            # 캐시가 생긴 뒤 시도 결과가 없어져도 영속 데이터로 재개한다.
            (attempt / 'result.json').unlink()
            self.assertEqual(CAMPAIGN.load_scout_cache(output, 'SEC01'), cache)
            self.assertIsNone(CAMPAIGN.load_scout_cache(output, 'SEC02'))
            self.assertIsNone(CAMPAIGN.load_scout_cache(output / 'other_campaign', 'SEC01'))

    def test_migration_uses_latest_successful_scout_even_while_harvesting(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)
            for index, count in ((1, 3), (2, 2), (3, 4)):
                attempt = output / f'SEC01_attempt_{index:04d}'
                attempt.mkdir()
                data = self.scout_result(count)
                if index == 3:
                    data['result']['result_code'] = 'FAILED'
                CAMPAIGN.save(attempt / 'result.json', dict(
                    status='RUNNING', phase='harvest', scout_result=data))
            cache = CAMPAIGN.load_scout_cache(output, 'SEC01')
            self.assertEqual(cache['source_attempt'], 'SEC01_attempt_0002')
            self.assertEqual(cache['scout_result'], self.scout_result(2))

    def test_failed_wrong_section_or_incomplete_scout_is_not_cached(self):
        with tempfile.TemporaryDirectory() as tmp:
            attempt = Path(tmp) / 'SEC01_attempt_0001'
            attempt.mkdir()
            original = self.scout_result()
            cases = []
            for key, value in (('result_code', 'FAILED'), ('section_id', 'SEC02'),
                               ('harvest_task_count', 3)):
                data = copy.deepcopy(original)
                data['result'][key] = value
                cases.append(data)
            data = copy.deepcopy(original)
            data['status'] = 6
            cases.append(data)
            for data in cases:
                with self.assertRaises(ValueError):
                    CAMPAIGN.cache_scout_result(attempt, 'SEC01', data)
                CAMPAIGN.save(attempt / 'result.json', dict(scout_result=data))
                self.assertIsNone(CAMPAIGN.load_scout_cache(Path(tmp), 'SEC01'))
            self.assertFalse((Path(tmp) / 'scout_cache/SEC01.json').exists())

    def test_empty_success_is_cached_and_corrupt_cache_is_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)
            cache = CAMPAIGN.cache_scout_result(output / 'SEC01_attempt_0001',
                                              'SEC01', self.scout_result(0))
            self.assertEqual(CAMPAIGN.load_scout_cache(output, 'SEC01'), cache)
            cache['map_id'] = 'changed_map'
            CAMPAIGN.save(output / 'scout_cache/SEC01.json', cache)
            with self.assertRaisesRegex(ValueError, '지도/SEC'):
                CAMPAIGN.load_scout_cache(output, 'SEC01')

    def test_overnight_resume_starts_after_completed_sec01(self):
        """SEC01 단독 시험 종료 뒤 같은 캠페인을 SEC16까지 확장한다."""
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)
            attempt = output / 'SEC01_attempt_0004'
            attempt.mkdir()
            CAMPAIGN.save(attempt / 'result.json', dict(status='SUCCESS', phase='complete'))
            CAMPAIGN.save(attempt / 'artifacts.json', dict(files=[]))
            CAMPAIGN.save(output / 'summary.json', dict(started_at='original_start'))
            workers = []

            class Process:
                pid = 999999

                def __init__(self, command, **kwargs):
                    if '--worker' in command:
                        directory = Path(command[command.index('--worker') + 1])
                        workers.append(command[command.index('--sections') + 1])
                        CAMPAIGN.save(directory / 'result.json', dict(
                            status='SUCCESS', phase='complete'))

                def poll(self):
                    return 0

            args = argparse.Namespace(domain=13, sections=[f'SEC{i:02d}' for i in range(1, 17)],
                                      resume=True, isaac_python='unused', vision_python='unused')
            with patch.object(CAMPAIGN.subprocess, 'Popen', Process), \
                    patch.object(CAMPAIGN.subprocess, 'check_output', return_value='test'), \
                    patch.object(CAMPAIGN, 'inventory', return_value={}), \
                    patch.object(CAMPAIGN, 'stop_group'):
                self.assertEqual(CAMPAIGN.campaign(output, args), 0)
            self.assertEqual(workers, args.sections[1:])
            summary = json.loads((output / 'summary.json').read_text())
            self.assertEqual(summary['completed_sections'], args.sections)
            self.assertEqual(summary['started_at'], 'original_start')

    def test_failures_retry_same_section_and_restart_every_attempt(self):
        """두 번 실패 후 SEC01 성공해야 SEC02로 넘어가며 16개를 모두 수행한다."""
        launches, workers, stops = [], [], []
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)

            class Process:
                pid = 999999

                def __init__(self, command, **kwargs):
                    if '--worker' not in command:
                        launches.append(command)
                        return
                    directory = Path(command[command.index('--worker') + 1])
                    section = command[command.index('--sections') + 1]
                    workers.append(section)
                    success = len(workers) > 2
                    CAMPAIGN.save(directory / 'result.json', dict(
                        status='SUCCESS' if success else 'FAILED', phase='harvest',
                        error=None if success else 'injected failure'))

                def poll(self):
                    return 0

            args = argparse.Namespace(domain=13, sections=[f'SEC{i:02d}' for i in range(1, 17)],
                                      resume=False, isaac_python='unused', vision_python='unused')
            with patch.object(CAMPAIGN.subprocess, 'Popen', Process), \
                    patch.object(CAMPAIGN.subprocess, 'check_output', return_value='test'), \
                    patch.object(CAMPAIGN, 'inventory', return_value={}), \
                    patch.object(CAMPAIGN, 'stop_group', side_effect=lambda p: stops.append(p)):
                self.assertEqual(CAMPAIGN.campaign(output, args), 0)
            self.assertEqual(workers[:4], ['SEC01', 'SEC01', 'SEC01', 'SEC02'])
            self.assertEqual(workers[-1], 'SEC16')
            self.assertEqual(len(launches), 18)
            self.assertEqual(len(stops), 36)
            summary = json.loads((output / 'summary.json').read_text())
            self.assertEqual(len(summary['completed_sections']), 16)
            self.assertEqual(len(summary['attempts']), 18)
            self.assertEqual(summary['status'], 'COMPLETE')
            self.assertTrue((output / 'SEC01_attempt_0001/result.json').is_file())
            args.resume = True
            with patch.object(CAMPAIGN.subprocess, 'Popen', side_effect=AssertionError('중복 실행')), \
                    patch.object(CAMPAIGN.subprocess, 'check_output', return_value='test'):
                self.assertEqual(CAMPAIGN.campaign(output, args), 0)
            analysis = json.loads((output / 'failure_analysis.json').read_text())
            self.assertEqual(analysis['failure_groups'][0]['count'], 2)


if __name__ == '__main__':
    unittest.main()
