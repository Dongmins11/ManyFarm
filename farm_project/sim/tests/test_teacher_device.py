"""Isaac I/O 경계 fixture로 좌표·접촉 단위·실제 관절 목표와 분리 시점을 검사한다.

실제 PhysX 접촉 handle 검증은 check_teacher_device.py GPU probe가 담당한다.
"""
import json
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'sim/ros_ws/src/farm_sim_devices'))
from farm_sim_devices.teacher_device import TeacherDevice, continuous_near_mask, _quaternion
from farm_sim_devices.stem_physics import quaternion_matrix


def fixture() -> TeacherDevice:
    """순서를 뒤집은 finger view와 회전한 dock의 알려진 물리 측정값이다."""
    d = TeacherDevice.__new__(TeacherDevice)
    profile = json.loads((ROOT/'sim/ros_ws/src/farm_sim_config/config/teacher_policy.json').read_text())
    d.config = dict(profile['device'], **{k: profile['runtime'][k] for k in
        ('box_min', 'box_max', 'box_contact_tolerance', 'box_bottom_contact_tolerance', 'sequence')})
    d._ready = True
    d.paths = ['/red', '/yellow', '/green']
    d._path_indices = {p: i for i, p in enumerate(d.paths)}
    d._selected, d._completed, d._events, d._previous = '/red', set(), [], None
    d._joint_indices = np.array([7, 3, 8, 5, 6, 1])
    d.home = np.zeros(6)
    d.lower, d.upper = -np.ones(6), np.ones(6)
    d._last_physics_dt = 1/480
    d._mount_path, d._fixed_path = '/mount', '/fixed'
    d._pose_indices, d._finger_indices = {'/mount': 0, '/fixed': 1}, [1, 0]
    d._tcp_offset = np.array([.1, 0, 0])
    d._policy_arm = np.asarray(d.config['policy_arm_position_m'])
    d._policy_world = np.eye(4)
    d._policy_world[:3, :3] = [[0, -1, 0], [1, 0, 0], [0, 0, 1]]
    d._policy_world[:3, 3] = [10, 20, 30]
    d._dock_world_arm = np.eye(4)
    d.world = SimpleNamespace(current_time=1.)
    d._poses = np.array([[0., 0., 0.], [1., 2., 3.]])
    d._orientations = np.tile([1., 0., 0., 0.], (2, 1))
    d._pose_view = SimpleNamespace(get_world_poses=lambda: (d._poses, d._orientations))
    d._q, d._qd, d._commands, d._calls = np.arange(6)/10, np.arange(6)/20, [], []
    d.articulation = SimpleNamespace(
        get_joint_positions=lambda **kw: d._q.copy(),
        get_joint_velocities=lambda **kw: d._qd.copy(),
        apply_action=d._commands.append)
    a = SimpleNamespace(paths=d.paths, records=[dict(color=c) for c in ('red', 'yellow', 'green')],
        positions=np.array([[.32, 0., .27]]*3), _cached_orientations=np.tile([1., 0., 0., 0.], (3, 1)),
        velocity=np.array([[1., 2., 3., 4., 5., 6.]]*3), local_com=np.array([[.01, 0, 0]]*3),
        anchors=np.array([[.32, 0, .32]]*3), tips=np.array([[0., 0., .05]]*3),
        attached=np.ones(3, dtype=bool), active=np.ones(3, dtype=bool), timer=np.zeros(3),
        thresholds=np.array([2., 2.5, 3.]), last_step=SimpleNamespace(tension=np.array([.7, .8, .9])))
    a.current_positions = lambda: a.positions.copy()
    a.current_velocities = lambda: a.velocity.copy()
    d.attachments = a
    d._vertices = {p: np.array([[0., 0., -.0375], [.035, 0, .0375]]) for p in d.paths}
    d._impulses = np.zeros((2, 3, 3))
    d._impulses[1, 0] = [1/480, 0, 0]
    d._impulses[0, 0] = [0, 2/480, 0]

    def pair(dt: float) -> np.ndarray:
        d._calls.append(('pair', dt))
        return d._impulses/dt

    def fingers(dt: float) -> np.ndarray:
        d._calls.append(('fingers', dt))
        return np.array([[0, 3/480, 0], [4/480, 0, 0]])/dt

    def arm(dt: float) -> np.ndarray:
        d._calls.append(('arm', dt))
        return np.array([[0, 0, 5/480]])/dt

    d._finger_view = SimpleNamespace(get_contact_force_matrix=pair, get_net_contact_forces=fingers)
    d._arm_view = SimpleNamespace(get_net_contact_forces=arm)
    return d


