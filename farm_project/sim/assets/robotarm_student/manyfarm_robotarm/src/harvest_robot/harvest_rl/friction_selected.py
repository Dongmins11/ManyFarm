"""Separate inference selection; original material profile and PPO files preserved."""
import json
from .environment_version import load_profile,rooted,sha,ACTIVE

VERSION='teacher60_finger_friction_run_v2'
FOLLOWUP=dict(bridge_velocity_cap=.15,bridge_rate_deg_s=6.,transport_mode='progress_budget')


def load_selected(path=None):
    environment,environment_path=load_profile()
    if path is None:
        active=json.loads(ACTIVE.read_text());path=rooted(active['runtime_profile'])
        if sha(path)!=active['runtime_profile_sha256']:raise ValueError('Selected runtime profile hash differs')
    path=rooted(path).resolve();profile=json.loads(path.read_text())
    if (profile['version']!=VERSION or profile['environment_profile_sha256']!=sha(environment_path)
            or profile['followup']!=FOLLOWUP or profile['maximum_extra_transport_s']!=6.
            or profile['training_executed'] or profile['hardware_executed']):
        raise ValueError('Unexpected runtime/physical override')
    for name,digest in profile['pins'].items():
        if sha(rooted(name))!=digest:raise ValueError('Selected runtime source/evidence differs: '+name)
    return profile,path,environment


def bind_selected(output,profile,path,environment):
    from .environment_version import validate_settings
    output=rooted(output);run=json.loads((output/'run.json').read_text())
    result=json.loads((output/'analysis.json').read_text())
    validate_settings(run['task'],environment)
    if (not run['completed'] or not run['source_still_matches'] or not run['normalizers_unchanged']
            or not run['grasp_actor_unchanged'] or run['learning'] or run['hardware_executed']
            or run['followup']!=FOLLOWUP or not run['transport_progress_budget']['enabled']
            or run['transport_progress_budget']['maximum_extra_s']!=6.
            or run['environment_profile_sha256']!=profile['environment_profile_sha256']
            or run['evaluation_checkpoint_sha256']!=environment['policies']['native']['sha256']):
        raise ValueError('Actual selected runtime differs')
    return dict(schema='teacher60_selected_friction_application_v1',runtime_version=profile['version'],
        runtime_profile_sha256=sha(path),environment_profile_sha256=profile['environment_profile_sha256'],
        run_sha256=sha(output/'run.json'),actual_followup=run['followup'],
        actual_transport_progress_budget=run['transport_progress_budget'],count=result['count'],success=result['success'],
        learning=False,hardware_executed=False)
