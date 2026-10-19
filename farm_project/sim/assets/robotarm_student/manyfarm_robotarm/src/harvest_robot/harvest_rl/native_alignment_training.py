"""Explicit new-height/reward transfer from the latest continuous pull final."""
from dataclasses import asdict
import json
from pathlib import Path
import torch
from .bridge_pull_training import make_contract as parent_contract, training_settings as parent_settings, FILES as PARENT_FILES
from .native_pull_alignment import SPEC
from .placement_height_v2 import height_settings
from .grasp_handoff_60hz import contract_digest, physical_signature
from .teacher_asset_reference import sha
from .bridge_pull_risk import RiskPullSpec

ROOT = Path(__file__).resolve().parents[3]
FILES = list(dict.fromkeys(PARENT_FILES+[
    'scripts/train_teacher60_native_alignment.py',
    'scripts/train_teacher60_native_alignment.sh',
    'scripts/analyze_teacher60_native_alignment.py',
    'src/harvest_robot/harvest_rl/native_pull_alignment.py',
    'src/harvest_robot/harvest_rl/native_alignment_training.py',
    'src/harvest_robot/harvest_rl/teacher_native_alignment_env.py',
    'src/harvest_robot/harvest_rl/teacher_bridge_pull_guarded_env.py',
    'src/harvest_robot/harvest_rl/teacher_bridge_pull_risk_env.py',
    'src/harvest_robot/harvest_rl/bridge_pull_risk.py',
    'src/harvest_robot/harvest_rl/bridge_pull_path.py',
    'src/harvest_robot/harvest_rl/matched_pull_60hz.py',
    'src/harvest_robot/harvest_rl/placement_height_v2.py',
    'src/harvest_robot/config/teacher60_placement_height_v2.json']))


def training_settings(metadata, seed):
    return height_settings(parent_settings(metadata, seed))[0]


def make_contract(metadata, pull_checkpoint, warm_checkpoint):
    _, parent = parent_contract(metadata, pull_checkpoint)
    warm_checkpoint = Path(warm_checkpoint).resolve()
    warm = torch.load(warm_checkpoint, map_location='cpu', weights_only=True)
    prior = json.loads((warm_checkpoint.parent/'run.json').read_text())
    prior_contract = json.loads((warm_checkpoint.parent/'bridge_pull_contract.json').read_text())
    digest = contract_digest(parent)
    if (warm.get('infos', {}).get('bridge_pull_contract_sha256') != digest
            or contract_digest(prior_contract) != digest or prior.get('contract_sha256') != digest
            or prior.get('mode') != 'train' or not prior.get('completed')
            or not prior.get('source_still_matches')):
        raise ValueError('Warm start must be the completed original continuous bridge-pull model')
    for name, h in parent['files'].items():
        if sha(ROOT/name) != h or sha(warm_checkpoint.parent/'source_snapshot'/name) != h:
            raise ValueError('Warm-start source changed: '+name)
    settings, placement = height_settings(parent_settings(metadata, 42))
    return warm, dict(schema='teacher60_native_alignment_training_v1', parent=parent,
        parent_contract_sha256=digest, spec=parent['spec'], alignment=asdict(SPEC),
        source_grasp_sha256=metadata['source_checkpoint_sha256'],
        source_grasp_contract_sha256=metadata['source_contract_sha256'],
        pull_transfer=parent['pull_transfer'],
        warm_start=dict(checkpoint=str(warm_checkpoint), checkpoint_sha256=sha(warm_checkpoint),
            run_sha256=sha(warm_checkpoint.parent/'run.json'), original_contract_sha256=digest,
            weights_and_normalizers=True, optimizer_transferred=False),
        placement_height_v2=placement, physical_signature=physical_signature(settings.as_dict()),
        domain=metadata['source_run']['domain'], source_domain_files=metadata['source_contract']['domain_files'],
        files={name:sha(ROOT/name) for name in FILES}, split='train', domain_stage=3,
        controller=dict(risk=asdict(RiskPullSpec(axial=True, hold_after_detach=True)),
            contact_loss='Pause previous arm targets; original finite timeout',
            duplicate_preparation=False, original_pressure=True),
        optimizer_transferred=False, grasp_actor_learns=False, bank_restore=False,
        original_success_failure_gates=True, production_selection_changed=False,
        scope='Frozen HOME/grasp, actual2s bridge, learned pull, valid detachment and0.5s retention. No box deposit training.')
