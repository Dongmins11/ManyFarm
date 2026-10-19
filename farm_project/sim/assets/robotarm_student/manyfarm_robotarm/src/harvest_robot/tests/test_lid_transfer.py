"""CPU checks: geometry, source isolation and transfer state/failure semantics."""
import json
import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET

import numpy as np
from scipy.spatial.transform import Rotation

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lid_transfer.model import (Settings, SOURCES, TransferMonitor, _geometry,
    inside_box, lid_spec, pepper_local_bounds, random_poses, scene_geometry, world_points)
from lid_transfer.scene import derive_robot


class GeometryTests(unittest.TestCase):
    def setUp(self):
        self.cfg = Settings()
        self.g = scene_geometry(self.cfg)

    def test_centers_aligned_and_original_heights_preserved(self):
        cargo_center = self.g['transport_box_pose'] @ np.array([-.15, 0, 0, 1])
        np.testing.assert_allclose(cargo_center[:2], self.g['harvest_pose'][:2, 3], atol=1e-10)
        self.assertAlmostEqual(self.g['transport_base'][2, 3], 0)
        self.assertAlmostEqual(self.g['vertical_gap_m'], .056)

    def test_deliberate_misalignment(self):
        self.cfg.transport_offset_x, self.cfg.transport_offset_y = .04, -.01
        g = scene_geometry(self.cfg)
        np.testing.assert_allclose(g['transport_base'][:2, 3] - self.g['transport_base'][:2, 3], [.04, -.01])

    def test_many_seeds_fully_inside_and_non_overlapping(self):
        bounds = pepper_local_bounds(self.cfg)
        corners = np.array([[x, y, z] for x in bounds[:, 0] for y in bounds[:, 1] for z in bounds[:, 2]])
        for seed in range(30):
            poses = random_poses(self.cfg, seed, self.g)
            self.assertEqual(len(poses), 8)
            world_bounds = []
            for pose in poses:
                p, q = pose['position'], pose['rotation_wxyz']
                self.assertTrue(inside_box(p, q, corners, self.g['harvest_pose'], self.g['harvest_bounds'], 0))
                pts = world_points(p, q, corners)
                world_bounds.append((pts.min(axis=0), pts.max(axis=0)))
            for i, (lo, hi) in enumerate(world_bounds):
                for other_lo, other_hi in world_bounds[:i]:
                    self.assertTrue(np.any(lo > other_hi) or np.any(other_lo > hi))

    def test_seed_reproducible_and_different(self):
        a = random_poses(self.cfg, 42, self.g)
        self.assertEqual(a, random_poses(self.cfg, 42, self.g))
        self.assertNotEqual(a, random_poses(self.cfg, 43, self.g))

    def test_too_large_payload_is_rejected(self):
        self.cfg.diameter = .12
        with self.assertRaises(ValueError):
            random_poses(self.cfg, 42, self.g)

    def test_stem_or_body_outside_is_rejected_even_when_center_inside(self):
        pose = np.eye(4)
        box = (np.array([-1, -1, -1]), np.array([1, 1, 1]))
        self.assertFalse(inside_box([.95, 0, 0], [1, 0, 0, 0], [[-.1, 0, 0], [.1, 0, 0]], pose, box, 0))
        self.assertFalse(inside_box([0, 0, .95], [1, 0, 0, 0], [[0, 0, 0], [0, 0, .1]], pose, box, 0))

    def test_rotated_containment(self):
        pose = np.eye(4)
        pose[:3, :3] = Rotation.from_euler('z', .8).as_matrix()
        pose[:3, 3] = [2, 3, 4]
        q = Rotation.from_matrix(pose[:3, :3]).as_quat()[[3, 0, 1, 2]]
        self.assertTrue(inside_box(pose[:3, 3], q, [[-.5, 0, 0], [.5, 0, 0]], pose,
            (np.full(3, -1), np.full(3, 1)), 0))

    def test_derived_lid_fk_matches_source_and_preserves_meshes(self):
        for name, source in SOURCES.items():
            original_bytes = source.read_bytes()
            spec = lid_spec(name)
            original = ET.parse(source).getroot()
            with tempfile.TemporaryDirectory() as tmp:
                derived = ET.parse(derive_robot(name, Path(tmp) / 'robot.urdf')).getroot()
            active = [j for j in derived.findall('joint') if j.get('type') != 'fixed']
            self.assertEqual({j.get('name') for j in active}, {spec['motor'], *spec['slides']})
            self.assertIsNone(derived.find(f"joint[@name='{spec['motor']}']/mimic"))
            for slide in spec['slides']:
                self.assertEqual(derived.find(f"joint[@name='{slide}']/mimic").get('joint'), spec['motor'])
            for fraction in [0, .5, 1]:
                q = {spec['motor']: spec['open_angle'] * fraction,
                     **{j: spec['travel'] * fraction for j in spec['slides']}}
                a, b = _geometry.fk(original, q), _geometry.fk(derived, q)
                for joint in active:
                    link = joint.find('child').get('link')
                    np.testing.assert_allclose(a[link], b[link], atol=1e-9)
            for old, new in zip(original.iter('mesh'), derived.iter('mesh')):
                self.assertEqual(old.get('scale'), new.get('scale'))
                self.assertEqual(_geometry.mesh_path(old.get('filename'), source).resolve(), Path(new.get('filename')))
            self.assertEqual(original_bytes, source.read_bytes())


