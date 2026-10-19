"""Versioned conservative optimization experiment on unchanged contact physics.

The transfer is from a completed v2 checkpoint selected on validation only.
No validation scene, contact label, or test score enters the training sampler.
"""
from pathlib import Path
import json
import torch
from .native_contact_v2_training import (
    verify_policy as verify_parent, FILES as PARENT_FILES, training_settings,
)
from .grasp_handoff_60hz import contract_digest
from .teacher_asset_reference import sha

ROOT = Path(__file__).resolve().parents[3]
OPTIMIZATION = dict(learning_rate=1e-5, schedule='fixed', entropy_coef=0.,
    clip_param=.1, arm_exploration_std=.02, learned_std=False,
    optimizer_transferred=False)
FILES = list(dict.fromkeys(PARENT_FILES + [
    'src/harvest_robot/harvest_rl/native_contact_conservative_training.py',
    'scripts/train_teacher60_native_contact_conservative.py',
    'scripts/analyze_teacher60_native_contact_conservative.py',
    'scripts/start_teacher60_native_contact_conservative.sh',
]))


def configure(config):
    """Keep the original network, masked loss, and return estimator."""
    config['algorithm'].update({k: OPTIMIZATION[k] for k in
        ('learning_rate', 'schedule', 'entropy_coef', 'clip_param')})
    return config


def freeze_exploration(policy):
    # G has no learner-controlled action. Keep its transferred std unchanged.
    with torch.no_grad():
        policy.std[:5].fill_(OPTIMIZATION['arm_exploration_std'])
    policy.std.requires_grad_(False)


def make_contract(metadata, parent_checkpoint, warm_checkpoint):
    warm_checkpoint = Path(warm_checkpoint).resolve()
    warm, proof = verify_parent(metadata, parent_checkpoint, warm_checkpoint, 'trained')
    parent = proof['native_training_contract']
    contract = dict(parent)
    contract.update(schema='teacher60_native_contact_conservative_training_v1',
        parent_contact_contract=parent,
        parent_contact_contract_sha256=proof['native_training_contract_sha256'],
        optimization=OPTIMIZATION,
        warm_start=dict(checkpoint=str(warm_checkpoint), checkpoint_sha256=sha(warm_checkpoint),
            run_sha256=sha(warm_checkpoint.parent/'run.json'), weights_and_normalizers=True,
            completed_iteration=warm['infos']['completed_iteration'], optimizer_transferred=False),
        files={**parent['files'], **{name: sha(ROOT/name) for name in FILES}},
        scope='Conservative native arm5 optimization only; unchanged v2 reward/sampler, physical gates, frozen HOME/bridge. Not evidence of physical sim-to-real calibration.')
    return warm, contract


def verify_policy(metadata, parent_checkpoint, checkpoint, role='trained'):
    checkpoint = Path(checkpoint).resolve()
    if role != 'trained':
        raise ValueError('Conservative inference requires a completed trained checkpoint')
    run = json.loads((checkpoint.parent/'run.json').read_text())
    warm, expected = make_contract(metadata, parent_checkpoint, run['warm_checkpoint'])
    stored = json.loads((checkpoint.parent/'bridge_pull_contract.json').read_text())
    saved = torch.load(checkpoint, map_location='cpu', weights_only=True)
    digest = contract_digest(expected)
    if (not run.get('completed') or not run.get('source_still_matches')
            or not run.get('grasp_actor_unchanged') or not run.get('normalizers_unchanged')
            or stored != expected or run['contract_sha256'] != digest
            or saved['infos']['bridge_pull_contract_sha256'] != digest
            or saved['infos']['seed'] != run['seed']):
        raise ValueError('Incomplete/mismatched conservative training contract')
    for name, h in expected['files'].items():
        if sha(ROOT/name) != h or sha(checkpoint.parent/'source_snapshot'/name) != h:
            raise ValueError('Conservative source changed: '+name)
    for key, value in saved['model_state_dict'].items():
        if not torch.isfinite(value).all():
            raise ValueError('Nonfinite trained model')
        if 'normalizer' in key and not torch.equal(value, warm['model_state_dict'][key]):
            raise ValueError('Transferred normalization changed')
    if not torch.allclose(saved['model_state_dict']['std'][:5], torch.full((5,), .02), atol=1e-8, rtol=0):
        raise ValueError('Fixed arm exploration changed')
    return saved, dict(role=role, checkpoint=str(checkpoint), checkpoint_sha256=sha(checkpoint),
        native_training_contract_sha256=digest, native_training_contract=expected,
        control='Preserved native pause/risk/retention and selected stopV4/unified floor',
        production_selection_changed=False, learning=False)
