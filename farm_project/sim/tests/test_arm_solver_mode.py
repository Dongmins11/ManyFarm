"""팔 작업/복귀의 학습 물리와 주행 제동 설정 전환을 검증한다."""
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'ros_ws/src/farm_sim_runtime'))
from farm_sim_runtime.teacher_arm_alignment import update_arm_solver_mode


class ArmSolverModeTests(unittest.TestCase):
    def test_work_and_blocked_recovery_keep_training_solver_then_restore_drive(self):
        robot = Mock()
        current = [64]
        robot.get_solver_position_iteration_count.side_effect = lambda: current[0]
        robot.set_solver_position_iteration_count.side_effect = lambda n: current.__setitem__(0, n)
        config = dict(solver_position_iterations=64, harvest_solver_position_iterations=12)
        # 작업 시작/작업중/복귀/접힘 미확인/최종 주행 허용 순서.
        for busy, stowed, expected in ((True, True, 12), (True, False, 12),
                                      (False, False, 12), (False, True, 64)):
            update_arm_solver_mode(robot, config, arm_active=busy or not stowed)
            self.assertEqual(current[0], expected)
        self.assertEqual(robot.set_solver_position_iteration_count.call_count, 2)

    def test_profile_without_override_preserves_existing_behavior(self):
        robot = Mock()
        self.assertIsNone(update_arm_solver_mode(robot, {}, arm_active=True))
        robot.set_solver_position_iteration_count.assert_not_called()

    def test_failed_physics_write_is_not_silently_accepted(self):
        robot = Mock()
        robot.get_solver_position_iteration_count.return_value = 64
        with self.assertRaisesRegex(RuntimeError, 'solver 전환 실패'):
            update_arm_solver_mode(robot, dict(harvest_solver_position_iterations=12), arm_active=True)


if __name__ == '__main__':
    unittest.main()
