"""launch가 실행하는 실제 Python 파일의 진입점을 검사합니다. Isaac 설치 불필요."""
from pathlib import Path
import subprocess
import sys
import unittest

RUNNER = Path(__file__).resolve().parents[1] / 'ros_ws/src/farm_sim_runtime/farm_sim_runtime/run_fleet.py'


class FleetEntrypointTests(unittest.TestCase):
    def test_help_reaches_argument_parser(self) -> None:
        result = subprocess.run([sys.executable, str(RUNNER), '--help'],
                                capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('--fleet-config', result.stdout)
        self.assertIn('--project-root', result.stdout)

    def test_missing_required_arguments_fail(self) -> None:
        result = subprocess.run([sys.executable, str(RUNNER)],
                                capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn('--fleet-config', result.stderr)


if __name__ == '__main__':
    unittest.main()
