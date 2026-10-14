"""현장 시작/종료 실패 재현. ROS·실제 장치를 실행하지 않는다."""
import importlib.util
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
import unittest
import yaml

ROOT = Path(__file__).resolve().parents[5]
PKG = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'robot/ros_ws/src/farm_navigation'))
SPEC = importlib.util.spec_from_file_location('runtime_check', ROOT / 'robot/tools/tag_camera/check_runtime.py')
CHECK = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CHECK)


class RuntimeRegressions(unittest.TestCase):
    def test_merge_marker_is_rejected_before_launch(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'node.py'
            path.write_text('<<<<<<< HEAD\na = 1\n=======\na = 2\n>>>>>>> main\n')
            with self.assertRaisesRegex(ValueError, '충돌'):
                CHECK.check_source(path)

    def test_empty_route_operations_are_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, 'operations'):
            CHECK.check_parameters(yaml.safe_load('route_server:\n  ros__parameters:\n    operations: []\n'))
        CHECK.check_parameters(yaml.safe_load((ROOT / 'robot/config/harvest/route_server.yaml').read_text()))

    def test_old_equal_tolerances_fail_real_common_contract(self) -> None:
        from farm_navigation.arrival import validate_goal_checkers, NavigationConfigurationError
        params = {'goal_checker_plugins': ['goal'], 'goal.plugin': 'nav2_controller::SimpleGoalChecker',
                  'goal.xy_goal_tolerance': .05, 'goal.yaw_goal_tolerance': .05236}
        with self.assertRaises(NavigationConfigurationError):
            validate_goal_checkers(params, .05, .05236)

    def test_session_preserves_child_failure_after_interrupt(self) -> None:
        """실제 프로세스/시그널로 하위 실패 1이 상위 성공으로 사라지지 않는지 확인한다."""
        for child_exit in (0, 1):
            with self.subTest(child_exit=child_exit), tempfile.TemporaryDirectory() as folder:
                root = Path(folder)
                script = root / 'capture.py'
                script.write_text('''import argparse,signal,sys,time
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--output-root');a,_=p.parse_known_args()
signal.signal(signal.SIGINT,lambda *_:sys.exit(EXIT))
o=Path(a.output_root)/'current';o.mkdir()
(o/'settings.json').write_text('{}');(o/'detections.jsonl').touch()
while True:time.sleep(.02)
'''.replace('EXIT', str(child_exit)))
                (root / 'cal.json').write_text('{}')
                (root / 'config.yaml').write_text(yaml.safe_dump(dict(script=str(script),
                    calibration='cal.json', device='/unused', trial_label='manual_2ms',
                    output_root='runs', startup_timeout_s=5)))
                env = dict(os.environ, PYTHONPATH=str(PKG))
                code = 'from farm_tag_localization.capture_session import main; raise SystemExit(main())'
                log = root / 'session.log'
                with log.open('w') as stream:
                    process = subprocess.Popen([sys.executable, '-c', code,
                        '--project-root', str(root), '--capture-config', 'config.yaml', '--robot-id', 'test'],
                        stdout=stream, stderr=subprocess.STDOUT, env=env, start_new_session=True)
                    try:
                        deadline = time.monotonic() + 8
                        while 'TAG_CAPTURE_DIRECTORY:' not in log.read_text():
                            if process.poll() is not None or time.monotonic() > deadline:
                                self.fail(log.read_text())
                            time.sleep(.02)
                        process.send_signal(signal.SIGINT)
                        self.assertEqual(process.wait(timeout=8), child_exit, log.read_text())
                    finally:
                        if process.poll() is None:
                            process.send_signal(signal.SIGINT)
                            process.wait(timeout=8)
                receipt = json.loads(next((root / 'runs').glob('*/session.json')).read_text())
                self.assertEqual(receipt['capture_exit'], child_exit)
                self.assertEqual(receipt['clean_shutdown'], child_exit == 0)
                if child_exit:
                    self.assertEqual(receipt['shutdown_errors'], {'capture': 1})


if __name__ == '__main__':
    unittest.main()
