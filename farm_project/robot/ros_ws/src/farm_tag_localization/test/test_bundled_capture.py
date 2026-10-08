"""실물 없이 저장소 내부 캡처 경로·캘리브레이션·기존 CLI 호환을 검증한다."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import yaml

ROOT = Path(__file__).resolve().parents[5]
MODULE = Path(__file__).resolve().parents[1] / 'farm_tag_localization/capture_session.py'
SPEC = importlib.util.spec_from_file_location('bundled_capture_session', MODULE)
CAPTURE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CAPTURE)
SCRIPT = ROOT / 'robot/tools/tag_camera/pinky_tag_capture_compare.py'
CALIBRATION = ROOT / 'robot/config/cameras/pcweb400_720p_report.json'


class BundledCapture(unittest.TestCase):
    def test_plan_from_foreign_directory_without_legacy_home(self) -> None:
        with tempfile.TemporaryDirectory(prefix='camera home ') as folder:
            env = dict(os.environ, HOME=folder)
            result = subprocess.run([sys.executable, str(SCRIPT), '--trial-label', 'manual_2ms', '--plan'],
                                    cwd=folder, env=env, capture_output=True, text=True, check=True)
        plan = json.loads(result.stdout)
        self.assertEqual(plan['calibration'], str(CALIBRATION))
        self.assertEqual(plan['ids'], list(range(100, 107)))
        self.assertEqual(plan['resolution'], [1280, 720])
        self.assertEqual(plan['requested_exposure_s'], .002)
        self.assertEqual(plan['ros_domain_id'], 178)
        self.assertFalse(plan['motion_commands'])
        self.assertEqual(plan['calibration_sha256'],
                         '7f0512b9f466fb12e36cc424331af727f516670cb9e179dd2c25d7ead8f10e31')

    def test_live_config_uses_bundled_calibration(self) -> None:
        cfg = yaml.safe_load((ROOT / 'robot/config/cameras/harvest_tag_capture.yaml').read_text())
        command = CAPTURE.capture_command(ROOT, cfg, ROOT / 'runs/test session')
        self.assertEqual(command[2], str(SCRIPT))
        self.assertEqual(command[3:5], ['--calibration', str(CALIBRATION)])
        self.assertNotIn('--workspace', command)

    def test_spaces_and_legacy_workspace(self) -> None:
        with tempfile.TemporaryDirectory(prefix='camera space ') as folder:
            root = Path(folder)
            (root / 'camera.py').touch()
            (root / 'cal.json').write_text('{}')
            cfg = dict(script='camera.py', calibration='cal.json', device='/dev/video0', trial_label='manual_2ms')
            command = CAPTURE.capture_command(root, cfg, root / 'out')
            self.assertEqual(command[3:5], ['--calibration', str(root / 'cal.json')])
            del cfg['calibration']
            cfg['workspace'] = str(root)
            self.assertEqual(CAPTURE.capture_command(root, cfg, root / 'out')[3:5], ['--workspace', str(root)])

    def test_missing_and_ambiguous_configuration(self) -> None:
        base = dict(script=str(SCRIPT), device='/dev/video0', trial_label='manual_2ms')
        for extra in ({}, {'workspace': str(ROOT), 'calibration': str(CALIBRATION)}):
            with self.subTest(extra=extra), self.assertRaises(ValueError):
                CAPTURE.capture_command(ROOT, dict(base, **extra), ROOT / 'runs/test')
        with self.assertRaises(FileNotFoundError):
            CAPTURE.capture_command(ROOT, dict(base, calibration='missing.json'), ROOT / 'runs/test')

    def test_wrong_calibration_fails_before_ros_or_camera(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'cal.json'
            path.write_text('{}')
            result = subprocess.run([sys.executable, str(SCRIPT), '--trial-label', 'manual_2ms',
                                     '--calibration', str(path), '--plan'], capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Calibration differs', result.stderr)

    def test_driver_and_recording_code_preserved(self) -> None:
        hashes = {
            'opencv_camera_compare.py': 'ffed74e574ed81611a04ef0359d7c09fdeb1ea5445ed71e8d0073a832a30bbcb',
            'trial_io.py': '4733df115e3771e2e2d50fd7f84a92fd3e05835abd345ccbce4cb9f9f4fb082d',
        }
        for name, expected in hashes.items():
            self.assertEqual(hashlib.sha256((SCRIPT.parent / name).read_bytes()).hexdigest(), expected)


if __name__ == '__main__':
    unittest.main()