class TeacherDeviceTest(unittest.TestCase):
    def test_quaternion_keeps_rotation_for_half_turns_and_general_pose(self) -> None:
        for q in ([1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1], [1, 2, 3, 4]):
            q = np.asarray(q, dtype=float)/np.linalg.norm(q)
            np.testing.assert_allclose(quaternion_matrix(_quaternion(quaternion_matrix(q))), quaternion_matrix(q), atol=1e-14)

    def test_candidates_use_real_pose_and_color_and_completed_ledger(self) -> None:
        d = fixture()
        self.assertEqual(d.candidate_ids(), ['/red', '/yellow'])
        self.assertEqual(d.candidate_ids(['/red']), ['/yellow'])
        d.attachments.positions[0] = [1., 0, .27]
        self.assertEqual(d.candidate_ids(), ['/yellow'])
        d.attachments.attached[1] = False
        self.assertEqual(d.candidate_ids(), [])

    def test_continuous_range_is_not_discrete_candidate_match(self) -> None:
        d = fixture()
        values = continuous_near_mask(np.array([[.30123, .0123, .274], [.5, 0, .274], [.265, 0, .274]]), d.config)
        np.testing.assert_array_equal(values, [False, False, False])
        self.assertTrue(continuous_near_mask(np.array([[.32123, .0123, .274]]), d.config)[0])

    def test_contact_impulses_use_physics_dt_and_correct_finger_direction(self) -> None:
        d = fixture()
        sample = d._read_sample(1., 1/480)
        np.testing.assert_allclose(sample['fixed_force'], [0, 1, 0])
        np.testing.assert_allclose(sample['moving_force'], [-2, 0, 0])
        np.testing.assert_allclose(sample['fixed_net_force'], [0, 4, 0])
        np.testing.assert_allclose(sample['moving_net_force'], [-3, 0, 0])
        np.testing.assert_allclose(sample['arm_forces'], [[0, 0, 5]])
        np.testing.assert_allclose(sample['fruit_position'], [10, 20.32, 30.27])
        np.testing.assert_allclose(sample['fruit_com_position'], [10, 20.33, 30.27])
        np.testing.assert_allclose(sample['fruit_linear_velocity'], [-2, 1, 3])
        np.testing.assert_allclose(sample['tcp_position'], [8, 21.1, 33])
        self.assertTrue(all(dt == 1/480 for _, dt in d._calls))
        np.testing.assert_allclose(sample['attachment_local'], [0, 0, .05])

    def test_detach_evidence_uses_preintegration_pose_and_is_consumed_once(self) -> None:
        d = fixture()
        d._previous = d._read_sample(1., 1/480)
        original = d._previous['fruit_position'].copy()
        d.attachments.attached[0] = False
        d.attachments.positions[0, 0] += .2
        d.observe_physics_tick(1/480, 1+1/480)
        sample = d.sample('/red')
        self.assertFalse(sample['attached'])
        self.assertEqual(len(sample['detach_events']), 1)
        event = sample['detach_events'][0]
        np.testing.assert_allclose(event['fruit_position'], original)
        np.testing.assert_allclose(event['tip_displacement'], [0, 0, 0], atol=1e-14)
        self.assertEqual(event['time_s'], 1.)
        self.assertGreater(np.linalg.norm(sample['fruit_position']-event['fruit_position']), .19)
        self.assertEqual(d.sample()['detach_events'], [])
        d.observe_physics_tick(1/480, 1+2/480)
        self.assertEqual(d.sample()['detach_events'], [])

    def test_other_detach_excludes_only_selected_and_completed(self) -> None:
        d = fixture()
        d.attachments.attached[:2] = False
        self.assertTrue(d._read_sample(1., 1/480)['other_detached'])
        d._completed = {'/yellow'}
        self.assertFalse(d._read_sample(1., 1/480)['other_detached'])
        d.attachments.attached[2] = False
        self.assertTrue(d._read_sample(1., 1/480)['other_detached'])

    def test_commands_only_existing_six_dofs_and_reject_unsafe_values(self) -> None:
        d = fixture()
        with patch.dict(sys.modules, {'isaacsim.core.utils.types': SimpleNamespace(ArticulationAction=SimpleNamespace)}):
            d.command([.1]*6)
            np.testing.assert_array_equal(d._commands[0].joint_indices, d._joint_indices)
            np.testing.assert_allclose(d._commands[0].joint_positions, [.1]*6)
            for target in ([2.]*6, [float('nan')]*6, [.1]*5):
                with self.assertRaises(ValueError):
                    d.command(target)
        self.assertEqual(len(d._commands), 1)
        d.clear_target()
        np.testing.assert_allclose(d.joint_velocities(), d._qd)

    def test_inactive_target_cannot_silently_start(self) -> None:
        d = fixture()
        d.attachments.active[0] = False
        with self.assertRaises(RuntimeError):
            d.select_target('/red')

    def test_deposit_guard_follows_current_robot_and_entire_collider(self) -> None:
        d = fixture()
        center = (np.asarray(d.config['box_min'])+d.config['box_max'])/2
        world = center-d._policy_arm
        d.attachments.positions[:] = world
        d.attachments.velocity[:] = 100.  # 이전 적재는 재정착 속도를 요구하지 않는다.
        self.assertEqual(d.escaped_deposits(['/red', '/yellow']), [])
        # 로봇과 이미 적재된 과실이 함께 주행했다면 고정 dock frame과 관계없이 남아 있다.
        shift = np.array([3., -2., 0.])
        d._poses[0] += shift
        d.attachments.positions += shift
        self.assertEqual(d.escaped_deposits(['/red']), [])
        # 박스 yaw도 현재 장착점 기준이다. 과실과 박스를 함께 90도 회전한다.
        rotation = np.array([[0., -1., 0.], [1., 0., 0.], [0., 0., 1.]])
        d._orientations[0] = [2**-.5, 0, 0, 2**-.5]
        d.attachments._cached_orientations[:] = d._orientations[0]
        d.attachments.positions[:] = rotation @ world+shift
        self.assertEqual(d.escaped_deposits(['/red']), [])
        d.attachments.positions[0, 1] += .3
        self.assertEqual(d.escaped_deposits(['/red', '/yellow']), ['/red'])
        self.assertEqual(d.escaped_deposits(['/yellow']), [])

    def test_deposit_guard_preserves_source_bottom_and_upper_tolerances(self) -> None:
        d = fixture()
        lo, hi = np.asarray(d.config['box_min']), np.asarray(d.config['box_max'])
        center = (lo+hi)/2
        root = center-d._policy_arm
        root[2] = lo[2]-.009+.0375-d._policy_arm[2]
        d.attachments.positions[0] = root
        self.assertEqual(d.escaped_deposits(['/red']), [])
        d.attachments.positions[0, 2] -= .002
        self.assertEqual(d.escaped_deposits(['/red']), ['/red'])
        d.attachments.positions[0] = center-d._policy_arm
        d.attachments.positions[0, 0] = hi[0]+.002-.035-d._policy_arm[0]
        self.assertEqual(d.escaped_deposits(['/red']), [])
        d.attachments.positions[0, 0] += .002
        self.assertEqual(d.escaped_deposits(['/red']), ['/red'])


if __name__ == '__main__':
    unittest.main()
