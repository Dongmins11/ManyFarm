"""과실 USD의 이식성·9g 물성·농장 배치와 독립 좌표 변환을 검사한다."""
import copy
import hashlib
import json
from pathlib import Path
import sys
import unittest

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
for package in ('farm_sim_runtime', 'farm_sim_devices'):
    sys.path.insert(0, str(ROOT / 'sim/ros_ws/src' / package))
from farm_sim_runtime.fruit_asset_setup import configure_farm_fruits, outward_tension_axis_world

try:
    from pxr import PhysxSchema, Usd, UsdGeom, UsdPhysics, UsdShade, UsdUtils
except ImportError:
    Usd = None


def _config() -> dict:
    """실제 실행 프로파일을 사용하여 authoring 계약도 검증한다."""
    path = ROOT / 'sim/ros_ws/src/farm_sim_config/config/robotarm_physics.json'
    return json.loads(path.read_text())['fruit']


def _survey() -> dict:
    """실제 8개 베드/16개 Section의 독립 map/world 등록을 읽는다."""
    path = ROOT / 'sim/ros_ws/src/farm_sim_config/config/scout_survey.json'
    return json.loads(path.read_text())


class TensionAxisTests(unittest.TestCase):
    def test_rotated_translated_map_registration_and_two_sides(self) -> None:
        transform = np.array([[0, -1, 0, 3], [1, 0, 0, 4], [0, 0, 1, 0], [0, 0, 0, 1]])
        survey = dict(evaluation=dict(T_map_world=transform.tolist()), sections=dict(
            A=dict(evaluation_bed_prim='/Bed', physical_bed_center_map_m=[5, 6],
                   survey_geometry=dict(start_xy_m=[3, 1], end_xy_m=[3, 11]))))
        for map_x, expected in [(6, [0, -1, 0]), (4, [0, 1, 0])]:
            world = np.linalg.inv(transform) @ [map_x, 8, 1, 1]
            axis = outward_tension_axis_world(world[:3], '/Bed', survey)
            np.testing.assert_allclose(axis, expected, atol=1e-12)
        world_center = np.linalg.inv(transform) @ [5, 8, 1, 1]
        with self.assertRaises(ValueError):
            outward_tension_axis_world(world_center[:3], '/Bed', survey)


