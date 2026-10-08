"""Isaac 없이 활성 과실 집합·전역 mapping·비가역 분리와 pose 보존을 검사한다.

SDK의 실제 kinematic 전환/접촉은 별도 GPU 검증이 필요하다. 이 fixture는
RigidPrim I/O 경계만 대체하고 활성 집합/줄기 상태 계산은 실제 코드를 실행한다.
"""
from pathlib import Path
from types import ModuleType, SimpleNamespace
import sys
import unittest
from unittest.mock import patch

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'sim/ros_ws/src/farm_sim_devices'))
from farm_sim_devices.fruit_attachment import FruitAttachments

try:
    from pxr import Gf, PhysxSchema, Usd, UsdGeom, UsdPhysics
except ImportError:
    Usd = None


class FakeWorld:
    """세 개 과실의 물리 상태와 SDK 호출을 보관하는 I/O fixture다."""

    def __init__(self) -> None:
        self.paths = ['/Fruit_0', '/Fruit_1', '/Fruit_2']
        self.positions = np.array([[0., 0., 1.], [1., 0., 1.], [2., 0., 1.]])
        self.orientations = np.tile([1., 0., 0., 0.], (3, 1))
        self.velocities = np.zeros((3, 6))
        self.kinematic = np.zeros(3, dtype=bool)
        self.views, self.registered, self.force_calls, self.transitions = [], [], [], []
        self.physics_sim_view = object()
        self.scene = SimpleNamespace(add=self.add)

    def add(self, view: object) -> object:
        self.registered.append(view)
        return view


class FakeRigidPrim:
    """부분 view 순서를 뒤집어 전역/지역 인덱스 혼동을 검출한다."""

    world: FakeWorld

    def __init__(self, prim_paths_expr: list[str], **kwargs: object) -> None:
        paths = list(prim_paths_expr)
        self.prim_paths = paths if len(paths) == 3 else list(reversed(paths))
        self.indices = np.asarray([self.world.paths.index(p) for p in self.prim_paths])
        self.pose_reads = self.velocity_reads = 0
        self.initialized_with = None
        self.world.views.append(self)

    def initialize(self, physics_sim_view: object = None) -> None:
        self.initialized_with = physics_sim_view

    def is_physics_handle_valid(self) -> bool:
        return True

    def get_world_poses(self) -> tuple[np.ndarray, np.ndarray]:
        self.pose_reads += 1
        return self.world.positions[self.indices].copy(), self.world.orientations[self.indices].copy()

    def get_velocities(self) -> np.ndarray:
        self.velocity_reads += 1
        return self.world.velocities[self.indices].copy()

    def get_masses(self) -> np.ndarray:
        return np.full(len(self.indices), .009)

    def get_coms(self) -> tuple[np.ndarray, np.ndarray]:
        return np.zeros((len(self.indices), 3)), np.tile([1., 0., 0., 0.], (len(self.indices), 1))

    def get_inv_inertias(self) -> np.ndarray:
        return np.tile(np.eye(3) * 200000., (len(self.indices), 1, 1))

    def apply_forces_and_torques_at_pos(self, **kwargs: object) -> None:
        indices = np.asarray(kwargs['indices'], dtype=int)
        self.world.force_calls.append(dict(global_indices=self.indices[indices].copy(), **kwargs))


class FixtureAttachments(FruitAttachments):
    """USD 전환 I/O만 대체한다. position/velocity를 변경하지 않는다."""

    def _set_kinematic(self, indices: np.ndarray, enabled: bool) -> None:
        self.world.kinematic[indices] = enabled
        if len(indices):
            self.world.transitions.append((indices.copy(), enabled, self._cached_positions[indices].copy()))


class FruitActivationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.world = FakeWorld()
        FakeRigidPrim.world = self.world
        module = ModuleType('isaacsim.core.prims')
        module.RigidPrim = FakeRigidPrim
        self.modules = patch.dict(sys.modules, {'isaacsim.core.prims': module})
        self.modules.start()
        self.addCleanup(self.modules.stop)
        self.records = [dict(prim_path=path, attachment_local_m=[0., 0., .035],
                             tension_axis_world=[-1., 0., 0.], break_force_N=2.5)
                        for path in self.world.paths]

    def make(self, selective: bool = True) -> FixtureAttachments:
        result = FixtureAttachments(self.world, self.records, {}, selective=selective)
        result.initialize()
        return result

    def test_default_all_active_preserves_full_shape_and_view(self) -> None:
        attachment = self.make(False)
        attachment.set_active([])
        attachment.update(1/480)
        self.assertEqual(len(self.world.views), 1)
        np.testing.assert_array_equal(attachment.active, [True, True, True])
        self.assertEqual(attachment.last_step.force.shape, (3, 3))
        np.testing.assert_array_equal(self.world.force_calls[-1]['global_indices'], [0, 1, 2])

    def test_initial_freeze_uses_post_reset_pose_but_original_anchor(self) -> None:
        attachment = FixtureAttachments(self.world, self.records, {}, selective=True)
        anchors, rest = attachment.anchors.copy(), attachment.rest_orientation.copy()
        self.world.positions[:, 2] -= .00005
        actual = self.world.positions.copy()
        attachment.initialize()
        np.testing.assert_array_equal(self.world.positions, actual)
        np.testing.assert_array_equal(attachment.current_positions(), actual)
        np.testing.assert_array_equal(attachment.anchors, anchors)
        np.testing.assert_array_equal(attachment.rest_orientation, rest)
        self.assertEqual(attachment.summary()['frozen_count'], 3)
        attachment.update(1/60)
        self.assertEqual(self.world.force_calls, [])

    def test_subset_view_mapping_and_no_global_reads_per_tick(self) -> None:
        attachment = self.make()
        full_reads = attachment.view.pose_reads, attachment.view.velocity_reads
        attachment.set_active([0, 2])
        np.testing.assert_array_equal(attachment._active_indices, [2, 0])
        self.world.positions[2, 0] -= .005
        attachment.update(1/480)
        np.testing.assert_array_equal(self.world.force_calls[-1]['global_indices'], [2, 0])
        self.assertEqual((attachment.view.pose_reads, attachment.view.velocity_reads), full_reads)
        self.assertEqual(attachment.last_step.force.shape, (3, 3))
        np.testing.assert_array_equal(attachment.last_step.force[1], [0., 0., 0.])
        self.assertEqual(len(self.world.registered), 1)
        revision = attachment._view_revision
        attachment.set_active([2, 0])
        self.assertEqual(attachment._view_revision, revision)

    def test_deactivation_defers_motion_or_dwell_then_preserves_pose(self) -> None:
        attachment = self.make()
        attachment.set_active([1])
        anchors, rest = attachment.anchors.copy(), attachment.rest_orientation.copy()
        self.world.velocities[1, 0] = .02
        attachment.set_active([])
        self.assertTrue(attachment.active[1])
        self.world.velocities[1] = 0
        self.world.velocities[1, 4] = .11
        attachment.set_active([])
        self.assertTrue(attachment.active[1])
        self.world.velocities[1] = 0
        attachment.timer[1] = .01
        attachment.set_active([])
        self.assertTrue(attachment.active[1])
        attachment.timer[1] = 0
        self.world.positions[1, 2] -= .003
        pose = self.world.positions.copy()
        attachment.set_active([])
        self.assertFalse(attachment.active[1])
        np.testing.assert_array_equal(self.world.transitions[-1][2], pose[[1]])
        attachment.set_active([1])
        np.testing.assert_array_equal(self.world.positions, pose)
        np.testing.assert_array_equal(attachment.anchors, anchors)
        np.testing.assert_array_equal(attachment.rest_orientation, rest)

    def test_physical_detach_stays_dynamic_after_request_is_removed(self) -> None:
        attachment = self.make()
        attachment.set_active([2])
        self.world.positions[2, 0] -= .026
        events = []
        for i in range(20):
            events += attachment.update(1/480, i/480)
        self.assertEqual([e['prim_path'] for e in events], ['/Fruit_2'])
        self.assertFalse(attachment.attached[2])
        attachment.set_active([])
        self.assertTrue(attachment.active[2])
        self.assertFalse(self.world.kinematic[2])
        calls = len(self.world.force_calls)
        attachment.update(1/60)
        self.assertEqual(len(self.world.force_calls), calls)
        self.assertFalse(attachment.last_step.attached[2])
        self.assertEqual(attachment.summary()['detached_count'], 1)

    def test_current_state_merges_active_view_with_frozen_cache(self) -> None:
        attachment = self.make()
        attachment.set_active([0, 2])
        self.world.positions[0, 2] = .9
        self.world.velocities[2, 0] = .3
        np.testing.assert_array_equal(attachment.current_positions(), self.world.positions)
        np.testing.assert_array_equal(attachment.current_velocities(), self.world.velocities)
        self.assertEqual(attachment.summary()['active_count'], 2)
        self.assertEqual(attachment.summary()['frozen_count'], 1)

    def test_invalid_indices_fail_before_physics_changes(self) -> None:
        attachment = self.make()
        for indices in ([-1], [3], [1.5], [[1]], [True]):
            with self.subTest(indices=indices):
                count = len(self.world.transitions)
                with self.assertRaises(ValueError):
                    attachment.set_active(indices)
                self.assertEqual(len(self.world.transitions), count)
        with self.assertRaises(ValueError):
            attachment.update(0.)


