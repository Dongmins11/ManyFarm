"""Finger-only scope and corrected grasp-confirmation readout audit."""
import json
from pathlib import Path
from analyze_teacher60_jaw_surface import analyze as original
from analyze_teacher60_transport_servo import trace_rows


def analyze(path):
    path=Path(path);result=original(path);rows=trace_rows(path)
    for metric in result['surface_metrics']:
        # This trace contains chain_bridge_confirmed, not has_grasped.
        metric['grasp_confirmed']=any(x['chain_bridge_confirmed'] for x in rows[metric['trial_id']])
    override=json.loads((path/'jaw_surface_override.json').read_text())
    for name in ['jaw_surface_audit.json','jaw_surface_audit_end.json']:
        record=json.loads((path/name).read_text())
        if not record.get('camera_motor_materials_unchanged') or not record.get('full_mass_inertia_attributes_unchanged'):
            raise ValueError('Missing finger-only material/full inertia audit')
    result.update(schema='teacher60_jaw_surface_comparison_audit_v2',
        material_scope=override['material_scope'],camera_motor_materials_unchanged=True,
        full_mass_inertia_attributes_unchanged=True)
    return result
