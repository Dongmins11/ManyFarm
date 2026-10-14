"""실물 시험 준비만 실행해 공통 설정 원본/해시가 재현 묶음에 포함되는지 검사한다."""
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch
import yaml

ROOT = Path(__file__).resolve().parents[5]
PATH = ROOT / 'robot/tools/tag_camera/bias_trial/trial.py'
SPEC = importlib.util.spec_from_file_location('bias_trial_configuration_snapshot', PATH)
TRIAL = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(TRIAL)


class TrialConfigurationSnapshot(unittest.TestCase):
    def copy_sources(self, root: Path) -> None:
        seeds = ['robot/config/environments/harvest_real.yaml',
            'robot/config/localization/bias_trial_20261010/profile.json',
            'robot/ros_ws/src/farm_tag_localization/farm_tag_localization/node.py',
            'robot/ros_ws/src/farm_tag_localization/farm_tag_localization/pixel_bias.py']
        for source in TRIAL.configuration_sources(ROOT, seeds):
            target = root / source.relative_to(ROOT)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)

    def test_prepare_on_off_snapshots_shared_inputs_without_hardware(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.copy_sources(root)
            with patch.object(TRIAL, 'ROOT', root), patch.object(TRIAL, 'MARKER', root/'marker'):
                for mode in ('on', 'off'):
                    folder = TRIAL.prepare(mode)
                    manifest = json.loads((folder/'manifest.json').read_text())
                    for relative in ('robot/config/navigation/harvest_nav2.yaml',
                        'robot/config/navigation/harvest_navigation.yaml',
                        'robot/config/navigation/harvest_task.yaml',
                        'robot/config/navigation/harvest_navigate_to_pose.xml',
                        'robot/config/navigation/harvest_navigate_through_poses.xml',
                        'robot/config/localization/common_observation_model.json',
                        'robot/config/cameras/pcweb400_720p_report.json'):
                        expected = (root/relative).read_bytes()
                        self.assertEqual(manifest['files'][relative], hashlib.sha256(expected).hexdigest())
                        self.assertEqual((folder/manifest['snapshots'][relative]).read_bytes(), expected)
                    self.assertEqual(manifest['model'] is not None, mode == 'on')

    def test_shared_model_reference_and_overridden_bt_are_included(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root/'model.json').write_text('{}')
            (root/'custom.xml').write_text('<root/>')
            (root/'profile.yaml').write_text(yaml.safe_dump(dict(shared_model_file='model.json',
                overrides={'bt_navigator': {'ros__parameters': {'default_nav_to_pose_bt_xml': 'custom.xml'}}})))
            self.assertEqual(TRIAL.configuration_sources(root, ['profile.yaml']),
                             {root/'profile.yaml', root/'model.json', root/'custom.xml'})

    def test_external_absolute_input_is_copied_inside_bundle_without_overwrite(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)/'project'
            self.copy_sources(root)
            source = Path(directory)/'external_nav.yaml'
            before = (root/'robot/config/robots/vicpinky/nav2.yaml').read_bytes()
            source.write_bytes(before)
            environment = root/'robot/config/environments/harvest_real.yaml'
            profile = yaml.safe_load(environment.read_text())
            profile['nav_params'] = str(source)
            environment.write_text(yaml.safe_dump(profile))
            with patch.object(TRIAL, 'ROOT', root), patch.object(TRIAL, 'MARKER', root/'marker'):
                folder = TRIAL.prepare('off')
            manifest = json.loads((folder/'manifest.json').read_text())
            saved = manifest['snapshots'][str(source)]
            self.assertTrue(saved.startswith('inputs/external/'))
            self.assertEqual((folder/saved).read_bytes(), before)
            self.assertEqual(source.read_bytes(), before)
