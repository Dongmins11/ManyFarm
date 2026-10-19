"""Read the explicit candidate; never redirect the adopted Teacher selection."""
import json
from dataclasses import asdict
from .environment_version import ROOT,sha,rooted
from .hook_connector import HookSpec

PATH=ROOT/'src/harvest_robot/config/teacher60_connector_hook_v2.json'


def load_hook_profile(path=PATH):
    path=rooted(path);profile=json.loads(path.read_text())
    if (profile.get('schema')!='teacher60_hook_candidate_v2'
            or profile.get('version')!='teacher60_connector_hook_v2'
            or profile['active_environment_changed'] or profile['training_executed']
            or profile['hardware_executed']):
        raise ValueError('Use the separate non-active hook candidate')
    spec=HookSpec(**{**profile['hook'],
        'pivot_offset_direction':tuple(profile['hook']['pivot_offset_direction'])}).validate()
    if (spec.final_extension_m!=.01 or spec.damping_N_s_m!=4.2
            or spec.bending_drag_N_s_m!=.1 or spec.rotation_damping_Nm_s_rad!=.008):
        raise ValueError('Candidate differs from selected physical comparison')
    evidence=profile['mechanical_evidence'];result_path=rooted(evidence['path'])
    if sha(result_path)!=evidence['sha256']:raise ValueError('Mechanical evidence changed')
    result=json.loads(result_path.read_text())
    if not result['candidates']['10']['passed'] or result['learning'] or result['hardware_executed']:
        raise ValueError('Mechanical candidate did not pass isolated checks')
    actual=json.loads(json.dumps(asdict(spec)))
    if actual not in result['specs']:raise ValueError('Actual mechanical candidate spec differs')
    return profile,path,spec
