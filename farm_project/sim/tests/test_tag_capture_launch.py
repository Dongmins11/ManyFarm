"""실제 시뮬 설정으로 영상 노드 조립을 검사한다. 프로세스와 DDS는 시작하지 않는다."""
import importlib.util
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'sim/ros_ws/src/farm_sim_devices'))
sys.path.insert(0, str(ROOT / 'sim/ros_ws/src/farm_sim_runtime'))
sys.path.insert(0, str(ROOT / 'robot/ros_ws/src/farm_navigation'))
sys.path.insert(0, str(ROOT / 'robot/ros_ws/src/farm_tag_localization'))
from farm_sim_runtime import tag_localization


class Action:
    def __init__(self, *args: object, **kwargs: object) -> None:
        self.args, self.kwargs = args, kwargs


class Config:
    def __init__(self, key: str) -> None:
        self.key = key

    def perform(self, context: dict) -> str:
        return context[self.key]


class Context(dict):
    """전체 launch의 환경 범위도 제공하는 조립 시험 컨텍스트."""
    def __init__(self, **kwargs: object) -> None:
        super().__init__(**kwargs)
        self.environment = {}


class CaptureLaunchTests(unittest.TestCase):
    def assemble(self, enabled: bool, robot: str = 'harvest') -> tuple[list, object]:
        path = ROOT / f'sim/ros_ws/src/farm_sim_runtime/launch/{robot}.launch.py'
        spec = importlib.util.spec_from_file_location('sim_harvest_launch_contract', path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with patch.multiple(module, IncludeLaunchDescription=Action,
                            PythonLaunchDescriptionSource=Action, LaunchConfiguration=Config,
                            get_package_share_directory=lambda package: '/share/' + package), \
                patch.object(module, 'Node', Action, create=True), \
                patch('launch_ros.actions.Node', Action), \
                patch('ament_index_python.packages.get_package_share_directory',
                      lambda package: '/share/' + package), \
                patch('farm_tag_localization.ros_capture.prepare_capture') as capture:
            actions = module.setup(dict(mode='sim', project_root=str(ROOT),
                environment_config=f'sim/ros_ws/src/farm_sim_config/config/{robot}_runtime.yaml',
                start_isaac='false', rviz='false', survey='true', navigation='true',
                vision_python='', device='0', isaac_python='', assets_root='',
                headless='true', cmd_vel_type='twist',
                tag_correction=str(enabled).lower()))
        return actions, capture

    def test_detector_matches_sensor_qos_rectified_topic_and_scoped_sizes(self) -> None:
        actions, capture = self.assemble(True)
        by_executable = {a.kwargs.get('executable'): a.kwargs for a in actions}
        detector = by_executable['apriltag_node']
        parameters = detector['parameters'][0]
        self.assertEqual(parameters['qos_profile'], 'sensor_data')
        self.assertTrue(parameters['use_sim_time'])
        self.assertEqual(detector['namespace'], 'harvest_01/apriltag_camera')
        self.assertEqual(detector['remappings'], [('/tf', 'diagnostic_tf'), ('/tf_static', 'diagnostic_tf_static')])
        self.assertIn(('image', 'image_raw'), by_executable['rectify_node']['remappings'])
        self.assertEqual(by_executable['tag_capture']['namespace'], detector['namespace'])
        assets = json.loads((ROOT / 'sim/ros_ws/src/farm_sim_config/config/tag_localization/assets.json').read_text())
        expected = {tag['tag_id']: tag['edge_m'] for tag in assets['tags']}
        self.assertEqual(dict(zip(parameters['tag.ids'], parameters['tag.sizes'])), expected)
        capture.assert_called_once()
        arguments = next(dict(a.kwargs['launch_arguments']) for a in actions if 'launch_arguments' in a.kwargs)
        self.assertEqual(arguments['tag_camera'], 'false')
        self.assertEqual(arguments['tag_correction'], 'true')
        self.assertTrue(Path(arguments['capture_directory']).is_relative_to(ROOT / 'sim/runs/apriltag'))

    def test_disabled_does_not_create_capture_or_detector(self) -> None:
        for robot in ('scout', 'harvest'):
            with self.subTest(robot=robot):
                actions, capture = self.assemble(False, robot)
                capture.assert_not_called()
                self.assertNotIn('apriltag_node', [action.kwargs.get('executable') for action in actions])
                arguments = next(dict(a.kwargs['launch_arguments']) for a in actions if 'launch_arguments' in a.kwargs)
                self.assertEqual(arguments['tag_correction'], 'false')
                self.assertEqual(arguments['capture_directory'], '')

    def test_scout_and_harvest_share_pipeline_without_crossing_camera_or_capture(self) -> None:
        assembled = {}
        for robot in ('scout', 'harvest'):
            actions, capture = self.assemble(True, robot)
            capture.assert_called_once()
            nodes = {a.kwargs.get('executable'): a.kwargs for a in actions}
            for executable in ('apriltag_node', 'rectify_node', 'tag_capture'):
                self.assertEqual(nodes[executable]['namespace'], robot + '_01/apriltag_camera')
            arguments = next(dict(a.kwargs['launch_arguments']) for a in actions if 'launch_arguments' in a.kwargs)
            self.assertEqual(arguments['tag_correction'], 'true')
            self.assertEqual(arguments['capture_directory'], nodes['tag_capture']['parameters'][0]['capture_directory'])
            assembled[robot] = nodes
        self.assertEqual(assembled['scout']['apriltag_node']['parameters'], assembled['harvest']['apriltag_node']['parameters'])
        scout_capture = assembled['scout']['tag_capture']['parameters'][0]
        harvest_capture = assembled['harvest']['tag_capture']['parameters'][0]
        self.assertNotEqual(scout_capture['capture_directory'], harvest_capture['capture_directory'])
        self.assertNotEqual(scout_capture['assets_file'], harvest_capture['assets_file'])

    def test_all_launch_passes_same_correction_switch_to_both_robots(self) -> None:
        path = ROOT / 'sim/ros_ws/src/farm_sim_runtime/launch/all.launch.py'
        spec = importlib.util.spec_from_file_location('sim_all_tag_contract', path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with patch.multiple(module, IncludeLaunchDescription=Action,
                            PythonLaunchDescriptionSource=Action, LaunchConfiguration=Config,
                            get_package_share_directory=lambda package: '/share/' + package):
            for enabled in ('true', 'false'):
                actions = module.setup(Context(project_root=str(ROOT),
                    environment_config='sim/ros_ws/src/farm_sim_config/config/scout_runtime.yaml',
                    harvest_environment_config='sim/ros_ws/src/farm_sim_config/config/harvest_runtime.yaml',
                    isaac='false', rviz='false', scout='true', harvest='true',
                    navigation='true', survey='true', vision_python='', device='0',
                    headless='true', tag_correction=enabled))
                actions = [a for a in actions[0].get_sub_entities() if isinstance(a, Action)]
                self.assertEqual(len(actions), 2)
                self.assertEqual([dict(a.kwargs['launch_arguments'])['tag_correction'] for a in actions], [enabled, enabled])

    def test_all_launch_forwards_physics_and_measurement_to_isaac_only(self) -> None:
        path = ROOT / 'sim/ros_ws/src/farm_sim_runtime/launch/all.launch.py'
        spec = importlib.util.spec_from_file_location('sim_all_performance_contract', path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with patch.multiple(module, IncludeLaunchDescription=Action,
                            PythonLaunchDescriptionSource=Action, LaunchConfiguration=Config,
                            get_package_share_directory=lambda package: '/share/' + package):
            actions = module.setup(Context(project_root=str(ROOT),
                environment_config='sim/ros_ws/src/farm_sim_config/config/scout_runtime.yaml',
                harvest_environment_config='sim/ros_ws/src/farm_sim_config/config/harvest_runtime.yaml',
                isaac='true', rviz='false', scout='true', harvest='true',
                navigation='true', survey='true', vision_python='', device='0',
                headless='true', tag_correction='true', isaac_python='/isaac/python',
                assets_root='', fleet_config='sim/fleet.json', physics_device='cpu',
                performance_log='sim/runs/test/frames.jsonl'))
        actions = [a for a in actions[0].get_sub_entities() if isinstance(a, Action)]
        arguments = [dict(a.kwargs['launch_arguments']) for a in actions]
        self.assertEqual(arguments[0]['physics_device'], 'cpu')
        self.assertEqual(arguments[0]['performance_log'], 'sim/runs/test/frames.jsonl')
        self.assertEqual(arguments[0]['headless'], 'true')
        self.assertEqual(arguments[0]['fleet_config'], 'sim/fleet.json')
        for robot in arguments[1:]:
            self.assertNotIn('physics_device', robot)
            self.assertEqual(robot['tag_correction'], 'true')


if __name__ == '__main__':
    unittest.main()
