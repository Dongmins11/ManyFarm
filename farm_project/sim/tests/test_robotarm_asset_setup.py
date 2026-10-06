"""USD 정적 검사: 주행 보존, degree 단위, 그리퍼 재질 및 실제 바닥 기하.

PhysX 실행 결과를 대신하지 않는다. Isaac 환경의 USD/PhysX schema 경로가
설정된 Python으로 실행한다.
"""
import copy
import math
from pathlib import Path
import sys
import unittest

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'sim/ros_ws/src/farm_sim_runtime'))
from farm_sim_runtime.robotarm_asset_setup import configure_harvest_arm

try:
    from pxr import PhysxSchema, Usd, UsdGeom, UsdPhysics, UsdShade
except ImportError:
    Usd = None


def _config() -> dict:
    """전달 SI 값과 초기 자세를 사용한 회귀용 입력이다."""
    return dict(
        arm=dict(joint_names=['arm_2_shoulder_pan', 'arm_2_shoulder_lift',
                             'arm_2_elbow_flex', 'arm_2_wrist_flex', 'arm_2_wrist_roll'],
                 stiffness_nm_per_rad=25, damping_nm_s_per_rad=1.5,
                 effort_limit_nm=2, velocity_limit_rad_s=1.2,
                 home_positions_rad=[0, -1.39, .77, .62, .04879632679489654]),
        gripper=dict(joint_name='arm_2_gripper', stiffness_nm_per_rad=8,
                     damping_nm_s_per_rad=.3, effort_limit_nm=.5,
                     velocity_limit_rad_s=1.5, home_position_rad=1.1),
        contact=dict(static_friction=1, dynamic_friction=1, restitution=.02,
                     contact_offset_m=.001, rest_offset_m=0),
        box_floor=dict(enabled=True,
                       asset_path=str(ROOT / 'sim/assets/robots/harvest_physics/box_floor_v3.usd'),
                       body_names=['box_bottom_left', 'box_bottom_right'],
                       source_prims=['/HarvestBoxFloor/Plus', '/HarvestBoxFloor/Minus']))


