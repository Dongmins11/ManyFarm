"""Verify inherited collision overrides in every cloned physics environment."""
import numpy as np


def audit_floor_clones(env):
    from pxr import UsdGeom, Gf, UsdPhysics
    stage = env.sim.stage
    cache = UsdGeom.XformCache()
    edits = env.floor_override['edits']
    source_origin = env.scene.env_origins[0].cpu().numpy()
    rows = []
    for i in range(env.num_envs):
        origin = env.scene.env_origins[i].cpu().numpy()
        for edit in edits:
            path = edit['path'].replace('/env_0/', f'/env_{i}/')
            mesh_path = edit['mesh_path'].replace('/env_0/', f'/env_{i}/')
            prim, mesh = stage.GetPrimAtPath(path), stage.GetPrimAtPath(mesh_path)
            if not prim or not mesh or not prim.HasAPI(UsdPhysics.CollisionAPI):
                raise ValueError('Missing actual cloned floor collider')
            transform = cache.GetLocalToWorldTransform(mesh)
            xyz = np.asarray([transform.Transform(Gf.Vec3d(*map(float, p)))
                for p in UsdGeom.Mesh(mesh).GetPointsAttr().Get()]) - origin
            lower, upper = xyz.min(0), xyz.max(0)
            if (not np.allclose(lower, np.asarray(edit['lower_xyz_m'])-source_origin, atol=1e-5)
                    or not np.allclose(upper, np.asarray(edit['upper_xyz_m'])-source_origin, atol=1e-5)
                    or UsdPhysics.MeshCollisionAPI(prim).GetApproximationAttr().Get() != edit['approximation']):
                raise ValueError('Clone floor differs from explicit override: '+path)
            rows.append(dict(env_id=i,path=path,lower_xyz_m=lower.tolist(),upper_xyz_m=upper.tolist()))
    return dict(all_clones_verified=True, collider_count=len(rows), rows=rows,
                original_visible_top_and_xy_preserved=True)
