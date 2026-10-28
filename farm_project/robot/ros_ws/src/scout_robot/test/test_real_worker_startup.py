"""실제 워커 진입점을 가짜 장치 모듈로 실행해 import 전 설정·종료를 확인한다."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[5]
SCRIPT = ROOT / 'scripts/run_scout_real_worker.py'
spec = importlib.util.spec_from_file_location('real_worker_entry', SCRIPT)
entry = importlib.util.module_from_spec(spec)
spec.loader.exec_module(entry)


class StartupTests(unittest.TestCase):
    def test_both_model_roots_and_missing_model(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            for name in ('project', 'legacy'):
                (root/name).mkdir()
                (root/name/'model.pt').touch()
            cfg = dict(model='model.pt', legacy_directory=str(root/'legacy'))
            for base in ('project', 'legacy'):
                cfg['model_base'] = base
                self.assertEqual(entry.resolve_model_path(cfg, root/'project'), root/base/'model.pt')
            cfg['model'] = 'missing.pt'
            with self.assertRaises(FileNotFoundError):
                entry.resolve_model_path(cfg, root/'project')

    def test_offline_before_import_ready_and_clean_shutdown(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root/'model.pt').touch()
            (root/'detect_capture.py').write_text('''import os
assert os.environ.get('YOLO_OFFLINE') == 'true', 'offline must precede import'
class torch:
    @staticmethod
    def set_num_threads(n): assert n == 2
def YOLO(path, task):
    assert task == 'segment'
    return object()
''')
            (root/'scout_realsense_camera.py').write_text('''class ConfiguredCamera:
    def __init__(self, cfg): assert cfg['warmup_frames'] == 30
    def start(self): return {'test': True}
    def close(self): pass
''')
            (root/'scout_mjpeg.py').write_text('''class Viewer:
    def __init__(self, camera): pass
    def close(self): pass
''')
            config = root/'config.json'
            config.write_text(json.dumps(dict(legacy_directory=str(root), model='model.pt',
                                              camera={'warmup_frames': 30})))
            env = dict(os.environ)
            env.pop('YOLO_OFFLINE', None)
            result = subprocess.run([sys.executable, str(SCRIPT), '--config', str(config)],
                                    input='{"op":"stop"}\n', capture_output=True, text=True,
                                    env=env, timeout=10)
            self.assertEqual(result.returncode, 0, result.stderr)
            ready = json.loads(result.stdout.split('FARM_RPC ', 1)[1])
            self.assertTrue(ready['ready'])
            for stage in ('imports_s', 'model_load_s', 'camera_start_s'):
                self.assertIn(stage, ready['timings'])
                self.assertIn(stage, result.stderr)


if __name__ == '__main__':
    unittest.main()