@unittest.skipIf(Usd is None, 'Isaac USD/PhysX schema Python 환경이 필요합니다.')
class RobotarmAssetTests(unittest.TestCase):
    def setUp(self) -> None:
        self.stage = Usd.Stage.CreateInMemory()
        UsdGeom.SetStageMetersPerUnit(self.stage, 1)
        UsdGeom.SetStageUpAxis(self.stage, 'Z')
        prim = UsdGeom.Xform.Define(self.stage, '/Robot').GetPrim()
        prim.GetReferences().AddReference(str(ROOT / 'sim/assets/robots/harvest_count_test/harvest_robot.usd'))

    def _protected_state(self) -> dict:
        """주행·왼팔 및 모든 body/articulation의 기존 solver·sleep 물성을 읽는다."""
        values = {}
        for prim in Usd.PrimRange(self.stage.GetPrimAtPath('/Robot'), Usd.TraverseInstanceProxies()):
            name, path = prim.GetName(), str(prim.GetPath())
            if prim.HasAPI(UsdPhysics.RigidBodyAPI) or prim.HasAPI(UsdPhysics.ArticulationRootAPI):
                values[(path, 'body_properties')] = [(a.GetName(), str(a.Get()), a.HasAuthoredValueOpinion())
                    for a in prim.GetAttributes() if a.GetName().startswith(
                        ('physxRigidBody:', 'physxArticulation:')) or a.GetName() in
                    ('physics:mass', 'physics:centerOfMass', 'physics:diagonalInertia', 'physics:principalAxes')]
            if name in ('left_wheel_joint', 'right_wheel_joint') or (
                    name.startswith('arm_1_') and prim.IsA(UsdPhysics.Joint)):
                values[path] = [(a.GetName(), str(a.Get())) for a in prim.GetAttributes()]
            if 'caster' in path and prim.HasAPI(UsdPhysics.CollisionAPI):
                mat, _ = UsdShade.MaterialBindingAPI(prim).ComputeBoundMaterial('physics')
                values[path] = (str(mat.GetPath()), mat.GetPrim().GetAttribute('physics:staticFriction').Get(),
                                mat.GetPrim().GetAttribute('physics:dynamicFriction').Get())
        return values

    def test_session_only_drive_units_and_preserved_navigation(self) -> None:
        before = self.stage.GetRootLayer().ExportToString()
        protected = self._protected_state()
        result = configure_harvest_arm(self.stage, '/Robot', _config())
        self.assertEqual(self.stage.GetRootLayer().ExportToString(), before)
        self.assertEqual(self._protected_state(), protected)
        self.assertTrue(self.stage.GetPrimAtPath('/Robot/base_footprint').HasAPI(UsdPhysics.ArticulationRootAPI))
        self.assertEqual(len(result['joint_paths']), 6)
        for i, path in enumerate(result['joint_paths']):
            prim = self.stage.GetPrimAtPath(path)
            # 1 rad 오차/속도를 deg 단위에 넣어도 전달 torque gain이 나온다.
            stiffness = prim.GetAttribute('drive:angular:physics:stiffness').Get()
            damping = prim.GetAttribute('drive:angular:physics:damping').Get()
            self.assertAlmostEqual(stiffness * math.degrees(1), 25 if i < 5 else 8, places=5)
            self.assertAlmostEqual(damping * math.degrees(1), 1.5 if i < 5 else .3, places=6)
            self.assertEqual(prim.GetAttribute('drive:angular:physics:type').Get(), 'force')
            self.assertAlmostEqual(prim.GetAttribute('drive:angular:physics:maxForce').Get(), 2 if i < 5 else .5)
            velocity = prim.GetAttribute('physxJoint:maxJointVelocity').Get()
            self.assertAlmostEqual(math.radians(velocity), 1.2 if i < 5 else 1.5, places=6)
            target = prim.GetAttribute('drive:angular:physics:targetPosition').Get()
            self.assertAlmostEqual(math.radians(target), result['home_positions_rad'][i], places=6)

    def test_grip_material_floor_geometry_and_idempotence(self) -> None:
        result = configure_harvest_arm(self.stage, '/Robot', _config())
        self.assertEqual(len(result['floor_colliders']), 4)
        self.assertGreater(len(result['grip_colliders']), 0)
        for path in result['grip_colliders']:
            prim = self.stage.GetPrimAtPath(path)
            mat, _ = UsdShade.MaterialBindingAPI(prim).ComputeBoundMaterial('physics')
            self.assertEqual(str(mat.GetPath()), result['grip_material'])
            self.assertEqual(mat.GetPrim().GetAttribute('physics:staticFriction').Get(), 1)
            self.assertEqual(mat.GetPrim().GetAttribute('physics:dynamicFriction').Get(), 1)
            self.assertAlmostEqual(mat.GetPrim().GetAttribute('physics:restitution').Get(), .02)
            self.assertAlmostEqual(prim.GetAttribute('physxCollision:contactOffset').Get(), .001)
            self.assertEqual(prim.GetAttribute('physxCollision:restOffset').Get(), 0)
        transforms = UsdGeom.XformCache()
        points = []
        for path in result['floor_colliders']:
            prim = self.stage.GetPrimAtPath(path)
            self.assertFalse(prim.HasAPI(UsdPhysics.RigidBodyAPI))
            xyz = np.asarray(UsdGeom.Mesh(prim).GetPointsAttr().Get())
            transform = np.asarray(transforms.GetLocalToWorldTransform(prim)).T
            points.extend(xyz @ transform[:3, :3].T + transform[:3, 3])
        points = np.asarray(points)
        np.testing.assert_allclose(points.min(0), [-.1, -.45, .495], atol=1e-6)
        np.testing.assert_allclose(points.max(0), [.1, -.25, .501], atol=1e-6)
        before = self.stage.GetSessionLayer().ExportToString()
        configure_harvest_arm(self.stage, '/Robot', _config())
        self.assertEqual(before, self.stage.GetSessionLayer().ExportToString())

    def test_bad_home_fails_before_mutation(self) -> None:
        config = copy.deepcopy(_config())
        config['gripper']['home_position_rad'] = 10
        before = self.stage.GetSessionLayer().ExportToString()
        with self.assertRaises(ValueError):
            configure_harvest_arm(self.stage, '/Robot', config)
        self.assertEqual(before, self.stage.GetSessionLayer().ExportToString())


if __name__ == '__main__':
    unittest.main()
