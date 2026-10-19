"""Applied-action-aware PPO contract; immutable conservative parent preserved."""
from pathlib import Path
import json
import torch
from .native_contact_conservative_training import (
    verify_policy as verify_parent, FILES as PARENT_FILES, training_settings,
    configure, freeze_exploration, OPTIMIZATION,
)
from .native_control_mask import SPEC
from .grasp_handoff_60hz import contract_digest
from .teacher_asset_reference import sha

ROOT = Path(__file__).resolve().parents[3]
FILES = list(dict.fromkeys(PARENT_FILES + [
    'src/harvest_robot/harvest_rl/native_control_mask.py',
    'src/harvest_robot/harvest_rl/native_control_ppo.py',
    'src/harvest_robot/harvest_rl/teacher_native_contact_control_env.py',
    'src/harvest_robot/harvest_rl/native_contact_control_training.py',
    'scripts/train_teacher60_native_contact_control.py',
    'scripts/analyze_teacher60_native_contact_control.py',
    'scripts/eval_teacher60_native_contact_control_chain.py',
    'scripts/analyze_teacher60_native_contact_control_chain.py',
    'scripts/start_teacher60_native_contact_control.py',
]))


def make_contract(metadata, parent_checkpoint, warm_checkpoint):
    warm_checkpoint = Path(warm_checkpoint).resolve()
    warm, proof = verify_parent(metadata, parent_checkpoint, warm_checkpoint, 'trained')
    parent = proof['native_training_contract']
    contract = dict(parent)
    contract.update(schema='teacher60_native_contact_control_training_v1',
        parent_conservative_contract=parent,
        parent_conservative_contract_sha256=proof['native_training_contract_sha256'],
        actor_mask=SPEC,
        warm_start=dict(checkpoint=str(warm_checkpoint), checkpoint_sha256=sha(warm_checkpoint),
            run_sha256=sha(warm_checkpoint.parent/'run.json'), weights_and_normalizers=True,
            completed_iteration=warm['infos']['completed_iteration'], optimizer_transferred=False),
        files={**parent['files'], **{name: sha(ROOT/name) for name in FILES}},
        scope='Read-only control provenance changes actor sample eligibility only. Physical rewards, full native critic trajectory, GAE terminal, frozen HOME/bridge and conservative optimization unchanged.')
    return warm, contract


def verify_policy(metadata, parent_checkpoint, checkpoint, role='trained'):
    checkpoint = Path(checkpoint).resolve()
    if role != 'trained':
        raise ValueError('Applied-action-aware inference requires a completed trained checkpoint')
    run = json.loads((checkpoint.parent/'run.json').read_text())
    warm, expected = make_contract(metadata, parent_checkpoint, run['warm_checkpoint'])
    stored = json.loads((checkpoint.parent/'bridge_pull_contract.json').read_text())
    saved = torch.load(checkpoint, map_location='cpu', weights_only=True)
    digest = contract_digest(expected)
    if (not run.get('completed') or not run.get('source_still_matches')
            or not run.get('grasp_actor_unchanged') or not run.get('normalizers_unchanged')
            or stored != expected or run['contract_sha256'] != digest
            or saved['infos']['bridge_pull_contract_sha256'] != digest
            or not saved['infos'].get('actor_applied_mask') or saved['infos']['seed'] != run['seed']):
        raise ValueError('Incomplete/mismatched control-aware training contract')
    for name, h in expected['files'].items():
        if sha(ROOT/name) != h or sha(checkpoint.parent/'source_snapshot'/name) != h:
            raise ValueError('Control-aware source changed: '+name)
    for key, value in saved['model_state_dict'].items():
        if not torch.isfinite(value).all():
            raise ValueError('Nonfinite trained model')
        if 'normalizer' in key and not torch.equal(value, warm['model_state_dict'][key]):
            raise ValueError('Transferred normalization changed')
    if not torch.equal(saved['model_state_dict']['std'], warm['model_state_dict']['std']):
        raise ValueError('Fixed exploration changed')
    return saved, dict(role=role, checkpoint=str(checkpoint), checkpoint_sha256=sha(checkpoint),
        native_training_contract_sha256=digest, native_training_contract=expected,
        control='Preserved native pause/risk/retention and selected stopV4/unified floor',
        production_selection_changed=False, learning=False)
