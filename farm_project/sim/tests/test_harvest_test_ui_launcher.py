"""Isaac/ROS 설치 없이 수확 UI 실행 설정의 격리·원본 보존을 검사한다."""
from contextlib import redirect_stdout
from copy import deepcopy
import io
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'sim/tools'))
import harvest_test_ui as launcher


class HarvestTestUILauncherTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        relative = Path('sim/ros_ws/src/farm_sim_config/config')
        shutil.copytree(ROOT / relative, self.root / relative)
        self.fleet = launcher.read_sim_config(self.root, launcher.DEFAULT_FLEET)
        self.evaluation = launcher.read_sim_config(self.root, self.fleet['evaluation_config'])
        self.devices = [launcher.read_sim_config(self.root, path) for path in self.fleet['device_configs']]
        self.device = next(config for config in self.devices if config['robot_id'] == self.evaluation['robot_id'])

    def test_preparation_isolates_ports_snapshots_and_preserves_source(self) -> None:
        before = {path: path.read_bytes() for path in self.root.rglob('*.json')}
        first = launcher.prepare_run(self.root)
        second = launcher.prepare_run(self.root)
        self.assertNotEqual(first.parent, second.parent)
        source_ports = set(self.fleet['clock'].values())
        for config in self.devices:
            source_ports.update(config['runtime'][key] for key in ('command_port', 'telemetry_port'))
        for prepared in (first, second):
            fleet = launcher.read_sim_config(self.root, prepared)
            self.assertEqual(len(fleet['device_configs']), 1)
            device = launcher.read_sim_config(self.root, fleet['device_configs'][0])
            expected = deepcopy(self.device)
            expected['runtime'].update({key: device['runtime'][key] for key in ('command_port', 'telemetry_port')})
            expected['camera']['enabled'] = expected['lidar']['enabled'] = False
            expected['publish_clock'] = False
            self.assertEqual(device, expected)
            ports = [device['runtime'][key] for key in ('command_port', 'telemetry_port')]
            ports.extend(fleet['clock'].values())
            self.assertEqual(len(set(ports)), 4)
            self.assertTrue(all(1024 <= port <= 65535 for port in ports))
            self.assertFalse(set(ports) & source_ports)
            evaluation = launcher.read_sim_config(self.root, fleet['evaluation_config'])
            self.assertEqual(Path(evaluation['evaluation']['snapshot_file']).parent, prepared.parent)
            self.assertNotEqual(evaluation['evaluation']['snapshot_file'], self.evaluation['evaluation']['snapshot_file'])
            self.assertEqual(evaluation['evaluation']['workspace'], self.evaluation['evaluation']['workspace'])
            self.assertEqual(launcher.read_sim_config(self.root, fleet['station_config']),
                             launcher.read_sim_config(self.root, self.fleet['station_config']))
        self.assertEqual({path: path.read_bytes() for path in before}, before)

    def test_invalid_physics_rates_fail_before_creating_run(self) -> None:
        path = self.root / self.device['runtime']['robotarm_physics_config']
        original = json.loads(path.read_text())
        cases = [((), 'enabled', False), (('adaptive',), 'enabled', False),
                 (('adaptive',), 'idle_hz', 120), (('adaptive',), 'harvest_hz', 240),
                 ((), 'physics_hz', 240), ((), 'render_hz', 30)]
        for parents, key, value in cases:
            with self.subTest(key=key, value=value):
                changed = deepcopy(original)
                target = changed
                for parent in parents:
                    target = target[parent]
                target[key] = value
                path.write_text(json.dumps(changed))
                with self.assertRaisesRegex(ValueError, '60Hz / harvest 480Hz'):
                    launcher.prepare_run(self.root)
                self.assertFalse((self.root / 'sim/runs').exists())

    def test_disabled_teacher_is_rejected(self) -> None:
        device = deepcopy(self.device)
        device['runtime']['harvest_arm']['enabled'] = False
        with self.assertRaisesRegex(ValueError, 'harvest_arm'):
            launcher.validate_harvest_config(self.root, device)

    def test_harvest_rate_changes_only_the_isolated_physics_profile(self) -> None:
        before = {path: path.read_bytes() for path in self.root.rglob('*.json')}
        prepared = launcher.prepare_run(self.root)
        for rate in (480, 240, 120, 60, 180):
            with self.subTest(rate=rate):
                launcher.configure_run_harvest_hz(self.root, prepared, rate)
                fleet = launcher.read_sim_config(self.root, prepared)
                device = launcher.read_sim_config(self.root, fleet['device_configs'][0])
                physics_path = Path(device['runtime']['robotarm_physics_config'])
                self.assertEqual(physics_path.parent, prepared.parent)
                physics = launcher.read_sim_config(self.root, physics_path)
                self.assertEqual(physics['adaptive']['harvest_hz'], rate)
                self.assertEqual(physics['adaptive']['idle_hz'], 60)
                self.assertEqual(physics['render_hz'], 60)
                self.assertEqual(physics['physics_hz'], device['runtime']['physics_hz'])
        self.assertEqual({path: path.read_bytes() for path in before}, before)

    def test_harvest_rate_rejects_invalid_rates_and_source_config(self) -> None:
        for rate in (0, -60, 90, True, 240.5):
            with self.subTest(rate=rate), self.assertRaisesRegex(ValueError, 'harvest-hz'):
                launcher.configure_run_harvest_hz(self.root, self.root / launcher.DEFAULT_FLEET, rate)
        with self.assertRaisesRegex(ValueError, '격리 시험'):
            launcher.configure_run_harvest_hz(self.root, self.root / launcher.DEFAULT_FLEET, 240)

    def test_config_outside_sim_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, 'sim 안'):
            launcher.read_sim_config(self.root, self.root / 'outside.json')

    def test_command_uses_gui_source_modules_and_keeps_venv_link(self) -> None:
        target = self.root / 'system-python'
        target.touch()
        executable = self.root / 'venv/bin/python'
        executable.parent.mkdir(parents=True)
        executable.symlink_to(target)
        fleet = launcher.prepare_run(self.root)
        command = launcher.build_command(executable, self.root, fleet, seed=123, duration_s=2.5)
        self.assertEqual(command[0], str(executable))
        self.assertIn('--harvest-test-ui', command)
        self.assertNotIn('--headless', command)
        self.assertEqual(command[command.index('--fleet-config') + 1], str(fleet))
        self.assertEqual(command[command.index('--harvest-test-seed') + 1], '123')
        self.assertEqual(command[command.index('--duration-s') + 1], '2.5')
        modules = [command[index + 1] for index, item in enumerate(command) if item == '--module-path']
        self.assertEqual(modules, [str(self.root / value) for value in (
            'robot/ros_ws/src/farm_common', 'sim/ros_ws/src/farm_sim_devices',
            'sim/ros_ws/src/farm_sim_runtime')])

    def test_environment_removes_ros_python_paths_and_keeps_gui(self) -> None:
        contaminated = {key: 'ROS_PATH' for key in ('PYTHONPATH', 'PYTHONHOME', 'LD_LIBRARY_PATH',
                        'AMENT_PREFIX_PATH', 'CMAKE_PREFIX_PATH', 'COLCON_PREFIX_PATH')}
        source = dict(contaminated, DISPLAY=':0', XAUTHORITY='/tmp/display-cookie', PATH='/usr/bin')
        executable = self.root / 'venv/bin/python'
        environment = launcher.launch_environment(executable, source)
        self.assertFalse(set(contaminated) & environment.keys())
        self.assertEqual(environment['DISPLAY'], ':0')
        self.assertEqual(environment['XAUTHORITY'], '/tmp/display-cookie')
        self.assertEqual(environment['VIRTUAL_ENV'], str(executable.parent.parent))
        self.assertEqual(source['PYTHONPATH'], 'ROS_PATH')

    def test_prepare_only_does_not_launch_or_require_isaac_installation(self) -> None:
        with patch.object(launcher.subprocess, 'run') as run, redirect_stdout(io.StringIO()) as output:
            result = launcher.main(['--project-root', str(self.root), '--isaac-python', '/missing/isaac/python',
                                    '--seed', '9', '--harvest-hz', '240', '--prepare-only'])
        self.assertEqual(result, 0)
        run.assert_not_called()
        self.assertIn('--harvest-test-ui', output.getvalue())
        manifests = list((self.root / 'sim/runs/harvest_test_ui').glob('*/launch.json'))
        self.assertEqual(len(manifests), 1)
        self.assertEqual(json.loads(manifests[0].read_text())['seed'], 9)
        self.assertEqual(json.loads(manifests[0].read_text())['harvest_hz'], 240)

    def test_invalid_duration_is_rejected(self) -> None:
        for duration in (0, -1, float('nan'), float('inf')):
            with self.subTest(duration=duration), self.assertRaisesRegex(ValueError, 'duration-s'):
                launcher.build_command(Path(sys.executable), self.root, Path('fleet.json'), duration_s=duration)


if __name__ == '__main__':
    unittest.main()
