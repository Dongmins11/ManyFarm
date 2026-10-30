"""수확 완료 정책과 실제 팔 endpoint/주변 과실 물리 설정의 일치를 검사한다."""
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'sim/ros_ws/src/farm_sim_runtime'))
from farm_sim_runtime.fleet_config import validate_harvest_action


class HarvestActionConfigTests(unittest.TestCase):
    def setUp(self) -> None:
        base = ROOT/'sim/ros_ws/src/farm_sim_config/config'
        self.task, self.device, self.physics = [json.loads((base/name).read_text())
            for name in ('harvest_task.json', 'harvest.json', 'robotarm_physics.json')]

    def test_deployed_action_uses_arm_and_local_physics(self) -> None:
        self.assertEqual(self.task['completion_policy'], 'ARRIVAL_THEN_ARM')
        self.assertEqual(self.device['runtime']['harvest_arm']['backend'], 'student_u20')
        validate_harvest_action(self.task, self.device, self.physics)

    def test_previous_d435_backend_remains_available(self) -> None:
        self.device['runtime']['harvest_arm']['backend'] = 'student_d435'
        validate_harvest_action(self.task, self.device, self.physics)

    def test_disabled_arm_cannot_silently_complete_on_arrival(self) -> None:
        self.device['runtime']['harvest_arm']['enabled'] = False
        with self.assertRaisesRegex(ValueError, 'enabled'):
            validate_harvest_action(self.task, self.device, self.physics)

    def test_wrong_action_endpoint_fails_before_launch(self) -> None:
        self.task['arm_action']['endpoint'] = 'missing_arm'
        with self.assertRaisesRegex(ValueError, 'endpoint'):
            validate_harvest_action(self.task, self.device, self.physics)

    def test_global_fruit_physics_is_rejected(self) -> None:
        self.physics['adaptive']['enabled'] = False
        with self.assertRaisesRegex(ValueError, 'adaptive'):
            validate_harvest_action(self.task, self.device, self.physics)

    def test_explicit_navigation_only_test_remains_available(self) -> None:
        self.task['completion_policy'] = 'ARRIVAL_ONLY_NO_HARVEST'
        validate_harvest_action(self.task, {}, {})

    def test_unknown_policy_fails_before_launch(self) -> None:
        self.device['runtime']['harvest_arm']['backend'] = 'missing_policy'
        with self.assertRaisesRegex(ValueError, 'backend'):
            validate_harvest_action(self.task, self.device, self.physics)

    def test_student_requires_its_own_profile(self) -> None:
        self.device['runtime']['harvest_arm'].pop('student_profile')
        with self.assertRaisesRegex(ValueError, 'student_profile'):
            validate_harvest_action(self.task, self.device, self.physics)
