"""실물/Isaac 없이 Teacher 관측·원본 제어·과실별 판정을 검증합니다."""
from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path
import sys
import unittest

import numpy as np

PROJECT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT / 'sim/ros_ws/src/farm_sim_devices'))
HAS_TORCH = importlib.util.find_spec('torch') is not None
if HAS_TORCH:
    import torch
    from farm_sim_devices.teacher_state import TeacherState, SOURCE_HOME, SOURCE_LOWER, SOURCE_UPPER
    from farm_sim_devices._teacher_vendor.quaternion import quat_apply, quat_mul, quat_conjugate


def profile() -> dict:
    result = json.loads((PROJECT / 'sim/ros_ws/src/farm_sim_config/config/teacher_policy.json').read_text())
    result['joint_limits'] = dict(lower=SOURCE_LOWER, upper=SOURCE_UPPER, home=SOURCE_HOME)
    return result


def sample(time_s: float = 0., *, centered: bool = False) -> dict:
    """반대 방향의 양측 contact를 선택할 수 있는 측정 fixture입니다."""
    root = np.array([.55, -.19, .94])
    from farm_sim_devices._teacher_vendor.matched_pull_60hz import TensorGraspKinematics
    from farm_sim_devices.teacher_device import _quaternion
    kin = TensorGraspKinematics(PROJECT/'sim/assets/robotarm_teacher/harvest_training.urdf', .07)
    p, r, _ = kin.pose_and_jacobian(torch.tensor([SOURCE_HOME]))
    return dict(time_s=time_s, q=np.array(SOURCE_HOME), qd=np.zeros(6),
        tcp_position=root + [0., 0., -.006] if centered else p[0].numpy(),
        tcp_quaternion=_quaternion(r[0].numpy()), fruit_position=root,
        fruit_quaternion=np.array([1., 0., 0., 0.]), fruit_com_position=root.copy(),
        fruit_linear_velocity=np.zeros(3), fruit_angular_velocity=np.zeros(3),
        fixed_force=np.array([1., 0., 0.]) if centered else np.zeros(3),
        moving_force=np.array([-1., 0., 0.]) if centered else np.zeros(3),
        fixed_net_force=np.array([1., 0., 0.]) if centered else np.zeros(3),
        moving_net_force=np.array([-1., 0., 0.]) if centered else np.zeros(3),
        arm_forces=np.zeros((4, 3)), attached=True, anchor=root + [.017529832318793216, .012588152566927921, .0375],
        load_N=0., break_timer_s=0., break_threshold_N=2.5, other_detached=False,
        collision_vertices=np.array([[-.03, -.03, -.03], [.03, .03, .03],
                                     [.03, -.03, -.03], [-.03, .03, .03]]), detach_events=[])


@unittest.skipUnless(HAS_TORCH, 'PyTorch 필요')
class TeacherStateTests(unittest.TestCase):
    def state(self, value=None):
        from farm_sim_devices.teacher_policy import TeacherController
        c = TeacherController(profile(), project_root=PROJECT)
        c.start_target('state', value or sample())
        return c.state

    def test_target_only_observation_and_canonical_quaternion(self):
        value = sample(); value['fruit_quaternion'] *= -1
        e = self.state(value); obs = e.observation()['policy'][0].numpy()
        self.assertEqual(obs.shape, (82,))
        np.testing.assert_allclose(obs[25:28], value['fruit_position']-value['tcp_position'], atol=1e-6)
        np.testing.assert_allclose(obs[44:47], obs[25:28])
        np.testing.assert_array_equal(obs[47:68], 0.)
        np.testing.assert_array_equal(obs[68:76], [1., 0., 0., 0., 0., 0., 0., 0.])
        self.assertGreaterEqual(obs[31], 0.)

    def test_sample_shape_and_backward_time_rejected(self):
        e = self.state()
        bad = sample(); bad['q'] = [0.]*5
        with self.assertRaises(ValueError): e.accept_sample(bad)
        e.accept_sample(sample(1.))
        with self.assertRaises(ValueError): e.accept_sample(sample(.5))

    def test_detached_in_box_without_harvest_history_is_not_success(self):
        e = self.state()
        for tick in range(20):
            value = sample(tick*.05); value['attached'] = False
            value['fruit_position'] = np.array([.4, 0., .55])
            e.accept_sample(value)
        self.assertTrue(e.physical_in_box)
        self.assertFalse(e.physical_success)

    def test_observe_never_steps_physics_or_advances_policy(self):
        e = self.state(); before = e.episode_length_buf.clone()
        e.accept_sample(sample(.1))
        torch.testing.assert_close(e.episode_length_buf, before)