@unittest.skipIf(Usd is None, 'standalone USD/PhysX schema 환경 필요')
class FruitActivationUsdTests(unittest.TestCase):
    def test_ccd_transition_flush_order_and_original_pose_are_preserved(self) -> None:
        stage = Usd.Stage.CreateInMemory()
        parent = UsdGeom.Xform.Define(stage, '/Parent')
        parent.AddTranslateOp().Set(Gf.Vec3d(3., 2., 1.))
        paths = ['/Parent/Fruit_0', '/Parent/Fruit_1']
        for i, path in enumerate(paths):
            prim = UsdGeom.Xform.Define(stage, path).GetPrim()
            UsdPhysics.RigidBodyAPI.Apply(prim).CreateKinematicEnabledAttr(False)
            PhysxSchema.PhysxRigidBodyAPI.Apply(prim).CreateEnableCCDAttr(i == 0)
        source = stage.GetRootLayer().ExportToString()
        attachment = FruitAttachments.__new__(FruitAttachments)
        attachment.world = SimpleNamespace(stage=stage)
        attachment.paths = paths
        attachment._original_ccd = {}
        attachment._cached_positions = np.array([[6., 4., 3.], [7., 4., 3.]])
        attachment._cached_orientations = np.tile([1., 0., 0., 0.], (2, 1))
        snapshots = []

        def flush() -> None:
            snapshots.append([
                (bool(UsdPhysics.RigidBodyAPI(stage.GetPrimAtPath(path)).GetKinematicEnabledAttr().Get()),
                 bool(PhysxSchema.PhysxRigidBodyAPI(stage.GetPrimAtPath(path)).GetEnableCCDAttr().Get()))
                for path in paths])

        with patch.object(attachment, '_flush_physics_changes', side_effect=flush):
            for _ in range(2):
                attachment._set_kinematic(np.arange(2), True)
                attachment._set_kinematic(np.arange(2), False)
        expected = [[(False, False), (False, False)], [(True, False), (True, False)],
                    [(False, False), (False, False)], [(False, True), (False, False)]]
        self.assertEqual(snapshots, expected * 2)
        self.assertEqual(attachment._original_ccd, {0: True, 1: False})
        cache = UsdGeom.XformCache()
        for index, path in enumerate(paths):
            actual = cache.GetLocalToWorldTransform(stage.GetPrimAtPath(path)).ExtractTranslation()
            np.testing.assert_allclose(actual, attachment._cached_positions[index], atol=1e-12)
        self.assertEqual(stage.GetRootLayer().ExportToString(), source)


if __name__ == '__main__':
    unittest.main()
