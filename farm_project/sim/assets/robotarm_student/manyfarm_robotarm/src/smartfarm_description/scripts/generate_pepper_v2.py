"""Generate separate v2 visible/collision USD; never launch Isaac/GPU or overwrite v1."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[3]


def usd_imports():
    # Use installed USD libraries offline: no SimulationApp alongside live capture.
    try:import pxr
    except ImportError:
        cache=Path(sys.prefix)/'lib/python3.11/site-packages/isaacsim/extscache'
        found=list(cache.glob('omni.usd.libs-*'))
        if len(found)!=1:raise RuntimeError('Run with HARVEST_PY; standalone USD library unavailable')
        libs=found[0];kit=cache.parent/'kit'
        if os.environ.get('PEPPER_V2_USD_BOOTSTRAPPED')!='1':
            env=os.environ.copy();env['PEPPER_V2_USD_BOOTSTRAPPED']='1'
            env['LD_LIBRARY_PATH']=str(libs/'bin')+':'+str(kit)+':'+env.get('LD_LIBRARY_PATH','')
            env['PYTHONPATH']=str(libs)+os.pathsep+env.get('PYTHONPATH','')
            os.execve(sys.executable,[sys.executable,*sys.argv],env)
        sys.path.insert(0,str(libs))
    from pxr import Gf,Sdf,Usd,UsdGeom,UsdPhysics
    return Gf,Sdf,Usd,UsdGeom,UsdPhysics


def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def verify(out):
    """Read back composed meshes, including referenced visual transforms."""
    import numpy as np
    Gf,Sdf,Usd,UsdGeom,UsdPhysics=usd_imports()
    manifest=json.loads((out/'manifest.json').read_text());result={}
    for color,entry in manifest['assets'].items():
        path=out/entry['file']
        if digest(path)!=entry['sha256']:raise ValueError(f'{color}: asset hash mismatch')
        stage=Usd.Stage.Open(str(path));cache=UsdGeom.XformCache();visual=[]
        for prim in stage.Traverse():
            if prim.IsA(UsdGeom.Mesh) and str(prim.GetPath()).startswith('/Pepper/Visual/'):
                transform=cache.GetLocalToWorldTransform(prim)
                visual.extend(tuple(transform.Transform(Gf.Vec3d(*map(float,p)))) for p in UsdGeom.Mesh(prim).GetPointsAttr().Get())
        collision=UsdGeom.Mesh(stage.GetPrimAtPath('/Pepper/Collision'))
        points=np.asarray(collision.GetPointsAttr().Get(),dtype=float);visible=np.asarray(visual,dtype=float)
        if visible.shape!=points.shape or not np.allclose(visible,points,atol=1e-8,rtol=0):
            raise ValueError(f'{color}: composed visual/collision mismatch')
        mass=float(UsdPhysics.MassAPI(stage.GetDefaultPrim()).GetMassAttr().Get())
        if abs(mass-manifest['profile']['mass_kg'])>1e-8:raise ValueError(f'{color}: mass mismatch')
        result[color]={'visual_collision_max_error_m':float(np.max(np.abs(visible-points))),
                       'mass_kg':mass,'whole_extent_m':np.ptp(points,axis=0).tolist(),
                       'sha256':entry['sha256']}
    for name,sha in manifest['source_files'].items():
        path=Path(name) if Path(name).is_absolute() else ROOT/name
        if digest(path)!=sha:raise ValueError(f'Source changed: {name}')
    print('PEPPER_V2_VERIFIED',json.dumps(result),flush=True)
    return result


def generate(profile_path,out):
    import numpy as np
    from pepper_model_v2_geometry import fit,transform_point
    Gf,Sdf,Usd,UsdGeom,UsdPhysics=usd_imports()
    profile=json.loads(profile_path.read_text());source_dir=ROOT/'src/Pepper_RL_Demo/assets'
    source_meta=json.loads((source_dir/'manifest.json').read_text());out.mkdir(parents=True,exist_ok=False)
    manifest=dict(schema='pepper_geometry_v2',profile=profile,profile_sha256=digest(profile_path),assets={},source_files={},
                  default_environment_modified=False,policy_evaluated=False)
    for color in ('Red','Yellow','Green'):
        source_path=source_dir/f'Pepper_{color}.usdc';source=Usd.Stage.Open(str(source_path));cache=UsdGeom.XformCache()
        parts=[];all_points=[]
        for prim in source.Traverse():
            if prim.IsA(UsdGeom.Mesh):
                mesh=UsdGeom.Mesh(prim);transform=cache.GetLocalToWorldTransform(prim)
                points=np.array([tuple(transform.Transform(Gf.Vec3d(*map(float,p)))) for p in mesh.GetPointsAttr().Get()])
                parts.append((prim,mesh,transform,len(all_points),len(points)));all_points.extend(points)
        old=np.asarray(all_points);new,body,low,info=fit(old,profile)
        path=out/f'Pepper_{color}_v2.usda';stage=Usd.Stage.CreateNew(str(path));root=UsdGeom.Xform.Define(stage,'/Pepper').GetPrim()
        stage.SetDefaultPrim(root);UsdGeom.SetStageUpAxis(stage,'Z');UsdGeom.SetStageMetersPerUnit(stage,1.)
        UsdPhysics.RigidBodyAPI.Apply(root);mass=UsdPhysics.MassAPI.Apply(root);mass.CreateMassAttr(profile['mass_kg'])
        mass.CreateCenterOfMassAttr(Gf.Vec3f(*profile['grasp_center_local_m']))
        # Standard typed property is resolved by PhysxSchema when Isaac loads it.
        root.SetMetadata('apiSchemas',Sdf.TokenListOp.CreateExplicit(['PhysicsRigidBodyAPI','PhysicsMassAPI','PhysxRigidBodyAPI']))
        root.CreateAttribute('physxRigidBody:enableCCD',Sdf.ValueTypeNames.Bool).Set(True)
        root.SetCustomDataByKey('fruit_geometry_version',2)
        visual=UsdGeom.Xform.Define(stage,'/Pepper/Visual');visual.GetPrim().GetReferences().AddReference(os.path.relpath(source_path,out))
        indices=[];counts=[]
        for prim,mesh,transform,start,n in parts:
            rel=str(prim.GetPath()).removeprefix(str(source.GetDefaultPrim().GetPath()))
            target=UsdGeom.Mesh(stage.GetPrimAtPath('/Pepper/Visual'+rel));inv=transform.GetInverse()
            target.GetPointsAttr().Set([Gf.Vec3f(*inv.Transform(Gf.Vec3d(*p))) for p in new[start:start+n]])
            local=np.asarray(target.GetPointsAttr().Get())
            target.GetExtentAttr().Set([Gf.Vec3f(*map(float,local.min(0))),Gf.Vec3f(*map(float,local.max(0)))])
            ix=np.array(mesh.GetFaceVertexIndicesAttr().Get());ct=list(mesh.GetFaceVertexCountsAttr().Get());normals=np.zeros((n,3));k=0
            local=np.asarray(target.GetPointsAttr().Get())
            for count in ct:
                face=ix[k:k+count];k+=count
                for j in range(1,count-1):
                    tri=face[[0,j,j+1]];normal=np.cross(local[tri[1]]-local[tri[0]],local[tri[2]]-local[tri[0]])
                    np.add.at(normals,tri,normal)
            normals/=np.maximum(np.linalg.norm(normals,axis=1,keepdims=True),1e-12)
            target.GetNormalsAttr().Set([Gf.Vec3f(*p) for p in normals]);target.SetNormalsInterpolation('vertex')
            indices.extend((ix+start).tolist());counts.extend(ct)
        collision=UsdGeom.Mesh.Define(stage,'/Pepper/Collision');collision.CreatePointsAttr([Gf.Vec3f(*p) for p in new])
        collision.CreateFaceVertexCountsAttr(counts);collision.CreateFaceVertexIndicesAttr(indices);collision.CreateVisibilityAttr('invisible')
        UsdPhysics.CollisionAPI.Apply(collision.GetPrim());UsdPhysics.MeshCollisionAPI.Apply(collision.GetPrim()).CreateApproximationAttr('convexDecomposition')
        stage.GetRootLayer().Save()
        tip=transform_point(source_meta['Pepper_'+color]['attachment'],profile,info)
        entry=dict(file=path.name,sha256=digest(path),source_sha256=digest(source_path),attachment_local_m=tip.tolist(),fit=info,
                   actual_body_max_width_m=float(np.ptp(new[body],axis=0)[:2].max()),actual_body_height_m=float(np.ptp(new[body],axis=0)[2]),
                   actual_lower_body_max_width_m=float(np.ptp(new[low],axis=0)[:2].max()))
        for key,wanted in (('actual_body_max_width_m',profile['body_max_width_m']),('actual_body_height_m',profile['body_height_m']),('actual_lower_body_max_width_m',profile['lower_body_max_width_m'])):
            if abs(entry[key]-wanted)>1e-6:raise ValueError(f'Dimension mismatch: {color}/{key}')
        opened=Usd.Stage.Open(str(path));authored=np.array(UsdGeom.Mesh(opened.GetPrimAtPath('/Pepper/Collision')).GetPointsAttr().Get())
        if not np.allclose(authored,new,atol=1e-8):raise ValueError('Collision export differs from visual geometry')
        if abs(float(UsdPhysics.MassAPI(opened.GetDefaultPrim()).GetMassAttr().Get())-profile['mass_kg'])>1e-8:raise ValueError('Mass mismatch')
        manifest['assets'][color]=entry;manifest['source_files'][str(source_path.relative_to(ROOT))]=digest(source_path)
        if color=='Red':
            np.savez(out/'geometry_comparison.npz',source_points_m=old,current_rl_points_m=old*np.array([.070/.09052825719118118]*2+[.075/.11704932153224945]),
                     v2_points_m=new,body_mask=body,lower_mask=low,indices=np.asarray(indices),counts=np.asarray(counts))
    for p in profile['reference_images']:
        if Path(p).exists():manifest['source_files'][p]=digest(p)
    (out/'manifest.json').write_text(json.dumps(manifest,indent=2,ensure_ascii=False));print('PEPPER_V2_GENERATED',out,flush=True)
    for color,entry in manifest['assets'].items():print(color,'body width/height/lower width:',entry['actual_body_max_width_m'],entry['actual_body_height_m'],entry['actual_lower_body_max_width_m'],flush=True)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--profile',type=Path,default=ROOT/'src/smartfarm_description/config/pepper_model_v2.json')
    p.add_argument('--output',type=Path,default=ROOT/'src/smartfarm_description/meshes/pepper/v2')
    p.add_argument('--verify',action='store_true',help='Read-only audit of existing assets and source hashes')
    a=p.parse_args()
    if a.verify:verify(a.output)
    else:generate(a.profile,a.output);verify(a.output)


if __name__=='__main__':main()