class StateTests(unittest.TestCase):
    def setUp(self):
        self.cfg = Settings()
        self.ctl = TransferMonitor(self.cfg)
        self.ok = dict(loaded=8, received=0, escaped=False, finite=True, harvest_open=False, transport_open=False)

    def step(self, dt=.1, **updates):
        self.ctl.advance(dt, **(self.ok | updates))

    def test_loading_requires_all_eight_and_dwell(self):
        self.step(2.9)
        self.assertEqual(self.ctl.phase, 'LOADING')
        self.step(.2, loaded=7)
        self.step(.3)
        self.assertEqual(self.ctl.phase, 'LOADING')
        self.step(.4)
        self.assertEqual(self.ctl.phase, 'OPEN_TRANSPORT')

    def test_loading_failure(self):
        self.step(16, loaded=7)
        self.assertEqual(self.ctl.reason, 'HARVEST_LOADING_FAILED')

    def test_harvest_stays_closed_until_measured_transport_open(self):
        self.ctl.transition('OPEN_TRANSPORT')
        self.step(7)
        self.assertEqual(self.ctl.phase, 'OPEN_TRANSPORT')
        self.assertEqual(self.ctl.harvest_angle, 0)
        self.step(.3, transport_open=True)
        self.assertEqual(self.ctl.phase, 'OPEN_HARVEST')

    def test_motor_stall_is_failure(self):
        self.ctl.transition('OPEN_TRANSPORT')
        self.step(13)
        self.assertEqual(self.ctl.reason, 'TRANSPORT_LID_OPEN_FAILED')

    def test_harvest_stall_is_failure(self):
        self.ctl.transition('OPEN_HARVEST')
        self.step(13, transport_open=True)
        self.assertEqual(self.ctl.reason, 'HARVEST_LID_OPEN_FAILED')

    def test_all_eight_must_settle_continuously(self):
        self.ctl.transition('TRANSFER_SETTLE')
        flags = dict(transport_open=True, harvest_open=True)
        self.step(.5, received=8, **flags)
        self.step(.1, received=7, **flags)
        self.step(.5, received=8, **flags)
        self.assertFalse(self.ctl.finished)
        self.step(.11, received=8, **flags)
        self.assertEqual(self.ctl.phase, 'SUCCESS')

    def test_transfer_timeout_never_counts_seven_as_success(self):
        self.ctl.transition('TRANSFER_SETTLE')
        self.step(16, received=7, transport_open=True, harvest_open=True)
        self.assertEqual(self.ctl.reason, 'TRANSFER_INCOMPLETE')

    def test_open_lid_loss(self):
        self.ctl.transition('OPEN_HARVEST')
        self.step()
        self.assertEqual(self.ctl.reason, 'TRANSPORT_LID_LOST_OPEN')
        self.ctl = TransferMonitor(self.cfg)
        self.ctl.transition('TRANSFER_SETTLE')
        self.step(1, received=8, harvest_open=True)
        self.assertEqual(self.ctl.reason, 'LID_LOST_OPEN')

    def test_escape_and_nonfinite_have_priority_over_success(self):
        for flags, reason in [(dict(escaped=True), 'PEPPER_ESCAPED'),
                              (dict(finite=False), 'NONFINITE_PHYSICS')]:
            self.ctl = TransferMonitor(self.cfg)
            self.ctl.transition('TRANSFER_SETTLE')
            self.step(1, received=8, transport_open=True, harvest_open=True, **flags)
            self.assertEqual(self.ctl.reason, reason)

    def test_invalid_settings(self):
        for key, value in [('mass', 0), ('physics_dt', float('nan')), ('motor_speed', .6), ('count', 7)]:
            cfg = Settings(**{key: value})
            with self.assertRaises(ValueError):
                cfg.validate()


class TelemetryTests(unittest.TestCase):
    def test_measured_partial_lid_and_nonfinite_states_are_reportable(self):
        import torch
        from types import SimpleNamespace
        path = Path(__file__).resolve().parents[1] / 'test_lid_transfer.py'
        spec = importlib.util.spec_from_file_location('transfer_runner_cpu', path)
        runner = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(runner)
        cfg = Settings()
        robots = {}
        for name in ('harvest', 'transport'):
            s = lid_spec(name)
            q = torch.tensor([[s['open_angle'], s['travel'], s['travel']]])
            robots[name] = SimpleNamespace(joint_names=[s['motor'], *s['slides']],
                data=SimpleNamespace(joint_pos=q, joint_vel=torch.zeros_like(q), applied_torque=torch.zeros_like(q)))
        geometry = scene_geometry(cfg)
        state = runner.read_state(cfg, geometry, [], [], robots)
        self.assertTrue(state['lids']['transport']['open'])
        robots['transport'].data.joint_pos[0, 2] = .12
        state = runner.read_state(cfg, geometry, [], [], robots)
        self.assertFalse(state['lids']['transport']['open'])
        robots['harvest'].data.joint_pos[0, 0] = float('nan')
        state = runner.read_state(cfg, geometry, [], [], robots)
        self.assertFalse(state['finite'])
        self.assertFalse(state['lids']['harvest']['open'])
        json.dumps(state, allow_nan=False)
        fruit = SimpleNamespace(data=SimpleNamespace(root_state_w=torch.full((1, 13), float('nan'))))
        state = runner.read_state(cfg, geometry, [fruit], [np.zeros((1, 3))], robots)
        self.assertFalse(state['finite'])
        self.assertEqual(state['received'], 0)
        json.dumps(state, allow_nan=False)


if __name__ == '__main__':
    unittest.main()
