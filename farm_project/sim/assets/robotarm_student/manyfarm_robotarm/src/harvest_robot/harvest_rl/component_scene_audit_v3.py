"""Inspect imported named lid meshes as well as legacy floor-link names."""
from .component_scene_audit_v2 import scene_ccd_runtime


def inspect_scene(env):
    from .component_scene_audit import inspect_scene as original
    from pxr import Usd,UsdGeom,UsdPhysics
    report=original(env);stage=env.sim.stage
    cache=UsdGeom.BBoxCache(Usd.TimeCode.Default(),[UsdGeom.Tokens.default_,UsdGeom.Tokens.proxy,UsdGeom.Tokens.render])
    origin=env.scene.env_origins[0].cpu().tolist();shapes=[];floor=[]
    root=stage.GetPrimAtPath('/World/envs/env_0/Robot')
    for prim in Usd.PrimRange(root,Usd.TraverseInstanceProxies()):
        if not prim.HasAPI(UsdPhysics.CollisionAPI):continue
        path=str(prim.GetPath());bound=cache.ComputeWorldBound(prim).ComputeAlignedBox()
        lo=list(bound.GetMin());hi=list(bound.GetMax())
        row=dict(path=path,collision_enabled=UsdPhysics.CollisionAPI(prim).GetCollisionEnabledAttr().Get(),
            approximation=UsdPhysics.MeshCollisionAPI(prim).GetApproximationAttr().Get(),
            world_lower_xyz_m=lo,world_upper_xyz_m=hi,
            policy_lower_xyz_m=[v-o for v,o in zip(lo,origin)],policy_upper_xyz_m=[v-o for v,o in zip(hi,origin)])
        shapes.append(row)
        if any(token in path for token in ('box_bottom','lid_plus_tile','lid_minus_tile','lid_plus_seam','lid_minus_seam')):floor.append(row)
    report.update(floor_colliders=floor,all_robot_collision_shapes=shapes,scene_env0_origin_world_m=origin,
        floor_selection='Imported tile/seam mesh names and legacy bottom-link names; all colliders retained for independent check.')
    return report
