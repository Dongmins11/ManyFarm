"""Replace closed-lid tiles/straps by one exact box on the SAME fixed body."""
import itertools
import numpy as np


def configure_floor(stage,mode='unified'):
    if mode!='unified':raise ValueError('Requires explicit unified closed-floor transfer')
    from pxr import Usd,UsdGeom,UsdPhysics,PhysxSchema,UsdShade,Gf
    from .floor_collision_v4 import configure_floor as inspect
    original=inspect(stage,'original')
    root=stage.GetPrimAtPath('/World/envs/env_0/Robot/base_footprint/collisions')
    if root.IsInstance():root.SetInstanceable(False)
    if root.IsInstanceProxy():raise ValueError('Unexpected fixed collision instance root')
    disabled=[]
    for prim in Usd.PrimRange(root,Usd.TraverseInstanceProxies()):
        if not prim.HasAPI(UsdPhysics.CollisionAPI):continue
        if not any(token in str(prim.GetPath()) for token in
            ('lid_plus_tile','lid_minus_tile','lid_plus_seam_strap','lid_minus_seam_strap')):continue
        if prim.IsInstanceProxy():raise ValueError('Unexpected nested floor collider instance')
        UsdPhysics.CollisionAPI(prim).GetCollisionEnabledAttr().Set(False)
        disabled.append(str(prim.GetPath()))
    if len(disabled)!=8:raise ValueError('Requires exactly four tiles and four seam straps')
    lower=np.min([e['original_lower_xyz_m'] for e in original['edits']],axis=0)
    upper=np.max([e['original_upper_xyz_m'] for e in original['edits']],axis=0)
    lower[2]=upper[2]-.05
    size=upper-lower;center=(upper+lower)/2
    path=str(root.GetPath())+'/ClosedDepositFloor'
    cube=UsdGeom.Cube.Define(stage,path);cube.CreateSizeAttr().Set(1.)
    world=Gf.Matrix4d(1.);world.SetScale(Gf.Vec3d(*map(float,size)))
    world.SetTranslateOnly(Gf.Vec3d(*map(float,center)))
    parent=UsdGeom.XformCache().GetLocalToWorldTransform(root)
    UsdGeom.Xformable(cube).AddTransformOp().Set(world*parent.GetInverse())
    cube.CreateVisibilityAttr().Set('invisible')
    prim=cube.GetPrim()
    UsdPhysics.CollisionAPI.Apply(prim).CreateCollisionEnabledAttr().Set(True)
    api=PhysxSchema.PhysxCollisionAPI.Apply(prim)
    api.CreateContactOffsetAttr().Set(.04);api.CreateRestOffsetAttr().Set(0.)
    source=stage.GetPrimAtPath(original['edits'][0]['path'])
    material,_=UsdShade.MaterialBindingAPI(source).ComputeBoundMaterial('physics')
    if material:UsdShade.MaterialBindingAPI.Apply(prim).Bind(material,materialPurpose='physics')
    return dict(mode='unified',shape_type='Cube',added_shapes=1,disabled_shapes=disabled,
        added_rigid_bodies=0,body='/World/envs/env_0/Robot/base_footprint',path=path,
        lower_xyz_m=lower.tolist(),upper_xyz_m=upper.tolist(),original_tiles=original['edits'],
        original_usd_modified=False,visible_geometry_modified=False,
        contact_offset_m=.04,rest_offset_m=0.,depth_m=.05,
        material=str(material.GetPath()) if material else None,
        scope='Runtime-only stationary CLOSED box collision surface; unchanged visible lid/XY/top/walls and same fixed rigid body')


def audit_floor_clones(env):
    from pxr import UsdGeom,UsdPhysics,PhysxSchema,Gf
    stage=env.sim.stage;cache=UsdGeom.XformCache();source=env.floor_override
    origin0=env.scene.env_origins[0].cpu().numpy();rows=[]
    for i in range(env.num_envs):
        path=source['path'].replace('/env_0/',f'/env_{i}/')
        prim=stage.GetPrimAtPath(path);body=stage.GetPrimAtPath(source['body'].replace('/env_0/',f'/env_{i}/'))
        if not prim.IsA(UsdGeom.Cube) or prim.HasAPI(UsdPhysics.RigidBodyAPI) or not body.HasAPI(UsdPhysics.RigidBodyAPI):
            raise ValueError('Unified floor must share original fixed body')
        api=PhysxSchema.PhysxCollisionAPI(prim)
        if abs(api.GetContactOffsetAttr().Get()-.04)>1e-7 or abs(api.GetRestOffsetAttr().Get())>1e-7:
            raise ValueError('Actual speculative/rest offsets differ')
        t=cache.GetLocalToWorldTransform(prim)
        points=np.asarray([t.Transform(Gf.Vec3d(*p)) for p in itertools.product((-.5,.5),repeat=3)])-env.scene.env_origins[i].cpu().numpy()
        if not np.allclose(points.min(0),np.asarray(source['lower_xyz_m'])-origin0,atol=1e-5) or not np.allclose(points.max(0),np.asarray(source['upper_xyz_m'])-origin0,atol=1e-5):raise ValueError('Cloned slab moved surface')
        for old in source['disabled_shapes']:
            old=stage.GetPrimAtPath(old.replace('/env_0/',f'/env_{i}/'))
            if UsdPhysics.CollisionAPI(old).GetCollisionEnabledAttr().Get():raise ValueError('Overlapping old floor collider still enabled')
        rows.append(dict(env_id=i,path=path,lower_xyz_m=points.min(0).tolist(),upper_xyz_m=points.max(0).tolist()))
    return dict(all_clones_verified=True,active_floor_colliders=len(rows),disabled_floor_colliders=8*len(rows),
        added_rigid_bodies=0,all_contact_and_rest_offsets_verified=True,rows=rows)
