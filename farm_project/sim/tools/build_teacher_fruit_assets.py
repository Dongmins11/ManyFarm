#!/usr/bin/env python3
"""인수 자산 3색과 참조 텍스처만 복사하여 9g 과실 USD를 생성한다.

수신 코드 실행·URDF 변환·Isaac 실행은 하지 않는다. USD/PhysX schema가
설정된 Python으로 --source-assets 및 --output 경로를 지정한다.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil

import numpy as np


def _sha(path: Path) -> str:
    """전달 원본과 생성물의 SHA-256을 계산한다."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_assets(source_assets: Path, output: Path) -> dict:
    """폭70mm·높이75mm·질량9g의 3색 템플릿과 출처 기록을 만든다."""
    from pxr import Gf, PhysxSchema, Sdf, Usd, UsdGeom, UsdPhysics, UsdShade, Vt

    source_assets, output = source_assets.resolve(), output.resolve()
    manifest_path = source_assets / 'manifest.json'
    metadata = json.loads(manifest_path.read_text())
    colors = ('Red', 'Yellow', 'Green')
    source_files, texture_files = set(), set()
    stages = {}
    for color in colors:
        path = source_assets / f'Pepper_{color}.usdc'
        stage = Usd.Stage.Open(str(path))
        if not stage:
            raise ValueError(f'원본 과실 USD를 읽지 못했습니다: {path}')
        if stage.GetRootLayer().GetExternalReferences():
            raise ValueError(f'예상하지 않은 외부 USD 참조가 있습니다: {path}')
        source_files.add(path)
        stages[color] = stage
        for prim in stage.Traverse():
            for attribute in prim.GetAttributes():
                value = attribute.Get()
                if isinstance(value, Sdf.AssetPath) and value.path:
                    resolved = Path(value.resolvedPath)
                    if not resolved.is_file() or not resolved.is_relative_to(source_assets):
                        raise ValueError(f'묶음 내부 텍스처가 아닙니다: {value.path}')
                    texture_files.add(resolved)
    if len(texture_files) != 9:
        raise ValueError(f'3색 과실이 참조하는 텍스처는 9개여야 합니다: {len(texture_files)}')
    copied = []
    for path in sorted(source_files | texture_files):
        relative = path.relative_to(source_assets)
        destination = output / 'source' / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, destination)
        copied.append(dict(path=str(Path('source') / relative), sha256=_sha(path),
                           bytes=path.stat().st_size))

    summary = dict(schema_version=1, source_manifest_sha256=_sha(manifest_path),
                   source_description='수신된 Pepper_RL_Demo/assets 원본. 실행 시 수신 폴더 의존 없음.',
                   diameter_m=.070, height_m=.075, mass_kg=.009,
                   static_friction=1., dynamic_friction=1., restitution=.02,
                   contact_offset_m=.001, rest_offset_m=0.,
                   linear_damping=0., angular_damping=.02,
                   max_linear_velocity_m_s=3., max_angular_velocity_deg_s=20.,
                   copied_files=copied, assets={})
    for color in colors:
        source, meta = stages[color], metadata['Pepper_' + color]
        size = np.diff(np.asarray(meta['bounds'], dtype=float), axis=0)[0]
        if size.shape != (3,) or not np.isfinite(size).all() or np.any(size <= 0):
            raise ValueError(f'{color}: 원본 크기를 확인하세요.')
        scale = np.array([.070 / max(size[:2]), .070 / max(size[:2]), .075 / size[2]])
        attachment = np.asarray(meta['attachment'], dtype=float) * scale
        stage = Usd.Stage.CreateInMemory()
        UsdGeom.SetStageMetersPerUnit(stage, 1.)
        UsdGeom.SetStageUpAxis(stage, 'Z')
        root = UsdGeom.Xform.Define(stage, '/Pepper').GetPrim()
        stage.SetDefaultPrim(root)
        UsdPhysics.RigidBodyAPI.Apply(root).CreateRigidBodyEnabledAttr(True)
        UsdPhysics.MassAPI.Apply(root).CreateMassAttr(.009)
        body = PhysxSchema.PhysxRigidBodyAPI.Apply(root)
        body.CreateEnableCCDAttr(True)
        body.CreateDisableGravityAttr(False)
        body.CreateLinearDampingAttr(0.)
        body.CreateAngularDampingAttr(.02)
        # source env.py의 IsaacLab RigidBodyPropertiesCfg angular 항목 단위는 deg/s.
        body.CreateMaxLinearVelocityAttr(3.)
        body.CreateMaxAngularVelocityAttr(20.)
        visual = UsdGeom.Xform.Define(stage, '/Pepper/Visual')
        visual.GetPrim().GetReferences().AddReference(f'source/Pepper_{color}.usdc')
        visual.AddScaleOp().Set(Gf.Vec3f(*scale))
        transforms = UsdGeom.XformCache()
        points, indices, counts = [], [], []
        for prim in source.Traverse():
            if not prim.IsA(UsdGeom.Mesh):
                continue
            mesh = UsdGeom.Mesh(prim)
            transform = np.asarray(transforms.GetLocalToWorldTransform(prim)).T
            vertices = np.asarray(mesh.GetPointsAttr().Get(), dtype=float)
            vertices = (vertices @ transform[:3, :3].T + transform[:3, 3]) * scale
            offset = len(points)
            points.extend(vertices.tolist())
            indices.extend(offset + int(index) for index in mesh.GetFaceVertexIndicesAttr().Get())
            counts.extend(int(value) for value in mesh.GetFaceVertexCountsAttr().Get())
        if not points:
            raise ValueError(f'{color}: 원본 과실 mesh가 비어 있습니다.')
        points = np.asarray(points, dtype=np.float32)
        collision = UsdGeom.Mesh.Define(stage, '/Pepper/Collision')
        collision.CreatePointsAttr(Vt.Vec3fArray.FromNumpy(points))
        collision.CreateFaceVertexIndicesAttr(indices)
        collision.CreateFaceVertexCountsAttr(counts)
        collision.CreateSubdivisionSchemeAttr('none')
        collision.CreateExtentAttr([Gf.Vec3f(*map(float, points.min(0))),
                                    Gf.Vec3f(*map(float, points.max(0)))])
        collision.CreateVisibilityAttr('invisible')
        UsdPhysics.CollisionAPI.Apply(collision.GetPrim()).CreateCollisionEnabledAttr(True)
        UsdPhysics.MeshCollisionAPI.Apply(collision.GetPrim()).CreateApproximationAttr('convexDecomposition')
        contact = PhysxSchema.PhysxCollisionAPI.Apply(collision.GetPrim())
        contact.CreateContactOffsetAttr(.001)
        contact.CreateRestOffsetAttr(0.)
        material = UsdShade.Material.Define(stage, '/Pepper/PhysicsMaterial')
        physics = UsdPhysics.MaterialAPI.Apply(material.GetPrim())
        physics.CreateStaticFrictionAttr(1.)
        physics.CreateDynamicFrictionAttr(1.)
        physics.CreateRestitutionAttr(.02)
        PhysxSchema.PhysxMaterialAPI.Apply(material.GetPrim()).CreateFrictionCombineModeAttr('average')
        UsdShade.MaterialBindingAPI.Apply(collision.GetPrim()).Bind(
            material, materialPurpose='physics', bindingStrength=UsdShade.Tokens.strongerThanDescendants)
        root.CreateAttribute('teacher:attachmentLocalM', Sdf.ValueTypeNames.Double3,
                             custom=True).Set(Gf.Vec3d(*attachment))
        root.CreateAttribute('teacher:graspCenterLocalM', Sdf.ValueTypeNames.Double3,
                             custom=True).Set(Gf.Vec3d(0., 0., -.006))
        destination = output / f'pepper_{color.lower()}.usd'
        stage.GetRootLayer().Export(str(destination))
        summary['assets'][color.lower()] = dict(
            file=destination.name, sha256=_sha(destination),
            attachment_local_m=attachment.tolist(), source_scale=scale.tolist(),
            bounds_m=[points.min(0).tolist(), points.max(0).tolist()],
            points=len(points), source_asset=f'source/Pepper_{color}.usdc')
    (output / 'provenance.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2) + '\n')
    return summary


def main() -> None:
    """명시한 입력/출력 폴더 안에서만 자산을 생성한다."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-assets', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = build_assets(args.source_assets, args.output)
    print(json.dumps(dict(assets=3, copied_files=len(result['copied_files']),
                          output=str(args.output.resolve())), ensure_ascii=False))


if __name__ == '__main__':
    main()