@unittest.skipIf(Usd is None, 'Isaac USD/PhysX schema Python 환경이 필요합니다.')
class FruitAssetTests(unittest.TestCase):
    def test_all_template_dependencies_size_physics_and_hashes(self) -> None:
        directory = ROOT / 'sim/assets/fruit/teacher_9g'
        provenance = json.loads((directory / 'provenance.json').read_text())
        self.assertEqual(len(provenance['copied_files']), 12)
        for row in provenance['copied_files']:
            self.assertEqual(hashlib.sha256((directory / row['path']).read_bytes()).hexdigest(), row['sha256'])
        dependencies = set()
        for color, row in provenance['assets'].items():
            path = directory / row['file']
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), row['sha256'])
            layers, assets, unresolved = UsdUtils.ComputeAllDependencies(str(path))
            self.assertEqual(unresolved, [])
            for dependency in [layer.realPath for layer in layers] + assets:
                self.assertTrue(Path(dependency).resolve().is_relative_to(directory))
            dependencies.update(assets)
            stage = Usd.Stage.Open(str(path))
            root = stage.GetDefaultPrim()
            self.assertAlmostEqual(root.GetAttribute('physics:mass').Get(), .009)
            self.assertTrue(root.GetAttribute('physxRigidBody:enableCCD').Get())
            self.assertFalse(root.GetAttribute('physxRigidBody:disableGravity').Get())
            self.assertEqual(root.GetAttribute('physxRigidBody:linearDamping').Get(), 0)
            self.assertAlmostEqual(root.GetAttribute('physxRigidBody:angularDamping').Get(), .02)
            self.assertEqual(root.GetAttribute('physxRigidBody:maxLinearVelocity').Get(), 3.)
            self.assertEqual(root.GetAttribute('physxRigidBody:maxAngularVelocity').Get(), 20.)
            # source contact_solver_refine=false는 아래 항목에 override를 쓰지 않는다.
            for name in ('solverPositionIterationCount', 'solverVelocityIterationCount',
                         'maxDepenetrationVelocity', 'sleepThreshold',
                         'stabilizationThreshold', 'retainAccelerations'):
                self.assertFalse(root.GetAttribute('physxRigidBody:' + name).HasAuthoredValueOpinion())
            collider = stage.GetPrimAtPath('/Pepper/Collision')
            points = np.asarray(UsdGeom.Mesh(collider).GetPointsAttr().Get())
            size = np.ptp(points, axis=0)
            self.assertAlmostEqual(max(size[:2]), .070, places=6)
            self.assertAlmostEqual(size[2], .075, places=6)
            self.assertEqual(collider.GetAttribute('physics:approximation').Get(), 'convexDecomposition')
            np.testing.assert_allclose(root.GetAttribute('teacher:attachmentLocalM').Get(),
                                       _config()['attachment_local_m_by_color'][color], atol=1e-12)
        self.assertEqual(len(dependencies), 9)

    def test_288_fruits_keep_ids_positions_orientations_and_session_only(self) -> None:
        stage = Usd.Stage.Open(str(ROOT / 'sim/assets/envs/output/farm_with_plants_v5.usd'))
        original_layer = stage.GetRootLayer().ExportToString()
        transforms = UsdGeom.XformCache()
        before = {str(prim.GetPath()): (
            str(prim.GetAttribute('crop:color').Get()),
            np.asarray(transforms.GetLocalToWorldTransform(prim)).T.copy())
            for prim in stage.Traverse() if prim.GetAttribute('crop:color').Get()}
        result = configure_farm_fruits(stage, ROOT, _config(), _survey())
        self.assertEqual(len(result), 288)
        self.assertEqual(set(before), {record['prim_path'] for record in result})
        self.assertEqual(stage.GetRootLayer().ExportToString(), original_layer)
        transforms.Clear()
        for record in result:
            path = record['prim_path']
            prim = stage.GetPrimAtPath(path)
            color, old = before[path]
            actual = np.asarray(transforms.GetLocalToWorldTransform(prim)).T
            normalized_rotation = old[:3, :3] / np.linalg.norm(old[:3, :3], axis=0)
            np.testing.assert_allclose(actual[:3, :3], normalized_rotation, atol=1e-7)
            np.testing.assert_allclose(actual[:3, 3], old[:3, 3], atol=1e-10)
            self.assertEqual(prim.GetAttribute('crop:color').Get(), color)
            self.assertFalse(prim.GetChild('Model').IsActive())
            self.assertTrue(prim.HasAPI(UsdPhysics.RigidBodyAPI))
            self.assertAlmostEqual(prim.GetAttribute('physics:mass').Get(), .009)
            self.assertEqual(prim.GetAttribute('physxRigidBody:maxLinearVelocity').Get(), 3.)
            self.assertEqual(prim.GetAttribute('physxRigidBody:maxAngularVelocity').Get(), 20.)
            collider = prim.GetChild('Collision')
            mat, _ = UsdShade.MaterialBindingAPI(collider).ComputeBoundMaterial('physics')
            self.assertEqual(mat.GetPrim().GetAttribute('physics:staticFriction').Get(), 1)
            self.assertEqual(mat.GetPrim().GetAttribute('physics:dynamicFriction').Get(), 1)
            self.assertAlmostEqual(mat.GetPrim().GetAttribute('physics:restitution').Get(), .02)
            self.assertAlmostEqual(collider.GetAttribute('physxCollision:contactOffset').Get(), .001)
            self.assertEqual(collider.GetAttribute('physxCollision:restOffset').Get(), 0)
            self.assertTrue(2 <= record['break_force_N'] <= 3)
            self.assertAlmostEqual(np.linalg.norm(record['tension_axis_world']), 1)
        second = configure_farm_fruits(stage, ROOT, _config(), _survey())
        self.assertEqual([r['break_force_N'] for r in result], [r['break_force_N'] for r in second])
        self.assertEqual(len(second), 288)
        self.assertEqual(stage.GetRootLayer().ExportToString(), original_layer)

    def test_inconsistent_attachment_fails_before_mutation(self) -> None:
        stage = Usd.Stage.Open(str(ROOT / 'sim/assets/envs/output/farm_with_plants_v5.usd'))
        config = copy.deepcopy(_config())
        config['attachment_local_m_by_color']['red'] = [0, 0, 0]
        before = stage.GetSessionLayer().ExportToString()
        with self.assertRaises(ValueError):
            configure_farm_fruits(stage, ROOT, config, _survey())
        self.assertEqual(before, stage.GetSessionLayer().ExportToString())


if __name__ == '__main__':
    unittest.main()
