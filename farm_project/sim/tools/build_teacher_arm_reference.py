"""전달 USD의 오른팔 몸체/충돌 메시를 경로 독립적인 검증 기준 자산으로 추출한다."""
from pathlib import Path
import argparse
import hashlib
import json

BODY_NAMES = ('arm_2_shoulder_link', 'arm_2_upper_arm_link', 'arm_2_lower_arm_link',
              'arm_2_wrist_link', 'arm_2_gripper_link', 'arm_2_moving_jaw_so101_v1_link')


def build(source: Path, destination: Path) -> None:
    """형상을 재근사화하지 않고 전달된 메시·변환·질량·관성을 복사한다."""
    from pxr import Sdf, Usd, UsdGeom
    stage = Usd.Stage.Open(str(source.resolve()))
    # 인스턴스를 펼쳐 외부 prototype 의존성을 없앤다.
    while True:
        instances = [p for p in stage.Traverse() if p.IsInstance()]
        if not instances:
            break
        for p in instances:
            p.SetInstanceable(False)
    flat = stage.Flatten()
    destination.parent.mkdir(parents=True, exist_ok=True)
    output = Usd.Stage.CreateNew(str(destination))
    root = UsdGeom.Xform.Define(output, '/TeacherArm').GetPrim()
    output.SetDefaultPrim(root)
    UsdGeom.SetStageMetersPerUnit(output, 1)
    UsdGeom.SetStageUpAxis(output, 'Z')
    source_root = stage.GetDefaultPrim().GetPath()
    for name in (*BODY_NAMES, 'Looks', 'joints'):
        src = source_root.AppendChild(name)
        if not Sdf.CopySpec(flat, src, output.GetRootLayer(), root.GetPath().AppendChild(name)):
            raise RuntimeError('기준 자산 추출 실패: '+str(src))
    for prim in output.Traverse():
        for rel in prim.GetRelationships():
            rel.SetTargets([p.ReplacePrefix(source_root, root.GetPath()) for p in rel.GetTargets()])
        for attr in prim.GetAttributes():
            if attr.GetConnections():
                attr.SetConnections([p.ReplacePrefix(source_root, root.GetPath()) for p in attr.GetConnections()])
    output.GetRootLayer().Save()
    layers = {str(layer.realPath): hashlib.sha256(Path(layer.realPath).read_bytes()).hexdigest()
              for layer in stage.GetUsedLayers() if layer.realPath}
    destination.with_suffix('.json').write_text(json.dumps(dict(source=str(source.resolve()),
        source_layers_sha256=layers, asset_sha256=hashlib.sha256(destination.read_bytes()).hexdigest(),
        body_names=BODY_NAMES, note='전달 current_robot USD에서 추출; runtime drive/material/solver는 별도 적용'),
        ensure_ascii=False, indent=2)+'\n')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('destination', type=Path)
    args = parser.parse_args()
    build(args.source, args.destination)
