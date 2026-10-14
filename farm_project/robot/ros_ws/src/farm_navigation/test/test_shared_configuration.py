"""같은 구현/기본값을 재사용하며 환경 설정 변경은 실제 실행값에 반영되는지 검사한다."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest

import yaml

from farm_navigation.configuration import (
    load_environment, load_nav2_parameters, materialize_nav2_parameters,
    merge_mappings, read_mapping,
)

ROOT = Path(__file__).resolve().parents[5]
SIM_CONFIG = ROOT / 'sim/ros_ws/src/farm_sim_config/config'


class SharedConfigurationTests(unittest.TestCase):
    def test_role_profiles_reference_one_common_nav2_and_navigation_default(self) -> None:
        for role, robot in (('scout', 'burger'), ('harvest', 'vicpinky')):
            with self.subTest(role=role):
                real = read_mapping(ROOT / f'robot/config/robots/{robot}/nav2.yaml')
                sim = read_mapping(SIM_CONFIG / f'nav2_{role}.yaml')
                self.assertEqual(real['shared_nav2'], sim['shared_nav2'])
                self.assertNotIn('controller_server', real)
                self.assertNotIn('controller_server', sim)
                paths = [ROOT / f'robot/config/environments/{role}_real.yaml',
                         SIM_CONFIG / f'{role}_runtime.yaml']
                if role == 'scout':
                    paths.append(SIM_CONFIG / 'scout_fleet_runtime.yaml')
                policies = [read_mapping(path)['navigation_policy'] for path in paths]
                self.assertEqual(len(set(policies)), 1)
                for path in paths:
                    source = read_mapping(path)
                    resolved = load_environment(path, ROOT, source['mode'], require_survey=False)
                    expected = merge_mappings(read_mapping(ROOT / policies[0]), source['navigation'])
                    self.assertEqual(resolved['navigation'], expected)

    def test_nested_overrides_replace_lists_without_mutating_inputs(self) -> None:
        defaults = {'node': {'speed': .1, 'timeout': 20., 'limits': [1., 2.]}}
        overrides = {'node': {'speed': .15, 'limits': [3.]}, 'other': {'enabled': True}}
        before = deepcopy((defaults, overrides))
        merged = merge_mappings(defaults, overrides)
        self.assertEqual(merged['node'], {'speed': .15, 'timeout': 20., 'limits': [3.]})
        merged['node']['limits'].append(9.)
        merged['other']['enabled'] = False
        self.assertEqual((defaults, overrides), before)
        for invalid in (None, [], 'speed'):
            with self.assertRaises(ValueError):
                merge_mappings(defaults, invalid)

    def test_nav2_overrides_change_execution_parameters_not_common_source(self) -> None:
        source = SIM_CONFIG / 'nav2_harvest.yaml'
        descriptor = read_mapping(source)
        common = ROOT / descriptor['shared_nav2']
        before = common.read_bytes()
        baseline = load_nav2_parameters(source, ROOT)
        descriptor['overrides'] = {
            'controller_server': {'ros__parameters': {
                'HarvestWork': {'desired_linear_vel': .07},
                'general_goal_checker': {'xy_goal_tolerance': .03},
                'progress_checker': {'movement_time_allowance': 25.},
            }},
            'velocity_smoother': {'ros__parameters': {'max_accel': [.2, 0., 1.]}},
            'amcl': {'ros__parameters': {'update_min_d': .02}},
        }
        with tempfile.TemporaryDirectory() as folder:
            config = Path(folder) / 'nav.yaml'
            config.write_text(yaml.safe_dump(descriptor))
            effective = load_nav2_parameters(config, ROOT)
            controller = effective['controller_server']['ros__parameters']
            self.assertEqual(controller['HarvestWork']['desired_linear_vel'], .07)
            self.assertEqual(controller['general_goal_checker']['xy_goal_tolerance'], .03)
            self.assertEqual(controller['progress_checker']['movement_time_allowance'], 25.)
            self.assertEqual(controller['HarvestWork']['plugin'],
                             baseline['controller_server']['ros__parameters']['HarvestWork']['plugin'])
            self.assertTrue(controller['HarvestWork']['interpolate_curvature_after_goal'])
            self.assertEqual(effective['amcl']['ros__parameters']['update_min_d'], .02)
            self.assertEqual(effective['velocity_smoother']['ros__parameters']['max_accel'], [.2, 0., 1.])
            generated = Path(materialize_nav2_parameters(config, ROOT))
            self.addCleanup(generated.unlink, missing_ok=True)
            self.assertEqual(read_mapping(generated), effective)
        self.assertEqual(common.read_bytes(), before)
        self.assertEqual(load_nav2_parameters(source, ROOT), baseline)

    def test_overridden_bt_path_is_relative_to_environment_file(self) -> None:
        descriptor = read_mapping(SIM_CONFIG / 'nav2_harvest.yaml')
        descriptor['overrides'] = {'bt_navigator': {'ros__parameters': {
            'default_nav_to_pose_bt_xml': 'custom.xml'}}}
        with tempfile.TemporaryDirectory() as folder:
            config = Path(folder) / 'nav.yaml'
            custom = Path(folder) / 'custom.xml'
            custom.write_text('<root/>')
            config.write_text(yaml.safe_dump(descriptor))
            bt = load_nav2_parameters(config, ROOT)['bt_navigator']['ros__parameters']
            self.assertEqual(bt['default_nav_to_pose_bt_xml'], str(custom))
            self.assertEqual(Path(bt['default_nav_through_poses_bt_xml']).parent,
                             ROOT / 'robot/config/navigation')

    def test_navigation_values_override_common_defaults(self) -> None:
        source = SIM_CONFIG / 'harvest_runtime.yaml'
        descriptor = read_mapping(source)
        common = ROOT / descriptor['navigation_policy']
        before = common.read_bytes()
        descriptor['navigation'].update(goal_timeout_s=450., arrival_tolerance_m=.06,
                                        heading_tolerance_rad=.07, max_start_distance_m=.15)
        with tempfile.TemporaryDirectory() as folder:
            config = Path(folder) / 'environment.json'
            config.write_text(json.dumps(descriptor))
            effective = load_environment(config, ROOT, 'sim', require_survey=False)['navigation']
            self.assertEqual(effective['goal_timeout_s'], 450.)
            self.assertEqual(effective['arrival_tolerance_m'], .06)
            self.assertEqual(effective['heading_tolerance_rad'], .07)
            self.assertEqual(effective['max_start_distance_m'], .15)
            self.assertEqual(effective['controller_id'], read_mapping(common)['controller_id'])
        self.assertEqual(common.read_bytes(), before)

    def test_device_bindings_and_shared_bt_paths_resolve_for_both_environments(self) -> None:
        for path in (ROOT / 'robot/config/robots/vicpinky/nav2.yaml', SIM_CONFIG / 'nav2_harvest.yaml'):
            descriptor = read_mapping(path)
            effective = load_nav2_parameters(path, ROOT)
            amcl = effective['amcl']['ros__parameters']
            self.assertEqual(amcl['base_frame_id'], descriptor['bindings']['base_footprint_frame'])
            self.assertEqual(amcl['initial_pose'], descriptor['bindings']['initial_pose'])
            self.assertEqual(amcl['scan_topic'], descriptor['bindings']['scan_topic'])
            for key in ('default_nav_to_pose_bt_xml', 'default_nav_through_poses_bt_xml'):
                bt = Path(effective['bt_navigator']['ros__parameters'][key])
                self.assertTrue(bt.is_file())
                self.assertEqual(bt.parent, ROOT / 'robot/config/navigation')


if __name__ == '__main__':
    unittest.main()
