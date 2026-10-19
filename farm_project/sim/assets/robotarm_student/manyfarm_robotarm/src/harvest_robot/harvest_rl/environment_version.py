"""Explicit versioned Teacher environment, independent of mutable old defaults.

TaskSettings keeps the baseline fruit material1.0. The actual finger-only
material override is separately part of this environment's physical contract.
This is never certified as same-physics PPO resume of a historical checkpoint.
"""
import copy
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[3]
ACTIVE=ROOT/'src/harvest_robot/config/teacher60_active_environment.json'
VERSION='teacher60_finger_friction_v1'
MUTABLE_TASK={'seed','workspace_split'}


def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024),b''):h.update(chunk)
    return h.hexdigest()


def rooted(path):
    p=Path(path)
    return p if p.is_absolute() else ROOT/p


def validate_profile(profile):
    if profile.get('schema')!='teacher60_environment_version_v1' or profile.get('version')!=VERSION:
        raise ValueError('Unsupported environment version; do not silently use old defaults')
    material=profile['contact_material']
    expected=dict(scope='finger_collision_meshes_only',jaw_static_friction=2.2,jaw_dynamic_friction=2.2,
        fruit_static_friction=1.,fruit_dynamic_friction=1.,combine_mode='average',
        effective_pair_friction=1.6,pad_mode='none',real_material_calibrated=False)
    if material!=expected:raise ValueError('v1 finger-only material contract changed')
    task=profile['base_task']
    fixed=dict(mass=.009,diameter=.07,length=.075,physics_dt=1/60,decimation=3,
        grip_friction=1.,dynamic_friction=1.,gripper_effort=.5,gripper_stiffness=8.,
        gripper_damping=.3,stem_response_version=6,attachment_version=4,
        contact_stiffness=0.,contact_damping=0.,contact_substeps=1)
    if any(task[k]!=v for k,v in fixed.items()):raise ValueError('v1 baseline physical settings changed')
    if profile['fruit_version']!=1 or profile['physics_hz']!=60 or profile['policy_hz']!=20:
        raise ValueError('Frequency/fruit version changed')
    if profile['controls']!=dict(bridge_s=2.,jaw_budget_deg=4.,retention_s=.5,stop_s=.3,deposit_s=.6):
        raise ValueError('Original physical confirmation/dwell changed')
    if profile.get('training_executed') or profile.get('hardware_executed'):
        raise ValueError('An environment definition is not a new trained/hardware result')
    return profile


def load_profile(path=None,verify_files=True):
    if path is None:
        active=json.loads(ACTIVE.read_text())
        path=rooted(active['profile'])
        if active['version']!=VERSION or sha(path)!=active['profile_sha256']:
            raise ValueError('Active environment reference differs')
    path=rooted(path).resolve();profile=validate_profile(json.loads(path.read_text()))
    if verify_files:
        for name,digest in profile['pins'].items():
            if not rooted(name).is_file() or sha(rooted(name))!=digest:
                raise ValueError('Environment source/policy/evidence pin differs: '+name)
    return profile,path


def validate_settings(settings,profile):
    validate_profile(profile)
    actual=json.loads(json.dumps(settings.as_dict() if hasattr(settings,'as_dict') else settings))
    expected=profile['base_task']
    if set(actual)!=set(expected):raise ValueError('Task field set changed')
    wrong=[k for k in expected if k not in MUTABLE_TASK and actual[k]!=expected[k]]
    if wrong:raise ValueError('Versioned task changed: '+', '.join(wrong))


def material_signature(profile):
    return copy.deepcopy(profile['contact_material'])


def transfer_contract(profile,path,parent_contract):
    """New physical contract for future weights-only training, not old resume."""
    return dict(schema='teacher60_environment_weights_transfer_v1',version=profile['version'],
        environment_profile=str(Path(path).resolve()),environment_profile_sha256=sha(path),
        base_task=copy.deepcopy(profile['base_task']),actual_contact_material=material_signature(profile),
        parent_training_contract_sha256=hashlib.sha256(json.dumps(parent_contract,sort_keys=True).encode()).hexdigest(),
        parent_checkpoint=profile['policies']['native'],optimizer_transferred=False,
        same_physics_resume=False,training_executed=False,
        note='Future trainer must bind this new physical contract to checkpoint/run; old CLI remains old-material reproduction')


def runtime_audit(env):
    from .jaw_surface_compare_v2 import audit
    result=audit(env);profile=env.environment_profile
    validate_settings(env.settings,profile)
    if abs(env.physics_dt-1/60)>1e-12 or abs(env.step_dt-.05)>1e-12:
        raise ValueError('Actual60/20Hz differs')
    if result['spec']['effective_friction']!=1.6 or result['pad_shapes']:
        raise ValueError('Material or original geometry differs')
    result.update(environment_version=profile['version'],environment_profile_sha256=sha(env.environment_profile_path),
        actual_physics_dt_s=env.physics_dt,actual_policy_dt_s=env.step_dt,
        actual_contact_material=material_signature(profile))
    return result
