"""과실 고정/동적 전환에서도 표준 pose 연산과 물리 위치가 보존돼야 한다."""
from pathlib import Path
import sys
import unittest
import numpy as np
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'sim/ros_ws/src/farm_sim_devices'))
from farm_sim_devices.fruit_pose import set_rigid_local_pose
try:
    from pxr import Usd,UsdGeom,Gf
except ImportError:
    Usd=None


@unittest.skipIf(Usd is None,'Isaac USD 환경 필요')
class FruitPoseTests(unittest.TestCase):
    def test_custom_matrix_is_replaced_without_pose_jump(self) -> None:
        stage=Usd.Stage.CreateInMemory()
        x=UsdGeom.Xform.Define(stage,'/Fruit')
        matrix=Gf.Matrix4d().SetRotate(Gf.Rotation(Gf.Vec3d(1,2,3),37))
        matrix.SetTranslateOnly(Gf.Vec3d(4,-3,2))
        x.AddTransformOp(opSuffix='fruitFreeze').Set(matrix)
        child=UsdGeom.Xform.Define(stage,'/Fruit/Visual')
        child.AddScaleOp().Set(Gf.Vec3f(.7,.8,.9))
        before=np.array(UsdGeom.XformCache().GetLocalToWorldTransform(child.GetPrim()))
        for _ in range(3):
            set_rigid_local_pose(x.GetPrim(),np.array(matrix).T)
            self.assertEqual([o.GetOpName() for o in x.GetOrderedXformOps()],
                             ['xformOp:translate','xformOp:orient','xformOp:scale'])
            np.testing.assert_allclose(UsdGeom.XformCache().GetLocalToWorldTransform(child.GetPrim()),before,atol=1e-7)
        # PhysX가 갱신하는 표준 translate가 실제 표시 메시에도 영향을 주는지 확인한다.
        x.GetPrim().GetAttribute('xformOp:translate').Set(Gf.Vec3d(4,-3,3))
        after=UsdGeom.XformCache().GetLocalToWorldTransform(child.GetPrim())
        self.assertAlmostEqual(after.ExtractTranslation()[2],3.)

    def test_existing_float_quaternion_and_local_scale_are_preserved(self) -> None:
        stage=Usd.Stage.CreateInMemory();x=UsdGeom.Xform.Define(stage,'/Fruit')
        x.AddOrientOp(precision=UsdGeom.XformOp.PrecisionFloat).Set(Gf.Quatf(1))
        matrix=np.diag([.5,.75,1.2,1.]);matrix[:3,3]=[1,2,3]
        set_rigid_local_pose(x.GetPrim(),matrix)
        np.testing.assert_allclose(np.array(x.GetLocalTransformation()).T,matrix,atol=1e-6)
        with self.assertRaises(ValueError):
            set_rigid_local_pose(x.GetPrim(),np.full((4,4),np.nan))


if __name__=='__main__':unittest.main()
