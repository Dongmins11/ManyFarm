"""PhysX와 렌더러가 함께 갱신할 수 있는 과실의 표준 USD pose 작성."""
import numpy as np


def set_rigid_local_pose(prim: object, local_matrix: object) -> None:
    """위치를 보존하면서 custom matrix 대신 표준 translate/orient/scale을 쓴다.

    사용자 정의 matrix op로 고정하면 동적 전환 후 PhysX pose와 화면 변환이
    분리될 수 있다. 호출자가 물리 전환 경계와 session edit context를 보장한다.
    """
    from pxr import Gf, UsdGeom
    matrix = np.asarray(local_matrix, dtype=float)
    if matrix.shape != (4, 4) or not np.isfinite(matrix).all():
        raise ValueError('유한한 4x4 로컬 변환이 필요합니다.')
    transform = Gf.Transform(Gf.Matrix4d(*matrix.T.reshape(-1)))
    xform = UsdGeom.Xformable(prim)
    xform.ClearXformOpOrder()
    xform.SetResetXformStack(False)
    ops = []
    for name, value, create in (
            ('translate', transform.GetTranslation(), xform.AddTranslateOp),
            ('orient', transform.GetRotation().GetQuat(), xform.AddOrientOp),
            ('scale', transform.GetScale(), xform.AddScaleOp)):
        attr = prim.GetAttribute('xformOp:'+name)
        op = UsdGeom.XformOp(attr) if attr else create(precision=UsdGeom.XformOp.PrecisionDouble)
        if name == 'orient' and str(op.GetAttr().GetTypeName()) == 'quatf':
            value = Gf.Quatf(value)
        op.Set(value)
        ops.append(op)
    xform.SetXformOpOrder(ops)
