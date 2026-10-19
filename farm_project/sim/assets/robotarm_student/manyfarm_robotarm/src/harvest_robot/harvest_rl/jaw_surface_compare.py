"""Explicit runtime-only jaw material/convex-pad experiment, never a weld.

Pads are rigid geometric surrogates, NOT calibrated silicone deformation.
Two separate convex faces preserve the shallow recess: a single convex hull
would fill it. Existing jaw shapes, bodies, mass/inertia, motor and fruit stay.
"""
from dataclasses import dataclass, asdict
import math
import numpy as np


@dataclass(frozen=True)
class SurfaceSpec:
    effective_friction: float = 1.
    pad_mode: str = 'none'
    thickness_m: float = .001
    recess_m: float = .002
    half_width_m: float = .012

    def validate(self):
        if (not math.isfinite(self.effective_friction)
                or not 1 <= self.effective_friction <= 1.6
                or self.pad_mode not in ('none', 'flat', 'trough')
                or (self.thickness_m, self.recess_m, self.half_width_m) != (.001, .002, .012)):
            raise ValueError('Explicit mu1..1.6, none/flat/trough, fixed1mm/2mm/24mm geometry')
        return self

    @property
    def jaw_friction(self):
        # Fruit stays1.0 and both materials use average combination.
        return 2*self.effective_friction-1.


def pad_prisms(spec, jaw):
    """Vertices in the original body link frame (metres), attached to same body.

    Surface positions follow original STL inner-side extents. Rigid approximate
    mounting surfaces taper along the fingers; no palm end stop or hook is added.
    Flat has the SAME thickness/span/mounting as trough, to isolate recess effect.
    """
    spec.validate()
    if jaw not in ('fixed', 'moving'):
        raise ValueError('Unknown jaw')
    if spec.pad_mode == 'none':
        return []
    w=spec.half_width_m
    # axis along finger, transverse axis, transverse centre, outward sign,
    # longitudinal bounds, original inner surface x at the two ends.
    axis, transverse, center, sign, ends, surface = (
        (2, 1, -.000218214, 1., (-.102, -.072), (-.0079, -.0116))
        if jaw == 'fixed' else
        (1, 2, .0189, -1., (-.075, -.030), (-.0123, -.0083)))
    result=[]
    for index,(left,right) in enumerate(((-w,0.),(0.,w))):
        vertices=[]
        for side in (0,1):
            for j,s in enumerate(ends):
                for t in (left,right):
                    p=np.zeros(3);p[axis]=s;p[transverse]=center+t
                    height=spec.thickness_m+(spec.recess_m*abs(t)/w if spec.pad_mode=='trough' else 0.)
                    p[0]=surface[j]+sign*(height if side else -.0003)
                    vertices.append(p)
        result.append(dict(name=f'{jaw}_{index}',vertices_m=np.asarray(vertices),
            # Faces need consistent closed topology, convexHull cooking below.
            faces=[[0,1,3,2],[4,6,7,5],[0,4,5,1],[2,3,7,6],[0,2,6,4],[1,5,7,3]]))
    return result


def mass_attributes(prim):
    return {a.GetName():str(a.Get()) for a in prim.GetAttributes()
            if a.GetName().startswith('physics:') and any(x in a.GetName()
                for x in ('mass','density','inertia','centerOfMass','principalAxes'))}


