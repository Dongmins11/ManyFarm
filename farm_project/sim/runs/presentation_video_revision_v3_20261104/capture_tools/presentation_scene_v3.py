"""발표 V3의 기존 바닥 외형 복원과 촬영 전용 과실 복제. 원본은 저장하지 않는다."""
from pathlib import Path


HANDOFF_SOURCES = (
    '/World/Vegetation/Bed_04/Fruits/Pepper_0005_red',
    '/World/Vegetation/Bed_05/Fruits/Pepper_0035_yellow',
    '/World/Vegetation/Bed_08/Fruits/Pepper_0002_red',
    '/World/Vegetation/Bed_06/Fruits/Pepper_0029_yellow',
    '/World/Vegetation/Bed_06/Fruits/Pepper_0026_red',
    '/World/Vegetation/Bed_04/Fruits/Pepper_0003_yellow',
    '/World/Vegetation/Bed_07/Fruits/Pepper_0007_red',
)


def install_handoff_assets(stage: object, project_root: Path, harvest_root: str) -> dict:
    """기존 개폐 링크에 원본 판 메시를 연결하고 7개 복제본을 숨긴 채 준비한다."""
    from pxr import Gf, Sdf, Usd, UsdGeom, UsdShade

    if stage.GetEditTarget().GetLayer() != stage.GetSessionLayer():
        raise ValueError('V3 촬영 자산은 session layer에만 작성해야 합니다.')
    floor_asset = Path(project_root) / 'sim/assets/robots/harvest_physics/box_floor_v3.usd'
    floor_paths = []
    diagnostics = {'floor_asset': str(floor_asset), 'floor_mode': 'existing_plus_minus_mesh_reference',
                   'panel_travel_m': 0.105, 'panel_thickness_m': 0.006, 'panel_local_raise_m': 0.005,
                   'source_mesh_missing': {}, 'fruit_sources': list(HANDOFF_SOURCES)}
    material = UsdShade.Material.Define(stage, '/World/PresentationMaterials/HarvestFloor')
    shader = UsdShade.Shader.Define(stage, material.GetPath().AppendChild('Surface'))
    shader.CreateIdAttr('UsdPreviewSurface')
    shader.CreateInput('diffuseColor', Sdf.ValueTypeNames.Color3f).Set(Gf.Vec3f(.30, .32, .34))
    shader.CreateInput('roughness', Sdf.ValueTypeNames.Float).Set(.65)
    shader.CreateInput('opacity', Sdf.ValueTypeNames.Float).Set(1.)
    material.CreateSurfaceOutput().ConnectToSource(shader.ConnectableAPI(), 'surface')
    for side, asset_part in (('left', 'Plus'), ('right', 'Minus')):
        body_path = harvest_root + '/box_bottom_' + side
        body = stage.GetPrimAtPath(body_path)
        if not body:
            raise ValueError('기존 바닥 개폐 링크 없음: ' + body_path)
        visuals = body.GetChild('visuals')
        if visuals and visuals.IsInstance():
            visuals.SetInstanceable(False)
        existing = [p for p in Usd.PrimRange(body) if p.IsA(UsdGeom.Mesh)]
        diagnostics['source_mesh_missing'][body_path] = not bool(existing)
        # MakeVisible는 숨긴 조상을 풀고 형제들을 숨기므로 국소 속성만 설정한다.
        if existing:
            for prim in existing:
                UsdGeom.Imageable(prim).GetVisibilityAttr().Set(UsdGeom.Tokens.inherited)
                UsdShade.MaterialBindingAPI.Apply(prim).Bind(material)
            floor_paths.extend(str(p.GetPath()) for p in existing)
        else:
            path = body_path + '/PresentationRestoredFloor'
            prim = UsdGeom.Xform.Define(stage, path).GetPrim()
            prim.GetReferences().AddReference(str(floor_asset), '/HarvestBoxFloor/' + asset_part)
            # 원본 옆벽 하단 z=.506에 바닥 윗면을 맞춘다. 개폐 링크는 그대로다.
            UsdGeom.Xformable(prim).AddTranslateOp().Set(Gf.Vec3d(0., 0., .005))
            UsdGeom.Imageable(prim).GetVisibilityAttr().Set(UsdGeom.Tokens.inherited)
            UsdShade.MaterialBindingAPI.Apply(prim).Bind(material,
                bindingStrength=UsdShade.Tokens.strongerThanDescendants)
            floor_paths.append(path)
    UsdGeom.Xform.Define(stage, '/World/PresentationFruits')
    clone_paths = []
    for index, source in enumerate(HANDOFF_SOURCES, 1):
        if not stage.GetPrimAtPath(source):
            raise ValueError('기존 파프리카 복제 원본 없음: ' + source)
        path = f'/World/PresentationFruits/Handoff_{index:02d}'
        prim = UsdGeom.Xform.Define(stage, path).GetPrim()
        prim.GetReferences().AddInternalReference(source)
        prim.SetInstanceable(False)
        # 이동 복제의 Model native instance도 세션에서 풀어 렌더 변환 갱신을 분리한다.
        while True:
            instances = [child for child in Usd.PrimRange(prim) if child.IsInstance()]
            if not instances:
                break
            for child in instances:
                child.SetInstanceable(False)
        # 촬영 복제에는 운영 과실 ID/집계 속성을 전달하지 않는다.
        for attr in prim.GetAttributes():
            if attr.GetName().startswith('crop:'):
                attr.Block()
        UsdGeom.Imageable(prim).MakeInvisible()
        clone_paths.append(path)
    return {'clone_paths': clone_paths, 'floor_paths': floor_paths, 'diagnostics': diagnostics}
