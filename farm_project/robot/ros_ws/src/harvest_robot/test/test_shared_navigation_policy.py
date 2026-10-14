"""같은 수확 코드가 공통 기본값과 환경별 변경 데이터를 읽는지 검사한다."""
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[5]
for package in ('farm_navigation', 'harvest_robot'):
    sys.path.insert(0, str(ROOT / 'robot/ros_ws/src' / package))
from harvest_robot.configuration import load_harvest_config, NAVIGATION_KEYS


class SharedTaskPolicyTests(unittest.TestCase):
    profiles = (
        'robot/config/harvest/harvest_real.json',
        'sim/ros_ws/src/farm_sim_config/config/harvest_task.json',
    )

    def test_real_and_sim_use_one_policy_and_keep_map_data(self) -> None:
        configs = [load_harvest_config(ROOT / p, ROOT) for p in self.profiles]
        self.assertEqual(configs[0]['task_navigation_policy'], configs[1]['task_navigation_policy'])
        self.assertEqual({k: configs[0][k] for k in NAVIGATION_KEYS},
                         {k: configs[1][k] for k in NAVIGATION_KEYS})
        self.assertNotEqual(configs[0]['map_id'], configs[1]['map_id'])
        self.assertNotEqual(configs[0]['sections'], configs[1]['sections'])
        self.assertEqual(configs[0]['approach_controller_id'], 'HarvestApproach')
        self.assertEqual(configs[0]['work_controller_id'], 'HarvestWork')

    def test_environment_can_override_settings_without_changing_shared_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'task.json'
            original = json.loads((ROOT / self.profiles[0]).read_text())
            shared_file = ROOT / original['task_navigation_policy']
            before = shared_file.read_bytes()
            path.write_text(json.dumps(dict(original, resolve_section_from_goal_pose=False)))
            configured = load_harvest_config(path, ROOT)
            self.assertFalse(configured['resolve_section_from_goal_pose'])
            self.assertEqual(configured['work_controller_id'], 'HarvestWork')
            self.assertTrue(load_harvest_config(ROOT / self.profiles[1], ROOT)['resolve_section_from_goal_pose'])
            self.assertEqual(shared_file.read_bytes(), before)

    def test_nested_settings_override_only_explicit_values(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            policy = {'schema_version': 1, 'arm_action': {'timeout_s': 60., 'server_timeout_s': 5.}}
            (root / 'policy.json').write_text(json.dumps(policy))
            (root / 'task.json').write_text(json.dumps({
                'task_navigation_policy': 'policy.json', 'arm_action': {'timeout_s': 120.}}))
            config = load_harvest_config(root / 'task.json', root)
            self.assertEqual(config['arm_action'], {'timeout_s': 120., 'server_timeout_s': 5.})
            self.assertEqual(json.loads((root / 'policy.json').read_text()), policy)

    def test_legacy_explicit_configuration_remains_supported(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'task.json'
            value = {'movement_mode': 'graph_only', 'map_id': 'legacy'}
            path.write_text(json.dumps(value))
            self.assertEqual(load_harvest_config(path, ROOT), value)


if __name__ == '__main__':
    unittest.main()