def configure(env, spec):
    """Author before the first PhysX reset; edit each cloned jaw explicitly."""
    from pxr import Usd,UsdGeom,UsdPhysics,UsdShade,PhysxSchema,Gf,Vt
    from .assets import bind_verified_material
    spec.validate();stage=env.sim.stage
    material_path='/World/JawSurfaceCompareMaterial'
    material=UsdShade.Material.Define(stage,material_path)
    p=material.GetPrim();api=UsdPhysics.MaterialAPI.Apply(p)
    api.CreateStaticFrictionAttr().Set(spec.jaw_friction)
    api.CreateDynamicFrictionAttr().Set(spec.jaw_friction)
    api.CreateRestitutionAttr().Set(env.settings.restitution)
    phys=PhysxSchema.PhysxMaterialAPI.Apply(p)
    phys.CreateFrictionCombineModeAttr().Set('average')
    phys.CreateRestitutionCombineModeAttr().Set('average')
    rows=[]
    for i in range(env.num_envs):
        for jaw,pattern in [('fixed',env.fixed_path),('moving',env.moving_path)]:
            path=pattern.replace('env_.*',f'env_{i}')
            body=stage.GetPrimAtPath(path)
            if not body or not body.HasAPI(UsdPhysics.RigidBodyAPI):
                raise ValueError('Pad must share existing jaw rigid body: '+path)
            before=mass_attributes(body)
            for prim in list(Usd.PrimRange(body)):
                if prim.IsInstance():prim.SetInstanceable(False)
            pads=[]
            for part in pad_prisms(spec,jaw):
                mesh=UsdGeom.Mesh.Define(stage,path+'/SurfaceCompare/'+part['name'])
                mesh.CreatePointsAttr(Vt.Vec3fArray([Gf.Vec3f(*map(float,x)) for x in part['vertices_m']]))
                mesh.CreateFaceVertexCountsAttr([4]*6)
                mesh.CreateFaceVertexIndicesAttr([v for face in part['faces'] for v in face])
                mesh.CreateSubdivisionSchemeAttr('none');mesh.CreateDoubleSidedAttr(True)
                mesh.CreateDisplayColorAttr([(.35,.38,.40)])
                mesh.CreateExtentAttr([Gf.Vec3f(*map(float,part['vertices_m'].min(0))),
                                       Gf.Vec3f(*map(float,part['vertices_m'].max(0)))])
                prim=mesh.GetPrim()
                UsdPhysics.CollisionAPI.Apply(prim).CreateCollisionEnabledAttr(True)
                UsdPhysics.MeshCollisionAPI.Apply(prim).CreateApproximationAttr('convexHull')
                collision=PhysxSchema.PhysxCollisionAPI.Apply(prim)
                collision.CreateContactOffsetAttr(.001);collision.CreateRestOffsetAttr(0.)
                if prim.HasAPI(UsdPhysics.RigidBodyAPI):raise ValueError('No added rigid body')
                pads.append(str(prim.GetPath()))
            colliders=bind_verified_material(stage,path,material_path)
            if before!=mass_attributes(body):raise ValueError('Existing mass/inertia attributes changed')
            rows.append(dict(env_id=i,jaw=jaw,body=path,pads=pads,colliders=colliders,
                mass_attributes_before=before,mass_attributes_after=mass_attributes(body)))
    return dict(schema='teacher60_jaw_surface_compare_v1',spec=asdict(spec),
        jaw_static_dynamic_friction=spec.jaw_friction,fruit_static_dynamic_friction=1.,
        effective_pair_friction=spec.effective_friction,combine_mode='average',
        material=material_path,added_rigid_bodies=0,original_assets_modified=False,
        silicone_compliance_modelled=False,rows=rows)


def audit(env):
    from pxr import UsdPhysics,UsdShade,UsdGeom
    stage=env.sim.stage;record=env.surface_override;spec=env.surface_spec
    for row in record['rows']:
        body=stage.GetPrimAtPath(row['body'])
        if mass_attributes(body)!=row['mass_attributes_before']:raise ValueError('Mass/inertia drift')
        for path in row['colliders']:
            prim=stage.GetPrimAtPath(path)
            material,_=UsdShade.MaterialBindingAPI(prim).ComputeBoundMaterial('physics')
            if str(material.GetPath())!=record['material']:raise ValueError('Jaw binding differs')
            api=UsdPhysics.MaterialAPI(material.GetPrim())
            if abs(api.GetStaticFrictionAttr().Get()-spec.jaw_friction)>1e-6 or abs(api.GetDynamicFrictionAttr().Get()-spec.jaw_friction)>1e-6:
                raise ValueError('Jaw friction differs')
        for path in row['pads']:
            prim=stage.GetPrimAtPath(path)
            if prim.HasAPI(UsdPhysics.RigidBodyAPI) or not UsdPhysics.CollisionAPI(prim).GetCollisionEnabledAttr().Get():raise ValueError('Invalid pad body/collision')
            name=str(prim.GetName());expected=next(x for x in pad_prisms(spec,row['jaw']) if x['name']==name)
            if not np.allclose(np.asarray(UsdGeom.Mesh(prim).GetPointsAttr().Get()),expected['vertices_m'],atol=1e-8):raise ValueError('Cloned pad geometry differs')
    for i in range(env.num_envs):
        for k in range(env.settings.num_fruits):
            body=stage.GetPrimAtPath(f'/World/envs/env_{i}/Fruit_{k}')
            from pxr import Usd
            for prim in Usd.PrimRange(body):
                if not prim.HasAPI(UsdPhysics.CollisionAPI):continue
                material,_=UsdShade.MaterialBindingAPI(prim).ComputeBoundMaterial('physics')
                if str(material.GetPath())!='/World/GripMaterial':raise ValueError('Fruit material changed')
                api=UsdPhysics.MaterialAPI(material.GetPrim())
                if abs(api.GetStaticFrictionAttr().Get()-1)>1e-6 or abs(api.GetDynamicFrictionAttr().Get()-1)>1e-6:raise ValueError('Fruit friction changed')
    return dict(all_clones_verified=True,num_envs=env.num_envs,pad_shapes=sum(len(r['pads']) for r in record['rows']),
        jaw_material_verified=True,fruit_material_unchanged=True,mass_inertia_attributes_unchanged=True,
        added_rigid_bodies=0,original_assets_modified=False,spec=asdict(spec))
