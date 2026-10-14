"""예찰도 수확과 같은 태그 관측기·AMCL 수신기를 선택하는지 조립만 검사한다."""
import importlib.util
from pathlib import Path
import sys
from types import ModuleType
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[5]


class Action:
    def __init__(self, *args: object, **kwargs: object) -> None:
        self.args, self.kwargs = args, kwargs


class Config:
    def __init__(self, key: str) -> None:
        self.key = key

    def perform(self, context: dict) -> str:
        return context[self.key]


class ScoutLaunchContract(unittest.TestCase):
    def assemble(self, enabled: bool, mode: str = 'sim', capture: str = '/capture/scout') -> tuple[list, list]:
        prefix = 'sim' if mode == 'sim' else 'robot'
        profile = dict(robot_id='scout_01', map_id='farm_map_v1',
                       device_config=str(ROOT / prefix / 'd.json'),
                       map_yaml=str(ROOT / prefix / 'm.yaml'),
                       route_graph=str(ROOT / prefix / 'g.json'),
                       nav_params=str(ROOT / prefix / 'n.yaml'),
                       tag_localization_config=prefix + '/t.yaml')
        modules = {}

        def stub(name: str, **attrs: object) -> None:
            module = ModuleType(name)
            module.__dict__.update(attrs)
            modules[name] = module

        stub('ament_index_python')
        stub('ament_index_python.packages', get_package_share_directory=lambda package: '/share/' + package)
        stub('launch', LaunchDescription=Action)
        stub('launch.actions', DeclareLaunchArgument=Action, IncludeLaunchDescription=Action, OpaqueFunction=Action)
        stub('launch.launch_description_sources', PythonLaunchDescriptionSource=Action)
        stub('launch.substitutions', LaunchConfiguration=Config)
        stub('launch_ros')
        stub('launch_ros.actions', Node=Action)
        stub('farm_navigation')
        stub('farm_navigation.configuration', load_environment=lambda *args, **kwargs: profile,
             resolve_file=lambda root, path: root / path,
             read_mapping=lambda path: dict(correction_transport='scan_sync'))
        calls = []
        stub('farm_tag_localization.runtime', validate_binding=lambda *args: calls.append(args))
        with patch.dict(sys.modules, modules):
            path = ROOT / 'robot/ros_ws/src/farm_bringup/launch/scout.launch.py'
            spec = importlib.util.spec_from_file_location('common_scout_tag_contract', path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            actions = module.select_mode(dict(project_root=str(ROOT), mode=mode,
                environment_config=prefix + '/e.yaml', start_isaac='false', rviz='false',
                survey='true', navigation='true', map='', nav_params='', route_file='',
                vision_python='', device='0', headless='true', cmd_vel_type='twist',
                tag_correction=str(enabled).lower(), capture_directory=capture, tag_camera='auto'))
        return actions, calls

    def test_on_selects_shared_scan_sync_receiver_and_adapter_in_both_environments(self) -> None:
        for mode in ('sim', 'real'):
            with self.subTest(mode=mode):
                actions, calls = self.assemble(True, mode)
                self.assertEqual(len(calls), 1)
                navigation = dict(actions[1].kwargs['launch_arguments'])
                self.assertEqual(navigation['tag_scan_sync'], 'true')
                self.assertEqual(navigation['tag_map_id'], 'farm_map_v1')
                survey = dict(actions[2].kwargs['launch_arguments'])
                self.assertEqual(survey['tag_correction'], 'true')
                adapter = actions[3].kwargs
                self.assertEqual(adapter['package'], 'farm_tag_localization')
                self.assertEqual(adapter['executable'], 'tag_amcl_adapter')
                self.assertEqual(adapter['namespace'], 'scout_01')
                self.assertEqual(adapter['parameters'][0]['capture_directory'], '/capture/scout')
                self.assertEqual(adapter['remappings'], [] if mode == 'sim' else
                                 [('/tf', '/scout_01/tf'), ('/tf_static', '/scout_01/tf_static')])

    def test_off_retains_stock_navigation_without_adapter(self) -> None:
        actions, calls = self.assemble(False, capture='')
        self.assertEqual(len(actions), 3)
        self.assertFalse(calls)
        navigation = dict(actions[1].kwargs['launch_arguments'])
        self.assertEqual(navigation['tag_scan_sync'], 'false')
        self.assertEqual(navigation['tag_map_id'], '')
        self.assertEqual(dict(actions[2].kwargs['launch_arguments'])['tag_correction'], 'false')

    def test_on_requires_current_capture(self) -> None:
        with self.assertRaisesRegex(ValueError, 'capture_directory'):
            self.assemble(True, capture='')


if __name__ == '__main__':
    unittest.main()
