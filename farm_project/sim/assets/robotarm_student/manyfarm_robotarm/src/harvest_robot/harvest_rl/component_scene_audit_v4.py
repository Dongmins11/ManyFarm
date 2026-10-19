"""Read collision mesh vertices even when the render visibility is invisible."""
from .component_scene_audit_v2 import scene_ccd_runtime


def inspect_scene(env):
    import numpy as np
    from pxr import Usd,UsdGeom,UsdPhysics,PhysxSchema,Gf
    stage=env.sim.stage;origin=env.scene.env_origins[0].cpu().numpy()
    transforms=UsdGeom.XformCache();shapes=[];floor=[]
    root=stage.GetPrimAtPath('/World/envs/env_0/Robot')
    for prim in Usd.PrimRange(root,Usd.TraverseInstanceProxies()):
        if not prim.HasAPI(UsdPhysics.CollisionAPI):continue
        path=str(prim.GetPath())
        row=dict(path=path,collision_enabled=UsdPhysics.CollisionAPI(prim).GetCollisionEnabledAttr().Get(),
            approximation=UsdPhysics.MeshCollisionAPI(prim).GetApproximationAttr().Get())
        shapes.append(row)
        if not any(token in path for token in ('box_bottom','lid_plus_tile','lid_minus_tile','lid_plus_seam','lid_minus_seam')):continue
        if not prim.IsA(UsdGeom.Mesh):raise ValueError('Expected imported floor mesh:'+path)
        points=UsdGeom.Mesh(prim).GetPointsAttr().Get();transform=transforms.GetLocalToWorldTransform(prim)
        world=np.asarray([transform.Transform(Gf.Vec3d(*map(float,p))) for p in points])
        if not world.size or not np.isfinite(world).all():raise ValueError('Invalid floor vertices:'+path)
        row.update(world_lower_xyz_m=world.min(0).tolist(),world_upper_xyz_m=world.max(0).tolist(),
            policy_lower_xyz_m=(world.min(0)-origin).tolist(),policy_upper_xyz_m=(world.max(0)-origin).tolist(),
            bounds_method='Authored mesh vertices transformed directly; invisible render purpose ignored')
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
        note='Actual cached robot USD floor vertices, not legacy URDF or visibility-filtered empty bounds; cooking is separately tested by physical runs.')
