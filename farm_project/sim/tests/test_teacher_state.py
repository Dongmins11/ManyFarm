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
    return dict(time_s=time_s, q=np.array(SOURCE_HOME), qd=np.zeros(6),
        tcp_position=root + [0., 0., -.006] if centered else np.array([.45, -.19, .98]),
        tcp_quaternion=np.array([1., 0., 0., 0.]), fruit_position=root,
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


@unittest.skipUnless(HAS_TORCH, 'Teacher 검사는 PyTorch 환경에서 수행합니다.')
class TeacherStateTests(unittest.TestCase):
    def state(self, value: dict | None = None) -> TeacherState:
        p = profile()
        e = TeacherState(p['runtime'], p['joint_limits'], value or sample())
        e.expert_stage = torch.tensor([-1])
        e.entry_grasp_active = torch.tensor([True])
        return e

    def interval(self, state: TeacherState, value: dict, action: torch.Tensor | None = None) -> None:
        state.prepare_action(torch.zeros(1, 6) if action is None else action)
        state.accept_sample(value)
        state.finish_control_interval()

    def test_full_observation_layout_and_target_only_padding(self) -> None:
        s = sample()
        e = self.state(s)
        obs = e.observation()['policy'][0].numpy()
        expected = np.concatenate((2 * (s['q'] - SOURCE_LOWER) / (np.array(SOURCE_UPPER) - SOURCE_LOWER) - 1,
            s['qd'] / 1.5, np.zeros(6), s['tcp_position'], s['tcp_quaternion'],
            s['fruit_position'] - s['tcp_position'], s['fruit_linear_velocity'], s['fruit_quaternion'],
            np.array([.4, 0., .8]) - s['tcp_position'], [1., 0., 0., 0., 1., 0.],
            s['fruit_position'] - s['tcp_position'], np.zeros(21), [1.], np.zeros(7),
            s['anchor'] - s['tcp_position'], [0., 0., 1.]))
        self.assertEqual(obs.shape, (82,))
        np.testing.assert_allclose(obs, expected, atol=1e-6)
        np.testing.assert_array_equal(obs[47:68], 0.)
        np.testing.assert_array_equal(obs[69:76], 0.)

    def test_normalized_action_increment_and_gripper_antiwindup(self) -> None:
        e = self.state()
        e.prepare_action(torch.full((1, 6), -2.))
        expected = np.array(SOURCE_HOME) - ([.04] * 5 + [0.])
        expected[-1] = SOURCE_HOME[-1] - .04
        np.testing.assert_allclose(e.targets[0], expected, atol=1e-6)
        np.testing.assert_allclose(e.actions[0], -1.)

    def test_compliant_squeeze_released_by_positive_opening(self) -> None:
        e = self.state()
        e.squeeze_active[:] = True
        e.prepare_action(torch.zeros(1, 6))
        self.assertAlmostEqual(float(e.targets[0, -1]), SOURCE_HOME[-1] - .035, places=6)
        e.prepare_action(torch.tensor([[0., 0., 0., 0., 0., .15]]))
        self.assertFalse(bool(e.squeeze_active[0]))
        self.assertAlmostEqual(float(e.targets[0, -1]), SOURCE_HOME[-1] - .035 + .009, places=6)

    def test_grasp_requires_continuous_bilateral_hold(self) -> None:
        e = self.state(sample(centered=True))
        for tick in range(1, 5):
            self.interval(e, sample(tick * .05, centered=True))
            self.assertFalse(bool(e.has_grasped[0]))
        self.interval(e, sample(.25, centered=True))
        self.assertTrue(bool(e.has_grasped[0]))

    def test_contact_interruption_resets_grasp_timer(self) -> None:
        e = self.state(sample(centered=True))
        for tick in range(1, 4):
            self.interval(e, sample(tick * .05, centered=True))
        self.interval(e, sample(.20))
        self.assertEqual(float(e.grip_time[0]), 0.)
        self.assertFalse(bool(e.has_grasped[0]))

    def test_unobserved_detach_is_not_valid_harvest(self) -> None:
        e = self.state()
        s = sample(.05)
        s['attached'] = False
        self.interval(e, s)
        self.assertFalse(bool(e.valid_detach[0]))
        self.assertEqual(e.assignment_status, 'FAILED')
        self.assertIn('bad_detach', e.failure_reason())

    def test_substep_break_evidence_then_retention(self) -> None:
        e = self.state(sample(centered=True))
        for tick in range(1, 6):
            self.interval(e, sample(tick * .05, centered=True))
        e.entry_grasp_active[:] = False
        e.expert_stage[:] = 0
        s = sample(.30, centered=True)
        s['attached'] = False
        event = {key: copy.deepcopy(s[key]) for key in ('fruit_position', 'fruit_quaternion',
            'tcp_position', 'tcp_quaternion', 'fixed_force', 'moving_force')}
        event.update(time_s=.275, tip_displacement=[-.02, 0., 0.])
        s['detach_events'] = [event]
        self.interval(e, s)
        self.assertTrue(bool(e.valid_detach[0]))
        self.assertFalse(bool(e.has_retained[0]))
        for tick in range(7, 16):
            s = sample(tick * .05, centered=True)
            s['attached'] = False
            self.interval(e, s)
        self.assertTrue(bool(e.has_retained[0]))
        self.assertEqual(e.assignment_status, 'RUNNING')

    def test_physical_basket_dwell_is_separate_from_teacher_success(self) -> None:
        e = self.state()
        s = sample()
        s.update(attached=False, fruit_position=np.array([.4, 0., .6]),
                 fruit_com_position=np.array([.4, 0., .6]))
        for tick in range(1, 12):
            s['time_s'] = tick * .05
            e.accept_sample(s)
            self.assertFalse(e.physical_success)
        s['time_s'] = .6
        e.accept_sample(s)
        self.assertTrue(e.physical_success)
        self.assertFalse(e.diagnostics()['teacher_strict_success'])
        s['time_s'] = .65
        s['fruit_position'][0] = .7
        e.accept_sample(s)
        self.assertFalse(e.physical_success)
        self.assertEqual(e.physical_place_time, 0.)

    def test_detach_diagnostics_preserve_physics_event_before_zero_load_sample(self) -> None:
        e = self.state(sample(centered=True))
        for tick in range(1, 6):
            self.interval(e, sample(tick * .05, centered=True))
        e.entry_grasp_active[:] = False
        e.expert_stage[:] = 0
        s = sample(.30, centered=True)
        s.update(attached=False, load_N=0., break_timer_s=0.)
        event = {key: copy.deepcopy(s[key]) for key in ('fruit_position', 'fruit_quaternion',
            'tcp_position', 'tcp_quaternion', 'fixed_force', 'moving_force')}
        event.update(time_s=.275, tip_displacement=[-.02, 0., 0.],
                     break_timer_s=20/480, load_N=1.73)
        s['detach_events'] = [event]
        self.interval(e, s)
        self.assertTrue(bool(e.valid_detach[0]))
        self.assertAlmostEqual(e.diagnostics()['break_load_N'], 1.73, places=6)
        self.assertAlmostEqual(e.diagnostics()['break_dwell_s'], 20/480, places=7)
        # 다음 제어 sample에 event가 없고 현재 줄기 힘0이어도 과거 분리 증거는 남습니다.
        later = sample(.35, centered=True)
        later.update(attached=False, load_N=0., break_timer_s=0.)
        self.interval(e, later)
        self.assertAlmostEqual(e.diagnostics()['break_load_N'], 1.73, places=6)
        self.assertAlmostEqual(e.diagnostics()['break_dwell_s'], 20/480, places=7)

    def test_zero_event_tension_with_overtravel_is_not_replaced_by_current_load(self) -> None:
        e = self.state()
        s = sample(.05)
        s.update(attached=False, load_N=2.2, break_timer_s=.15)
        event = {key: copy.deepcopy(s[key]) for key in ('fruit_position', 'fruit_quaternion',
            'tcp_position', 'tcp_quaternion', 'fixed_force', 'moving_force')}
        event.update(time_s=.025, tip_displacement=[.018, .037, -.012],
                     break_timer_s=20/480, load_N=0.)
        s['detach_events'] = [event]
        self.interval(e, s)
        diagnostics = e.diagnostics()
        self.assertEqual(diagnostics['break_load_N'], 0.)
        self.assertAlmostEqual(diagnostics['break_dwell_s'], 20/480, places=7)
        self.assertTrue(diagnostics['stem_overtravel_break'])
        self.assertFalse(diagnostics['valid_detach'])

    def test_attached_or_fast_body_cannot_be_physical_basket_success(self) -> None:
        e = self.state()
        s = sample(1.)
        s.update(fruit_position=[.4, 0., .6], fruit_com_position=[.4, 0., .6])
        e.accept_sample(s)
        self.assertFalse(e.physical_success)
        s.update(time_s=2., attached=False, fruit_linear_velocity=[.13, 0., 0.])
        e.accept_sample(s)
        self.assertFalse(e.physical_success)

    def test_one_finger_contact_prevents_and_resets_physical_basket_dwell(self) -> None:
        for side in ('fixed', 'moving'):
            for force in (.08, .09):
                with self.subTest(side=side, force_N=force):
                    e = self.state()
                    s = sample()
                    s.update(attached=False, fruit_position=[.4, 0., .6],
                             fruit_com_position=[.4, 0., .6])
                    s[side + '_force'] = [force, 0., 0.]
                    for tick in range(1, 14):
                        s['time_s'] = tick * .05
                        e.accept_sample(s)
                        self.assertFalse(e.physical_success)
                        self.assertEqual(e.physical_place_time, 0.)
                    # 한쪽 힘이 사라진 뒤부터 별도의 연속0.6초가 필요합니다.
                    s[side + '_force'] = [0., 0., 0.]
                    for tick in range(14, 25):
                        s['time_s'] = tick * .05
                        e.accept_sample(s)
                        self.assertFalse(e.physical_success)
                    s['time_s'] = 1.25
                    e.accept_sample(s)
                    self.assertTrue(e.physical_success)
                    s.update(time_s=1.30)
                    s[side + '_force'] = [force, 0., 0.]
                    e.accept_sample(s)
                    self.assertFalse(e.physical_success)
                    self.assertEqual(e.physical_place_time, 0.)

    def test_other_fruit_detach_has_independent_failure(self) -> None:
        e = self.state()
        s = sample(.05)
        s['other_detached'] = True
        self.interval(e, s)
        self.assertEqual(e.assignment_status, 'FAILED')
        self.assertIn('other_detach', e.failure_reason())

    def test_failure_does_not_reset_measured_world_data(self) -> None:
        s = sample(.05)
        s['fruit_position'][2] = .4
        original = copy.deepcopy(s)
        e = self.state()
        self.interval(e, s)
        self.assertEqual(e.assignment_status, 'FAILED')
        self.assertIn('dropped', e.failure_reason())
        for key, value in s.items():
            if isinstance(value, np.ndarray):
                np.testing.assert_array_equal(value, original[key])
        new = self.state(sample())
        self.assertEqual(new.assignment_status, 'RUNNING')
        self.assertFalse(bool(new.has_grasped[0]))

    def test_validation_rejects_nonfinite_time_and_wrong_quaternion(self) -> None:
        e = self.state()
        for key, value in [('time_s', float('nan')), ('q', [0., 0., 0., 0., 0., float('inf')]),
                           ('tcp_quaternion', [2., 0., 0., 0.]), ('attached', 1)]:
            s = sample(.05)
            s[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                e.accept_sample(s)
        e.accept_sample(sample(.1))
        with self.assertRaises(ValueError):
            e.accept_sample(sample(.05))

    def test_joint_limits_must_match_original_normalization(self) -> None:
        p = profile()
        p['joint_limits']['lower'] = list(SOURCE_LOWER)
        p['joint_limits']['lower'][0] += .1
        with self.assertRaisesRegex(ValueError, '정규화'):
            TeacherState(p['runtime'], p['joint_limits'], sample())

    def test_quaternion_rotation_and_inverse(self) -> None:
        q = torch.tensor([[2**-.5, 0., 0., 2**-.5]])
        v = torch.tensor([[1., 0., 0.]])
        torch.testing.assert_close(quat_apply(q, v), torch.tensor([[0., 1., 0.]]), atol=1e-6, rtol=0.)
        torch.testing.assert_close(quat_mul(q, quat_conjugate(q)), torch.tensor([[1., 0., 0., 0.]]))


if __name__ == '__main__':
    unittest.main()
