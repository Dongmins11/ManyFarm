"""학습 팔의 메시·질량·관성·접촉 설정 일치와 차체 구동 보존 회귀 검사."""
import json
from pathlib import Path
import sys
import unittest
from types import SimpleNamespace
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'sim/ros_ws/src/farm_sim_runtime'))
try:
    from pxr import Usd, UsdGeom, UsdPhysics, UsdShade
except ImportError:
    Usd = None
from farm_sim_runtime.teacher_arm_alignment import BODY_NAMES, align_teacher_scene
from farm_sim_runtime.robotarm_asset_setup import configure_harvest_arm


@unittest.skipIf(Usd is None, 'Isaac USD 환경 필요')
class TeacherAlignmentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.stage = Usd.Stage.CreateInMemory()
        UsdGeom.SetStageMetersPerUnit(cls.stage, 1)
        UsdGeom.SetStageUpAxis(cls.stage, 'Z')
        UsdGeom.Xform.Define(cls.stage, '/Robot').GetPrim().GetReferences().AddReference(
            str(ROOT/'sim/assets/robots/harvest_count_test/harvest_robot.usd'))
        cls.root_before = cls.stage.GetRootLayer().ExportToString()
        cls.wheels_before = {p.GetName(): str(p.GetAttribute('drive:angular:physics:damping').Get())
                            for p in cls.stage.Traverse() if p.GetName() in ('left_wheel_joint','right_wheel_joint')}
        config = json.loads((ROOT/'sim/ros_ws/src/farm_sim_config/config/robotarm_physics.json').read_text())
        for key in ('box_floor','teacher_alignment'):
            if 'asset_path' in config[key]:
                config[key]['asset_path'] = str(ROOT/config[key]['asset_path'])
        cls.reference = Usd.Stage.Open(config['teacher_alignment']['asset_path'])
        cls.report = configure_harvest_arm(cls.stage, '/Robot', config)

    def test_exact_collision_geometry_and_link_transforms(self) -> None:
        count = 0
        for name in BODY_NAMES:
            source = self.reference.GetPrimAtPath('/TeacherArm/'+name+'/collisions')
            for p in Usd.PrimRange(source):
                suffix = str(p.GetPath()).split('/collisions', 1)[1]
                actual = self.stage.GetPrimAtPath('/Robot/'+name+'/TeacherCollisions'+suffix)
                self.assertTrue(actual)
                for attr in p.GetAttributes():
                    if attr.GetName().startswith(('xformOp','physics:','physx')) or attr.GetName() in (
                            'points','faceVertexCounts','faceVertexIndices','size'):
                        self.assertEqual(str(actual.GetAttribute(attr.GetName()).Get()), str(attr.Get()),
                                         str(p.GetPath())+':'+attr.GetName())
                if p.HasAPI(UsdPhysics.CollisionAPI):
                    count += 1
                    self.assertFalse(actual.GetAttribute('physxCollision:contactOffset').HasAuthoredValueOpinion())
        self.assertEqual(count, 15)

    def test_mass_com_inertia_and_axes_match(self) -> None:
        for name in BODY_NAMES:
            source = self.reference.GetPrimAtPath('/TeacherArm/'+name)
            actual = self.stage.GetPrimAtPath('/Robot/'+name)
            for key in ('mass','centerOfMass','diagonalInertia','principalAxes'):
                self.assertEqual(str(actual.GetAttribute('physics:'+key).Get()),
                                 str(source.GetAttribute('physics:'+key).Get()))
        self.assertAlmostEqual(self.stage.GetPrimAtPath('/Robot/arm_2_gripper_link').GetAttribute('physics:mass').Get(), .18)

    def test_fixed_camera_not_double_counted(self) -> None:
        for path in self.report['teacher_alignment']['disabled']:
            self.assertFalse(self.stage.GetPrimAtPath(path).IsActive())
        self.assertTrue(self.stage.GetPrimAtPath('/Robot/arm_2_gripper_link/TeacherVisuals/d435_wrist_mount'))

    def test_materials_and_articulation(self) -> None:
        for name in BODY_NAMES:
            for p in Usd.PrimRange(self.stage.GetPrimAtPath('/Robot/'+name+'/TeacherCollisions')):
                if p.HasAPI(UsdPhysics.CollisionAPI):
                    mat, _ = UsdShade.MaterialBindingAPI(p).ComputeBoundMaterial('physics')
                    finger = any(token in str(p.GetPath()) for token in ('wrist_roll_follower_so101_v1', 'moving_jaw_so101_v1'))
                    expected = 2.2 if finger else (1. if name in BODY_NAMES[-2:] else .8)
                    self.assertAlmostEqual(mat.GetPrim().GetAttribute('physics:dynamicFriction').Get(), expected)
        root = self.stage.GetPrimAtPath(self.report['teacher_alignment']['articulation_root'])
        self.assertTrue(root.GetAttribute('physxArticulation:enabledSelfCollisions').Get())
        # 이동 차체의 원호 정지 시험에 따른 시뮬 프로파일만 정밀도를 높인다.
        self.assertEqual(root.GetAttribute('physxArticulation:solverPositionIterationCount').Get(), 64)
        self.assertEqual(root.GetAttribute('physxArticulation:solverVelocityIterationCount').Get(), 4)

    def test_joint_frames_limits_and_drive_units(self) -> None:
        for i, path in enumerate(self.report['joint_paths']):
            actual = self.stage.GetPrimAtPath(path)
            source = self.reference.GetPrimAtPath('/TeacherArm/joints/'+actual.GetName())
            keys = ['physics:localPos1','physics:localRot1','physics:lowerLimit','physics:upperLimit']
            if i:
                keys += ['physics:localPos0','physics:localRot0']
            for key in keys:
                np.testing.assert_allclose(np.array(actual.GetAttribute(key).Get()) if 'Rot' not in key else
                    [*actual.GetAttribute(key).Get().GetImaginary(),actual.GetAttribute(key).Get().GetReal()],
                    np.array(source.GetAttribute(key).Get()) if 'Rot' not in key else
                    [*source.GetAttribute(key).Get().GetImaginary(),source.GetAttribute(key).Get().GetReal()], atol=1e-6)
            self.assertAlmostEqual(actual.GetAttribute('drive:angular:physics:stiffness').Get(),
                                   (25. if i<5 else 8.)*np.pi/180, places=6)

    def test_source_and_wheel_drives_are_preserved(self) -> None:
        self.assertEqual(self.root_before,self.stage.GetRootLayer().ExportToString())
        after={p.GetName():str(p.GetAttribute('drive:angular:physics:damping').Get())
               for p in self.stage.Traverse() if p.GetName() in self.wheels_before}
        self.assertEqual(after,self.wheels_before)

    def test_scene_contact_solver_matches_reference(self) -> None:
        stage = Usd.Stage.CreateInMemory()
        prim = UsdPhysics.Scene.Define(stage, '/Scene').GetPrim()
        calls = {}
        context = SimpleNamespace(get_current_physics_scene_prim=lambda: prim,
            enable_gpu_dynamics=lambda value: calls.update(gpu=value),
            set_broadphase_type=lambda value: calls.update(broadphase=value))
        align_teacher_scene(SimpleNamespace(get_physics_context=lambda: context))
        self.assertEqual(calls, dict(gpu=True, broadphase='GPU'))
        self.assertEqual(prim.GetAttribute('physxScene:solverType').Get(), 'TGS')
        self.assertFalse(prim.GetAttribute('physxScene:enableStabilization').Get())
        self.assertFalse(prim.GetAttribute('physxScene:solveArticulationContactLast').Get())
        self.assertAlmostEqual(prim.GetAttribute('physxScene:bounceThreshold').Get(), .5)
        self.assertEqual(prim.GetAttribute('physxScene:gpuFoundLostPairsCapacity').Get(), 4194304)


if __name__ == '__main__':
    unittest.main()
