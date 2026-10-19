"""Resolve imported Xform colliders to their descendant mesh vertices."""
from .component_scene_audit_v2 import scene_ccd_runtime


def inspect_scene(env):
    import numpy as np
    from pxr import Usd,UsdGeom,UsdPhysics,PhysxSchema,Gf
    stage=env.sim.stage;origin=env.scene.env_origins[0].cpu().numpy()
    transforms=UsdGeom.XformCache();shapes=[];floor=[]
    root=stage.GetPrimAtPath('/World/envs/env_0/Robot')
    for prim in Usd.PrimRange(root,Usd.TraverseInstanceProxies()):
        if not prim.HasAPI(UsdPhysics.CollisionAPI):continue
        path=str(prim.GetPath());row=dict(path=path,type_name=prim.GetTypeName(),
            collision_enabled=UsdPhysics.CollisionAPI(prim).GetCollisionEnabledAttr().Get(),
            approximation=UsdPhysics.MeshCollisionAPI(prim).GetApproximationAttr().Get())
        shapes.append(row)
        if not any(token in path for token in ('box_bottom','lid_plus_tile','lid_minus_tile','lid_plus_seam','lid_minus_seam')):continue
        world=[];mesh_paths=[]
        for mesh_prim in Usd.PrimRange(prim,Usd.TraverseInstanceProxies()):
            if not mesh_prim.IsA(UsdGeom.Mesh):continue
            points=UsdGeom.Mesh(mesh_prim).GetPointsAttr().Get();transform=transforms.GetLocalToWorldTransform(mesh_prim)
            world.extend([transform.Transform(Gf.Vec3d(*map(float,p))) for p in points]);mesh_paths.append(str(mesh_prim.GetPath()))
        world=np.asarray(world)
        if not world.size or not np.isfinite(world).all():raise ValueError('No valid descendant floor mesh:'+path)
        row.update(world_lower_xyz_m=world.min(0).tolist(),world_upper_xyz_m=world.max(0).tolist(),
            policy_lower_xyz_m=(world.min(0)-origin).tolist(),policy_upper_xyz_m=(world.max(0)-origin).tolist(),mesh_paths=mesh_paths,
            bounds_method='Authored descendant vertices transformed directly; invisible visibility ignored')
        floor.append(row)
    scenes=[dict(path=str(p.GetPath()),enable_ccd=PhysxSchema.PhysxSceneAPI(p).GetEnableCCDAttr().Get())
            for p in stage.Traverse() if p.IsA(UsdPhysics.Scene)]
    fruits=[]
    for fruit in env.fruits:
        path=fruit.root_physx_view.prim_paths[0];body=stage.GetPrimAtPath(path)
        fruits.append(dict(path=path,enable_ccd=PhysxSchema.PhysxRigidBodyAPI(body).GetEnableCCDAttr().Get(),
            max_depenetration_velocity=PhysxSchema.PhysxRigidBodyAPI(body).GetMaxDepenetrationVelocityAttr().Get()))
    return dict(sim_config_enable_ccd=bool(env.cfg.sim.physx.enable_ccd),physics_scenes=scenes,
        floor_colliders=floor,all_robot_collision_shapes=shapes,fruit_bodies=fruits,
        box_min=env.settings.box_min,box_max=env.settings.box_max,
        note='Actual cached USD invisible Xform collider descendant vertices; cooking is tested by physical runs.')
