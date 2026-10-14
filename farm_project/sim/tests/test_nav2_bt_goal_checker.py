"""복수 GoalChecker에서도 기존 일반 Nav2 BT의 checker 선택·경로 로딩을 보존합니다."""
import importlib.util
import os
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET

from ament_index_python.packages import get_package_share_directory
from launch import LaunchContext
import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'robot/ros_ws/src/farm_navigation'))
from farm_navigation.configuration import load_nav2_parameters
SPEC = importlib.util.spec_from_file_location('nav2_bt_launch',
    ROOT / 'robot/ros_ws/src/farm_bringup/launch/scout_navigation.launch.py')
NAVIGATION = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(NAVIGATION)
KEYS = ('default_nav_to_pose_bt_xml', 'default_nav_through_poses_bt_xml')


class GoalCheckerTreeTests(unittest.TestCase):
    def test_only_follow_path_goal_checker_differs_from_upstream_tree(self) -> None:
        upstream = Path(get_package_share_directory('nav2_bt_navigator')) / 'behavior_trees'
        for config, checker in (
            ('robot/config/robots/vicpinky/nav2.yaml', 'general_goal_checker'),
            ('sim/ros_ws/src/farm_sim_config/config/nav2_harvest.yaml', 'general_goal_checker'),
        ):
            navpath = ROOT / config
            params = load_nav2_parameters(navpath, ROOT)
            xmls = NAVIGATION._bt_xml_parameters(str(navpath), ROOT)
            self.assertEqual(set(xmls), set(KEYS))
            self.assertIn(checker, params['controller_server']['ros__parameters']['goal_checker_plugins'])
            for key, original in zip(KEYS, ('navigate_to_pose_w_replanning_and_recovery.xml',
                                            'navigate_through_poses_w_replanning_and_recovery.xml')):
                with self.subTest(config=config, key=key):
                    tree = ET.parse(xmls[key]).getroot()
                    follows = tree.findall('.//FollowPath')
                    self.assertEqual(len(follows), 1)
                    self.assertEqual(follows[0].attrib.pop('goal_checker_id'), checker)
                    self.assertEqual(ET.tostring(tree), ET.tostring(ET.parse(upstream / original).getroot()))
                    content = Path(xmls[key]).read_text()
                    self.assertIn('SPDX-License-Identifier: Apache-2.0', content)
                    self.assertIn('/1.3.12/nav2_bt_navigator/behavior_trees/', content)


class TreePathTests(unittest.TestCase):
    def write_config(self, directory: Path, params: dict) -> Path:
        path = directory / 'nav2.yaml'
        path.write_text(yaml.safe_dump({'bt_navigator': {'ros__parameters': params}}))
        return path

    def test_relative_paths_use_selected_config_parent_and_absolute_paths_stay_absolute(self) -> None:
        with TemporaryDirectory() as temporary:
            directory = Path(temporary)
            relative = directory / 'subdir' / 'pose.xml'
            relative.parent.mkdir()
            relative.write_text('<root/>')
            absolute = directory / 'through.xml'
            absolute.write_text('<root/>')
            path = self.write_config(directory, dict(zip(KEYS, ('subdir/pose.xml', str(absolute)))))
            self.assertEqual(NAVIGATION._bt_xml_parameters(str(path)),
                             {KEYS[0]: str(relative), KEYS[1]: str(absolute)})

    def test_omitted_and_empty_paths_keep_nav2_defaults(self) -> None:
        with TemporaryDirectory() as temporary:
            directory = Path(temporary)
            for params in ({}, {KEYS[0]: ''}, {KEYS[1]: None}):
                self.assertEqual(NAVIGATION._bt_xml_parameters(str(self.write_config(directory, params))), {})
            path = directory / 'without_navigator.yaml'
            path.write_text('controller_server: {}\n')
            self.assertEqual(NAVIGATION._bt_xml_parameters(str(path)), {})

    def test_missing_and_invalid_explicit_paths_fail_before_launch(self) -> None:
        with TemporaryDirectory() as temporary:
            directory = Path(temporary)
            path = self.write_config(directory, {KEYS[0]: 'missing.xml'})
            with self.assertRaises(FileNotFoundError):
                NAVIGATION._bt_xml_parameters(str(path))
            for value in (True, 123, [], {}, ' '):
                with self.subTest(value=value), self.assertRaises(ValueError):
                    NAVIGATION._bt_xml_parameters(str(self.write_config(directory, {KEYS[0]: value})))

    def test_only_bt_navigator_receives_resolved_overrides(self) -> None:
        with TemporaryDirectory() as temporary:
            directory = Path(temporary)
            xml = directory / 'goal.xml'
            xml.write_text('<root/>')
            path = self.write_config(directory, {KEYS[0]: 'goal.xml'})
            dummy = directory / 'map.yaml'
            dummy.write_text('image: dummy.pgm\n')
            with patch.dict(os.environ, {'ROS_LOG_DIR': str(directory / 'logs')}):
                context = LaunchContext()
            context.launch_configurations.update(mode='real', robot_id='harvest_01',
                map=str(dummy), nav_params=str(path), route_file=str(dummy),
                tag_scan_sync='false', tag_map_id='', rviz='false')
            nodes = []

            def node(**kwargs):
                nodes.append(kwargs)
                return SimpleNamespace(**kwargs)

            with patch.object(NAVIGATION, 'Node', side_effect=node):
                NAVIGATION.setup(context)
            for created in nodes:
                overrides = [p for p in created.get('parameters', [])
                             if isinstance(p, dict) and any(key in p for key in KEYS)]
                if created.get('name') == 'bt_navigator':
                    self.assertEqual(overrides, [{KEYS[0]: str(xml)}])
                else:
                    self.assertEqual(overrides, [], created.get('name'))


if __name__ == '__main__':
    unittest.main()
