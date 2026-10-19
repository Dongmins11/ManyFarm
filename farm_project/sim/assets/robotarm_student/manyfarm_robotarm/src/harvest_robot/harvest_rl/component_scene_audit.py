"""Separate explicit CCD scene comparison and read-only box collision inspection."""
from contextlib import contextmanager


@contextmanager
def scene_ccd_runtime(enabled):
    from .env import HarvestEnvCfg
    config=HarvestEnvCfg.sim.physx
    previous=config.enable_ccd
    config.enable_ccd=bool(enabled)
    try: yield dict(previous_enable_ccd=previous,requested_enable_ccd=bool(enabled))
    finally: config.enable_ccd=previous


def inspect_scene(env):
    from pxr import Usd, UsdGeom, UsdPhysics, PhysxSchema
    stage=env.sim.stage
    cache=UsdGeom.BBoxCache(Usd.TimeCode.Default(),[UsdGeom.Tokens.default_,UsdGeom.Tokens.proxy,UsdGeom.Tokens.render])
    robot=stage.GetPrimAtPath('/World/envs/env_0/Robot')
    floor=[]
    for prim in Usd.PrimRange(robot,Usd.TraverseInstanceProxies()):
        if not prim.HasAPI(UsdPhysics.CollisionAPI) or 'box_bottom' not in str(prim.GetPath()): continue
        bound=cache.ComputeWorldBound(prim).ComputeAlignedBox()
        floor.append(dict(path=str(prim.GetPath()),collision_enabled=UsdPhysics.CollisionAPI(prim).GetCollisionEnabledAttr().Get(),
            approximation=UsdPhysics.MeshCollisionAPI(prim).GetApproximationAttr().Get(),
            world_lower_xyz_m=list(bound.GetMin()),world_upper_xyz_m=list(bound.GetMax())))
    scenes=[]
    for prim in stage.Traverse():
        if prim.IsA(UsdPhysics.Scene):
            scenes.append(dict(path=str(prim.GetPath()),enable_ccd=PhysxSchema.PhysxSceneAPI(prim).GetEnableCCDAttr().Get()))
    fruits=[]
    for fruit in env.fruits:
        path=fruit.root_physx_view.prim_paths[0];body=stage.GetPrimAtPath(path)
        fruits.append(dict(path=path,enable_ccd=PhysxSchema.PhysxRigidBodyAPI(body).GetEnableCCDAttr().Get(),
            max_depenetration_velocity=PhysxSchema.PhysxRigidBodyAPI(body).GetMaxDepenetrationVelocityAttr().Get()))
    return dict(sim_config_enable_ccd=bool(env.cfg.sim.physx.enable_ccd),physics_scenes=scenes,
        floor_colliders=floor,fruit_bodies=fruits,box_min=env.settings.box_min,box_max=env.settings.box_max,
        note='Authored world bounds for fixed box colliders; not a dump of PhysX cooked convex parts.')
