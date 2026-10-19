"""Finger-only material variant, excluding merged camera/motor colliders.

The earlier whole-link experiment is kept frozen for reproducibility.
This version also records all explicit inertia attributes (including capitals).
"""
from unittest.mock import patch
from . import jaw_surface_compare as original
from .jaw_surface_compare import SurfaceSpec,pad_prisms


def full_mass_attributes(prim):
    return {a.GetName():str(a.Get()) for a in prim.GetAttributes()
            if a.GetName().startswith('physics:') and any(x in a.GetName().lower()
                for x in ('mass','density','inertia','centerofmass','principalaxes'))}


def configure(env,spec):
    from pxr import UsdShade
    # Local, source-preserving instrumentation. No mass/inertia writes.
    with patch.object(original,'mass_attributes',full_mass_attributes):
        result=original.configure(env,spec)
    stage=env.sim.stage
    material=UsdShade.Material(stage.GetPrimAtPath('/World/GripMaterial'))
    for row in result['rows']:
        kept=[];restored=[]
        token=('wrist_roll_follower_so101_v1' if row['jaw']=='fixed'
               else 'moving_jaw_so101_v1')
        for path in row['colliders']:
            if token in path or '/SurfaceCompare/' in path:kept.append(path)
            else:
                binding=UsdShade.MaterialBindingAPI.Apply(stage.GetPrimAtPath(path))
                binding.Bind(material,bindingStrength=UsdShade.Tokens.strongerThanDescendants,materialPurpose='physics')
                restored.append(path)
        if not kept:raise ValueError('Original finger collision mesh missing')
        row.update(colliders=kept,baseline_material_colliders=restored)
    result.update(schema='teacher60_jaw_surface_compare_v2',material_scope='finger collision meshes and pads only',
                  camera_motor_colliders_unchanged=True,full_mass_inertia_attributes_recorded=True)
    return result


def audit(env):
    from pxr import UsdShade
    with patch.object(original,'mass_attributes',full_mass_attributes):
        result=original.audit(env)
    for row in env.surface_override['rows']:
        if not any('diagonalInertia' in k for k in row['mass_attributes_before']):raise ValueError('Explicit inertia missing')
        for path in row['baseline_material_colliders']:
            material,_=UsdShade.MaterialBindingAPI(env.sim.stage.GetPrimAtPath(path)).ComputeBoundMaterial('physics')
            if str(material.GetPath())!='/World/GripMaterial':raise ValueError('Camera/motor material changed')
    result.update(camera_motor_materials_unchanged=True,full_mass_inertia_attributes_unchanged=True,
                  material_scope='finger collision meshes and pads only')
    return result
