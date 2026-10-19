"""Read the additive closed-floor proxy and verify its unchanged top height."""
from .component_scene_audit_v5 import scene_ccd_runtime


def inspect_scene(env):
    from .component_scene_audit_v5 import inspect_scene as original
    from pxr import Usd,UsdGeom,Gf
    import itertools
    import numpy as np
    result=original(env);stage=env.sim.stage
    proxy=stage.GetPrimAtPath('/World/envs/env_0/DepositFloorProxy')
    result['floor_proxy_requested']=bool(env.floor_proxy_requested)
    if proxy:
        transforms=UsdGeom.XformCache();points=[]
        for prim in Usd.PrimRange(proxy):
            if not prim.IsA(UsdGeom.Cube):continue
            size=float(UsdGeom.Cube(prim).GetSizeAttr().Get());t=transforms.GetLocalToWorldTransform(prim)
            points.extend(t.Transform(Gf.Vec3d(*p)) for p in itertools.product((-size/2,size/2),repeat=3))
        points=np.asarray(points)-env.scene.env_origins[0].cpu().numpy()
        if not points.size or abs(points[:,2].max()-.501)>1e-5:raise ValueError('Proxy moved actual floor top')
        result['floor_proxy']=dict(path=str(proxy.GetPath()),policy_lower_xyz_m=points.min(0).tolist(),
            policy_upper_xyz_m=points.max(0).tolist(),material=env.floor_proxy_material)
    elif env.floor_proxy_requested:raise ValueError('Requested floor proxy is absent')
    return result
