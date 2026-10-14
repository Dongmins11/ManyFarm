"""같은 구현을 양 환경에서 호출하며 설정값은 명시적으로 바꿀 수 있는지 검사한다."""
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace as NS
import unittest
from unittest.mock import patch
import yaml

ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT / 'robot/ros_ws/src/farm_navigation'))
sys.path.insert(0, str(ROOT / 'robot/ros_ws/src/farm_tag_localization'))
sys.path.insert(0, str(ROOT / 'sim/ros_ws/src/farm_sim_devices'))
from farm_tag_localization import ros_capture
from farm_tag_localization.detection import detector_parameters
from farm_tag_localization.launch_support import ros_capture_actions, tag_launch_actions
from farm_tag_localization.runtime import load_observation_model, validate_binding


class Action:
    def __init__(self, *args: object, **kwargs: object) -> None:
        self.args, self.kwargs = args, kwargs


class SharedTagConfiguration(unittest.TestCase):
    def test_model_overrides_merge_without_mutating_shared_defaults(self) -> None:
        shared = ROOT / 'robot/config/localization/common_observation_model.json'
        before = shared.read_bytes()
        with tempfile.TemporaryDirectory() as folder:
            profile = Path(folder) / 'model.json'
            profile.write_text(json.dumps(dict(shared_model_file=str(shared), overrides={
                'quality': {'max_rms_px': 3.5, 'min_area_px2': 1600.},
                'tag': {'distance_interval_m': [.8, 1.4]},
                'model_ids': {'tag': 'edited-camera-model'}})))
            model = load_observation_model(ROOT, str(profile))
        self.assertEqual(model['quality']['max_rms_px'], 3.5)
        self.assertEqual(model['quality']['min_margin'], 80.)
        self.assertEqual(model['tag']['distance_interval_m'], [.8, 1.4])
        self.assertEqual(model['model_ids']['tag'], 'edited-camera-model')
        self.assertEqual(shared.read_bytes(), before)

    def test_active_harvest_models_have_one_source(self) -> None:
        real = yaml.safe_load((ROOT / 'robot/config/localization/harvest_real.yaml').read_text())
        sim = yaml.safe_load((ROOT / 'sim/ros_ws/src/farm_sim_config/config/tag_localization/harvest.yaml').read_text())
        self.assertEqual(real['model_file'], sim['model_file'])
        compatibility = ROOT / 'sim/ros_ws/src/farm_sim_config/config/tag_localization/observation_model.json'
        self.assertEqual(compatibility.resolve(), ROOT / real['model_file'])

    def test_sim_compatibility_import_is_the_same_implementation(self) -> None:
        from farm_sim_devices import tag_capture
        self.assertIs(tag_capture.main, ros_capture.main)
        self.assertIs(tag_capture.detection_record, ros_capture.detection_record)
        self.assertIs(tag_capture.check_camera_info, ros_capture.check_camera_info)

    def test_usb_and_ros_recorders_share_detection_payload(self) -> None:
        path = ROOT / 'robot/tools/tag_camera/pinky_tag_capture_compare.py'
        spec = importlib.util.spec_from_file_location('hardware_capture_shared_test', path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        detection = NS(id=104, family='36h11', hamming=0, decision_margin=92.,
            corners=[NS(x=x, y=y) for x,y in ((400,200),(400,400),(600,400),(600,200))])
        message = NS(header=NS(frame_id='camera', stamp=NS(sec=1, nanosec=2)), detections=[detection])
        common = ros_capture.detection_record(message, 'camera')['detections'][0]
        field = module.detection_record(detection)
        self.assertEqual({key: field[key] for key in common}, common)

    def test_detector_values_can_be_edited_without_forking_code(self) -> None:
        params = detector_parameters({104: .05}, use_sim_time=False,
                                     overrides={'detector.decimate': 1.0, 'detector.threads': 4})
        self.assertEqual(params['detector.decimate'], 1.)
        self.assertEqual(params['detector.threads'], 4)
        self.assertEqual(params['tag.ids'], [104])
        self.assertFalse(params['use_sim_time'])

    def test_real_and_sim_ros_pipeline_differ_only_in_clock_and_paths(self) -> None:
        profile = dict(robot_id='scout_01', tag_localization_config=
            'sim/ros_ws/src/farm_sim_config/config/tag_localization/scout.yaml')
        parameters = []
        for sim in (False, True):
            with patch('launch_ros.actions.Node', Action), \
                    patch('ament_index_python.packages.get_package_share_directory', return_value='/share'), \
                    patch('farm_tag_localization.ros_capture.prepare_capture') as prepare:
                actions, folder = ros_capture_actions(ROOT, profile, use_sim_time=sim,
                                                       output_root='sim/runs/test')
            self.assertEqual(actions[-1].kwargs['package'], 'farm_tag_localization')
            self.assertEqual(actions[-1].kwargs['executable'], 'tag_capture')
            self.assertEqual(prepare.call_args.kwargs, {'use_sim_time': sim})
            detector = dict(actions[1].kwargs['parameters'][0])
            self.assertEqual(detector.pop('use_sim_time'), sim)
            parameters.append(detector)
        self.assertEqual(*parameters)

    def test_real_scout_unknown_calibration_fails_explicitly_before_nodes(self) -> None:
        environment = yaml.safe_load((ROOT / 'robot/config/environments/scout_real.yaml').read_text())
        config = yaml.safe_load((ROOT / environment['tag_localization_config']).read_text())
        self.assertFalse(config['configured'])
        self.assertIsNone(config['assets_file'])
        with self.assertRaisesRegex(ValueError, '실제 예찰 태그 카메라'):
            validate_binding(config, environment, ROOT)
        with patch('launch_ros.actions.Node', Action), \
                self.assertRaisesRegex(ValueError, '미완성 설정.*scout_real.yaml'):
            tag_launch_actions(ROOT, environment, 'real', enabled=True,
                               camera_mode='auto', capture_directory='')
