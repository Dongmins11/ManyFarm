"""공통 바퀴 계산과 Isaac 장치 경계 검사. 실물 모터 응답 동등성 시험은 아니다."""
import copy
import json
import math
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import patch

import numpy as np


ROOT = Path(__file__).resolve().parents[2]
for tree, package in [('robot', 'farm_common'), ('sim', 'farm_sim_devices')]:
    sys.path.insert(0, str(ROOT / tree / 'ros_ws/src' / package))

from farm_common.kinematics import WheelOdometry
from farm_sim_devices.base_sim import BaseSim


class JointDevice:
    """위치/속도 읽기와 속도 쓰기만 제공하는 SDK 대역. 물리 성공을 가정하지 않는다."""

    def __init__(self, joints: list[str]) -> None:
        self.joints = joints
        self.positions = np.array([1.0, -2.0])
        self.velocities = np.zeros(2)
        self.action = None

    def get_dof_index(self, name: str) -> int:
        return self.joints.index(name)

    def get_joint_positions(self, joint_indices: np.ndarray) -> np.ndarray:
        return self.positions[joint_indices].copy()

    def get_joint_velocities(self, joint_indices: np.ndarray) -> np.ndarray:
        return self.velocities[joint_indices].copy()

    def apply_action(self, action: SimpleNamespace) -> None:
        self.action = action

    def get_world_pose(self) -> None:
        raise AssertionError('제어/odom 계산에서 world 정답 pose를 읽으면 안 됩니다.')


class DriveDeviceContractTests(unittest.TestCase):
    def setUp(self) -> None:
        prims = ModuleType('isaacsim.core.prims')
        types = ModuleType('isaacsim.core.utils.types')
        prims.SingleArticulation = lambda **kwargs: self.device
        types.ArticulationAction = SimpleNamespace
        modules = patch.dict(sys.modules, {
            'isaacsim.core.prims': prims,
            'isaacsim.core.utils.types': types,
        })
        modules.start()
        self.addCleanup(modules.stop)

    def base(self, name: str, servo: bool = False) -> BaseSim:
        config = json.loads((ROOT / 'sim/ros_ws/src/farm_sim_config/config' /
                             f'{name}.json').read_text())['base']
        config = copy.deepcopy(config)
        if not servo:
            config.pop('wheel_velocity_servo', None)
        self.device = JointDevice(config['wheel_joints'])
        self.world = SimpleNamespace(current_time=0.0,
                                     scene=SimpleNamespace(add=lambda robot: robot))
        base = BaseSim(self.world, '/test', config)
        base.initialize()
        self.assertIsInstance(base.odometry, WheelOdometry)
        return base

    def test_twist_preserves_control_wheel_direction_for_both_mountings(self) -> None:
        for name in ('scout', 'harvest'):
            with self.subTest(robot=name):
                base = self.base(name)
                base.command(base.config['wheel_radius_m'] / 2, 0.0)
                np.testing.assert_allclose(self.device.action.joint_velocities,
                                           np.asarray(base.config['wheel_signs']) * 0.5)
                np.testing.assert_array_equal(self.device.action.joint_indices, [0, 1])

    def test_command_with_stalled_encoders_does_not_move_odometry(self) -> None:
        for name in ('scout', 'harvest'):
            with self.subTest(robot=name):
                base = self.base(name)
                base.command(0.1, 0.2)
                for _ in range(10):
                    odom, _, _ = base.sample(0.1)
                    np.testing.assert_array_equal(odom, np.zeros(5))

    def test_encoder_motion_with_zero_command_updates_odometry(self) -> None:
        for name in ('scout', 'harvest'):
            with self.subTest(robot=name):
                base = self.base(name)
                signs = np.asarray(base.config['wheel_signs'])
                self.device.positions += signs * 0.25
                # 읽힌 순간 속도와 이동량은 다를 수 있다. odom은 엔코더 이동량을 적분한다.
                self.device.velocities = signs * 9.0
                odom, _, velocities = base.sample(0.5)
                distance = base.config['wheel_radius_m'] * 0.25
                np.testing.assert_allclose(odom, [distance, 0.0, 0.0, distance / 0.5, 0.0])
                np.testing.assert_allclose(velocities, [9.0, 9.0])

    def test_encoder_counter_wrap_retains_rotation_direction(self) -> None:
        base = self.base('harvest')
        signs = np.asarray(base.config['wheel_signs'])
        self.device.positions += signs * np.array([-0.2, 0.2])
        # 같은 관절각을 다른 2π 표현으로 반환해도 회전량/방향은 유지해야 한다.
        self.device.positions += np.array([2 * math.pi, -2 * math.pi])
        odom, _, _ = base.sample(0.5)
        yaw = 0.4 * base.config['wheel_radius_m'] / base.config['wheel_separation_m']
        np.testing.assert_allclose(odom, [0.0, 0.0, yaw, 0.0, yaw / 0.5], atol=1e-12)

    def test_isaac_servo_brakes_observed_joint_motion_on_zero_command(self) -> None:
        base = self.base('harvest', servo=True)
        self.device.positions += [0.01, -0.01]
        self.world.current_time = 1 / 60
        base.command(0.0, 0.0)
        self.assertLess(self.device.action.joint_velocities[0], 0.0)
        self.assertGreater(self.device.action.joint_velocities[1], 0.0)
        np.testing.assert_array_equal(base.servo.integral, np.zeros(2))


if __name__ == '__main__':
    unittest.main()
