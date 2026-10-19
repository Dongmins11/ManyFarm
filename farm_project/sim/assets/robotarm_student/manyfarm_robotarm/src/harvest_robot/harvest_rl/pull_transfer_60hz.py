"""Verify an inference-only old pull actor on a newly trained contact grasp bank."""
import copy
import json
from pathlib import Path

from .followup_60hz import verify_source
from .grasp_handoff_60hz import contract_digest, validate_payload
from .pull_ready_60hz import make_contract as ready_contract
from .teacher_asset_reference import sha

CONTACT_FILES = ('scripts/train_teacher60_contact_grasp.py',
    'src/harvest_robot/harvest_rl/grasp_contact_margin_60hz.py',
    'src/harvest_robot/harvest_rl/teacher_contact_margin_env.py',
    'src/harvest_robot/harvest_rl/contact_points_60hz.py')


def check_source_compatibility(old, new):
    expected = copy.deepcopy(new['source_contract'])
    if 'contact_margin_refinement' not in expected:
        raise ValueError('Expected the explicit contact-grasp refinement contract')
    expected.pop('contact_margin_refinement')
    for name in CONTACT_FILES:
        if name not in expected['domain_files']:
            raise ValueError('Incomplete contact-grasp source contract')
        expected['domain_files'].pop(name)
    if (expected != old['source_contract']
            or old['physical_signature'] != new['physical_signature']
            or old['domain_stage'] != new['domain_stage']):
        raise ValueError('Pull transfer physics, observation, assets, domain or stage differs')


def verify_transfer(checkpoint, metadata):
    import torch
    checkpoint = Path(checkpoint).resolve()
    saved = torch.load(checkpoint, map_location='cpu', weights_only=True)
    parent = checkpoint.parent
    run = json.loads((parent/'run.json').read_text())
    contract = json.loads((parent/'followup_contract.json').read_text())
    bank = Path(run['start_bank'])
    if sha(bank) != run['start_bank_sha256']:
        raise ValueError('Original pull training bank changed')
    old = validate_payload(torch.load(bank, map_location='cpu', weights_only=True), 'train')['metadata']
    verify_source(old)
    verify_source(metadata)
    for source in (old, metadata):
        grasp = torch.load(source['source_checkpoint'], map_location='cpu', weights_only=True)
        if grasp.get('infos', {}).get('domain_contract_sha256') != source['source_contract_sha256']:
            raise ValueError('Grasp checkpoint and bank source contract differ')
    digest = contract_digest(contract)
    if (contract != ready_contract(old)
            or saved.get('infos', {}).get('followup_contract_sha256') != digest
            or run.get('followup_contract_sha256') != digest
            or saved['infos']['start_bank_sha256'] != sha(bank)):
        raise ValueError('Old pull checkpoint/controller does not match its original source')
    check_source_compatibility(old, metadata)
    return saved, dict(schema='teacher60_contact_grasp_pull_weights_inference_v1',
        learning=False, training_gate_eligible=False, comparison_only=True,
        checkpoint=str(checkpoint), checkpoint_sha256=sha(checkpoint),
        original_checkpoint_contract_sha256=digest,
        original_grasp_sha256=old['source_checkpoint_sha256'],
        original_grasp_contract_sha256=old['source_contract_sha256'],
        executed_grasp_sha256=metadata['source_checkpoint_sha256'],
        executed_grasp_contract_sha256=metadata['source_contract_sha256'],
        source_compatibility='Only grasp reward/source extension and weights differ; physics, observations, assets and domain are identical',
        optimizer_transferred=False, normalizer_buffers_transferred=True,
        success='Actual new-bank contact, valid detachment and retention; no full-harvest certificate')
