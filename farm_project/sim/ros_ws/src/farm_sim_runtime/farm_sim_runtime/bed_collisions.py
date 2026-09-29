"""Restore static farm-bed colliders in the session layer, before physics starts."""
from pxr import Usd, UsdGeom, UsdPhysics


def ensure_bed_collisions(stage, root_path='/World/farm_framechanged'):
    root = stage.GetPrimAtPath(root_path)
    if not root.IsValid():
        raise RuntimeError(f'베드 collision 대상이 없습니다: {root_path}. 배경 USD 로딩/참조 경로를 확인하세요.')
    meshes = []
    for group in root.GetChildren():
        if group.GetName().startswith(('GrowBed_', 'Bed_Edge_')):
            meshes.extend(p for p in Usd.PrimRange(group) if p.IsA(UsdGeom.Mesh))
    if not meshes:
        raise RuntimeError(f'{root_path} 아래에 GrowBed/Bed_Edge 메시가 없습니다.')
    if any(p.IsInstanceProxy() for p in meshes):
        raise RuntimeError('베드가 instance proxy입니다. 직접 collision을 수정할 수 없습니다.')
    added = enabled = existing = 0
    with Usd.EditContext(stage, stage.GetSessionLayer()):
        for prim in meshes:
            if not prim.HasAPI(UsdPhysics.CollisionAPI):
                UsdPhysics.CollisionAPI.Apply(prim).CreateCollisionEnabledAttr(True)
                # Current GrowBed and Bed_Edge meshes are cuboids. Static convex
                # shapes avoid triangle winding/back-face sensitivity in queries.
                UsdPhysics.MeshCollisionAPI.Apply(prim).CreateApproximationAttr('convexHull')
                added += 1
            else:
                collision = UsdPhysics.CollisionAPI(prim)
                if not collision.GetCollisionEnabledAttr().Get():
                    collision.CreateCollisionEnabledAttr(True)
                    enabled += 1
                else:
                    existing += 1
    return dict(mesh_count=len(meshes), added=added, enabled=enabled, existing=existing,
                paths=[str(p.GetPath()) for p in meshes])
