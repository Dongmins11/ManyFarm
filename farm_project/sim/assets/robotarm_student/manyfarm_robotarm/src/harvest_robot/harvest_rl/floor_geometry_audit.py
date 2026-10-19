"""Read authored collider vertices regardless of render visibility."""
import numpy as np


def floor_geometry(stage, env_origin=(0., 0., 0.)):
    from pxr import Usd, UsdGeom, UsdPhysics, UsdShade, Gf
    cache = UsdGeom.XformCache()
    result = []
    root = stage.GetPrimAtPath('/World/envs/env_0/Robot/base_footprint')
    for p in Usd.PrimRange(root, Usd.TraverseInstanceProxies()):
        if not p.HasAPI(UsdPhysics.CollisionAPI) or 'lid_' not in str(p.GetPath()):
            continue
        world = []
        mesh_paths = []
        for mesh in Usd.PrimRange(p, Usd.TraverseInstanceProxies()):
            if not mesh.IsA(UsdGeom.Mesh):
                continue
            points = UsdGeom.Mesh(mesh).GetPointsAttr().Get()
            transform = cache.GetLocalToWorldTransform(mesh)
            world.extend(transform.Transform(Gf.Vec3d(*map(float, pt))) for pt in points)
            mesh_paths.append(str(mesh.GetPath()))
        if not world:
            continue
        xyz = np.asarray(world) - np.asarray(env_origin)
        material, _ = UsdShade.MaterialBindingAPI(p).ComputeBoundMaterial('physics')
        result.append(dict(path=str(p.GetPath()), lower_xyz_m=xyz.min(0).tolist(),
            upper_xyz_m=xyz.max(0).tolist(), points=len(world), mesh_paths=mesh_paths,
            approximation=UsdPhysics.MeshCollisionAPI(p).GetApproximationAttr().Get(),
            enabled=UsdPhysics.CollisionAPI(p).GetCollisionEnabledAttr().Get(),
            material=str(material.GetPath()) if material else None,
            physics_attributes={a.GetName():str(a.Get()) for a in p.GetAttributes()
                if a.GetName().startswith(('physics:', 'physxCollision:', 'physxConvexDecomposition:'))}))
    if not result:
        raise ValueError('No actual fixed box/lid colliders')
    return result
