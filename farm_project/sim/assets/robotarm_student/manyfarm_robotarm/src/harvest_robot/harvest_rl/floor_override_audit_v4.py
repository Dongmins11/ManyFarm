"""Geometry and speculative/rest offsets must match in all32 cloned scenes."""
from .floor_override_audit_v3 import audit_floor_clones as original


def audit_floor_clones(env):
    result=original(env)
    if env.floor_override['mode']=='buffered':
        from pxr import PhysxSchema
        for row in result['rows']:
            api=PhysxSchema.PhysxCollisionAPI(env.sim.stage.GetPrimAtPath(row['path']))
            contact,rest=api.GetContactOffsetAttr().Get(),api.GetRestOffsetAttr().Get()
            if contact is None or rest is None or abs(contact-.04)>1e-7 or abs(rest)>1e-7:
                raise ValueError('Actual cloned contact/rest offset differs')
            row.update(contact_offset_m=float(contact),rest_offset_m=float(rest))
        result['all_contact_and_rest_offsets_verified']=True
    return result
