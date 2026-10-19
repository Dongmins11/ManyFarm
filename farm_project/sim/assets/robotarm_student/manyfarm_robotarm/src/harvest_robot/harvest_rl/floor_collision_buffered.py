"""Discrete60Hz floor: thick hull plus speculative contact before penetration."""
from .floor_collision_v4 import configure_floor as original


def configure_floor(stage,mode):
    result=original(stage,'deep-hull' if mode=='buffered' else mode)
    if mode!='buffered':return result
    from pxr import PhysxSchema
    for edit in result['edits']:
        prim=stage.GetPrimAtPath(edit['path'])
        api=PhysxSchema.PhysxCollisionAPI.Apply(prim)
        edit['original_contact_offset_m']=api.GetContactOffsetAttr().Get()
        edit['original_rest_offset_m']=api.GetRestOffsetAttr().Get()
        api.CreateContactOffsetAttr().Set(.04)
        api.CreateRestOffsetAttr().Set(0.)
    result.update(mode='buffered',contact_offset_m=.04,rest_offset_m=0.,
        note='40mm speculative contact band for~36mm per60Hz fall step. Rest surface stays original; no external support force/velocity override')
    return result
