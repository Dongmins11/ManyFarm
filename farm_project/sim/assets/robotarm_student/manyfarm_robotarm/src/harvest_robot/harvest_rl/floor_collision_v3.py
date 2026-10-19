"""Runtime-only closed-floor alternatives, preserving its visible top and XY."""
import numpy as np


def deepen_world_vertices(points, depth=.05):
    points = np.asarray(points, dtype=float)
    if points.ndim != 2 or points.shape[1] != 3 or not np.isfinite(points).all():
        raise ValueError('Expected finite world vertices')
    top, bottom = points[:, 2].max(), points[:, 2].min()
    if not .005 <= top-bottom <= .007 or depth != .05:
        raise ValueError('Expected verified6mm lid and50mm diagnostic depth')
    out = points.copy()
    out[:, 2] = top - (top-points[:, 2]) * depth/(top-bottom)
    return out


def configure_floor(stage, mode):
    if mode not in ('original', 'hull', 'deep', 'deep-hull'):
        raise ValueError('Unknown closed-floor alternative')
    from pxr import Usd, UsdGeom, UsdPhysics, Gf, Vt
    root = stage.GetPrimAtPath('/World/envs/env_0/Robot/base_footprint/collisions')
    colliders = [p for p in Usd.PrimRange(root, Usd.TraverseInstanceProxies())
        if p.HasAPI(UsdPhysics.CollisionAPI) and any(t in str(p.GetPath())
            for t in ('lid_plus_tile', 'lid_minus_tile'))]
    if len(colliders) != 4:
        raise ValueError('Requires four actual fixed closed-lid tile colliders')
    edits = []
    def editable(path):
        prim = stage.GetPrimAtPath(path)
        while prim.IsInstanceProxy() or prim.IsInstance():
            parent = prim
            while parent and not parent.IsInstance():
                parent = parent.GetParent()
            if not parent or not (str(parent.GetPath())==str(root.GetPath()) or any(t in str(parent.GetPath()) for t in ('lid_plus_tile', 'lid_minus_tile'))):
                raise ValueError('Refuse deinstancing outside fixed-base collision group: '+str(parent.GetPath()) if parent else 'Missing instance root')
            parent.SetInstanceable(False)
            prim = stage.GetPrimAtPath(path)
        return prim

    for collider in colliders:
        if mode != 'original':
            collider = editable(collider.GetPath())
        cache = UsdGeom.XformCache()
        old_approx = UsdPhysics.MeshCollisionAPI(collider).GetApproximationAttr().Get()
        meshes = [p for p in Usd.PrimRange(collider, Usd.TraverseInstanceProxies()) if p.IsA(UsdGeom.Mesh)]
        if len(meshes) != 1:
            raise ValueError('Unexpected tile mesh structure')
        if mode != 'original':
            meshes[0] = editable(meshes[0].GetPath())
        mesh = UsdGeom.Mesh(meshes[0])
        transform = cache.GetLocalToWorldTransform(meshes[0])
        world = np.asarray([transform.Transform(Gf.Vec3d(*map(float, p))) for p in mesh.GetPointsAttr().Get()])
        old = world.copy()
        if mode in ('deep', 'deep-hull'):
            world = deepen_world_vertices(world)
            inverse = transform.GetInverse()
            mesh.GetPointsAttr().Set(Vt.Vec3fArray([Gf.Vec3f(*inverse.Transform(Gf.Vec3d(*p))) for p in world]))
            local = np.asarray(mesh.GetPointsAttr().Get())
            mesh.GetExtentAttr().Set(Vt.Vec3fArray([Gf.Vec3f(*local.min(0)), Gf.Vec3f(*local.max(0))]))
        if mode in ('hull', 'deep-hull'):
            UsdPhysics.MeshCollisionAPI(collider).GetApproximationAttr().Set('convexHull')
        edits.append(dict(path=str(collider.GetPath()), original_approximation=old_approx,
            approximation=UsdPhysics.MeshCollisionAPI(collider).GetApproximationAttr().Get(),
            original_lower_xyz_m=old.min(0).tolist(), original_upper_xyz_m=old.max(0).tolist(),
            lower_xyz_m=world.min(0).tolist(), upper_xyz_m=world.max(0).tolist(),
            mesh_path=str(meshes[0].GetPath())))
    return dict(mode=mode, edits=edits, added_shapes=0, original_usd_modified=False,
        visible_geometry_modified=False, thickness_m=.05 if mode in ('deep','deep-hull') else .006,
        scope='Deinstance fixed-base collision group if required; edit only four stationary closed-lid collision tiles. All other vertices/physics remain; no added rigid body/support force')
