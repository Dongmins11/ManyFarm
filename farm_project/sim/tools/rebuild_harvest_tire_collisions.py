"""Isaac Python으로 sim 바퀴의 둥근 타이어 충돌체를 재생성한다.

기존 외경/폭, 질량/관성, 마찰, drive를 보존한다. 기본 원통의 평평한
50mm 접촉선을 기존 외형에 맞는 둥근 단면으로 바꾼다. 회전 방향은
native 원통으로 유지해 convex 다각형의 평평한 면에 걸리는 현상을 피한다.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path


def rebuild(stage: object, wheel_names: tuple[str, str] = ('left_wheel', 'right_wheel')) -> list[dict]:
    """좌우 바퀴 충돌체만 수정하고 적용된 기하를 반환한다."""
    from pxr import Gf, Usd, UsdGeom, UsdPhysics
    root = stage.GetDefaultPrim()
    report = []
    for name in wheel_names:
        wheel = stage.GetPrimAtPath(root.GetPath().AppendChild(name))
        if not wheel:
            raise ValueError('바퀴 몸체 없음: '+name)
        while True:
            instances = [p for p in Usd.PrimRange(wheel.GetChild('collisions')) if p.IsInstance()]
            if not instances:
                break
            for prim in instances:
                prim.SetInstanceable(False)
        originals = [p for p in Usd.PrimRange(wheel)
                     if p.IsA(UsdGeom.Cylinder) and p.HasAPI(UsdPhysics.CollisionAPI)
                     and not p.GetName().startswith('TireCollision')]
        if len(originals) != 1:
            raise ValueError('기준 원통은 바퀴별 하나여야 합니다: '+name)
        original = originals[0]
        cylinder = UsdGeom.Cylinder(original)
        radius = cylinder.GetRadiusAttr().Get()
        width = cylinder.GetHeightAttr().Get()
        if cylinder.GetAxisAttr().Get() != 'Z' or not 0 < width/2 < radius:
            raise ValueError('지원하지 않는 기준 바퀴 축/크기: '+name)
        local = (UsdGeom.Xformable(original).ComputeLocalToWorldTransform(Usd.TimeCode.Default())
                 * UsdGeom.Xformable(wheel).ComputeLocalToWorldTransform(Usd.TimeCode.Default()).GetInverse())
        UsdPhysics.CollisionAPI(original).GetCollisionEnabledAttr().Set(False)
        # 폭/2 원호로 접촉 단면을 둥글게 한다. 외경·폭은 기존 collider 값을 유지한다.
        # 21개 분할의 중앙 원통은 원래 반지름과 같다.
        count = 21
        for i in range(count):
            z = width*((i+.5)/count-.5)
            r = radius-width/2+math.sqrt(max(0., (width/2)**2-z*z))
            tire = UsdGeom.Cylinder.Define(stage, wheel.GetPath().AppendChild('TireCollision%02d'%i))
            tire.CreateRadiusAttr(r)
            tire.CreateHeightAttr(width/count)
            tire.CreateAxisAttr('Z')
            tire.CreateVisibilityAttr('invisible')
            offset = Gf.Matrix4d(1.)
            offset.SetTranslate(Gf.Vec3d(0., 0., z))
            tire.ClearXformOpOrder()
            tire.AddTransformOp().Set(offset*local)
            UsdPhysics.CollisionAPI.Apply(tire.GetPrim())
        report.append(dict(wheel=name, original=str(original.GetPath()), radius_m=radius,
                           width_m=width, slices=count, central_contact_width_m=width/count))
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    root = Path(__file__).resolve().parents[2]
    parser.add_argument('--input', type=Path, default=root/'sim/assets/robots/harvest_count_test/harvest_robot.usd')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    source, output = args.input.resolve(), args.output.resolve()
    if source == output or source.parent != output.parent or not output.is_relative_to(root/'sim'):
        parser.error('원본 보존과 상대 참조 유지를 위해 같은 sim 디렉터리의 다른 출력 파일을 지정하세요.')
    from isaacsim import SimulationApp
    app = SimulationApp({'headless': True})
    try:
        from pxr import Usd
        stage = Usd.Stage.Open(str(source))
        stage.SetEditTarget(stage.GetRootLayer())
        report = rebuild(stage)
        stage.GetRootLayer().Export(str(output))
        output.with_suffix('.tire.json').write_text(json.dumps(dict(
            source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
            output_sha256=hashlib.sha256(output.read_bytes()).hexdigest(), wheels=report), indent=2)+'\n')
        print('[tire_collision] '+json.dumps(report), flush=True)
    finally:
        app.close()


if __name__ == '__main__':
    main()
