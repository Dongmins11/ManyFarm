"""반복 감독자의 SEC 진행/실패 보존/재개를 실제 ROS 없이 검사한다."""
import argparse
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
