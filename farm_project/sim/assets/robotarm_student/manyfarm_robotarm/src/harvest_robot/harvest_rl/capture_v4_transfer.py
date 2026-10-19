"""Verified V3 weights/statistics transfer with explicit new optimizer/curriculum."""
import hashlib
import json
from pathlib import Path
from .teacher_asset_reference import sha


def verify_v3_transfer(checkpoint, saved, new_contract, root):
    old = json.loads((Path(checkpoint).parent/'domain_contract.json').read_text())
    digest = hashlib.sha256(json.dumps(old, sort_keys=True).encode()).hexdigest()
    if saved.get('infos', {}).get('domain_contract_sha256') != digest:
        raise ValueError('V3 checkpoint has no matching original contract')
    if old['domain']['name'] != 'teacher_60hz_capture_v3':
        raise ValueError('Only explicit V3 capture weights may transfer')
    for key in ('physics_profile', 'cached_asset_reference_sha256', 'source_run_sha256',
                'robot_usd_sha256', 'frozen_source_files', 'task'):
        if old[key] != new_contract[key]:
            raise ValueError(f'V3 transfer physical/task reference differs: {key}')
    allowed = {'name', 'status', 'confirmation_control', 'refinement', 'stages'}
    for key, value in old['domain'].items():
        if key not in allowed and new_contract['domain'].get(key) != value:
            raise ValueError(f'V3 transfer domain differs: {key}')
    old_stages, new_stages = old['domain']['stages'], new_contract['domain']['stages']
    if len(old_stages) != len(new_stages) or any(
            {k:v for k,v in a.items() if k!='earliest_iteration'} !=
            {k:v for k,v in b.items() if k!='earliest_iteration'}
            for a,b in zip(old_stages,new_stages)):
        raise ValueError('V3 transfer may change curriculum timing, not pose/distance limits')
    wrong = [name for name, value in old['domain_files'].items() if sha(Path(root)/name) != value]
    if wrong:
        raise ValueError(f'Original V3 source changed: {wrong}')
    return dict(source_checkpoint=str(Path(checkpoint).resolve()),
        source_checkpoint_sha256=sha(checkpoint), source_contract_sha256=digest,
        source_completed_iteration=saved['infos']['completed_iteration'],
        optimizer_transferred=False, curriculum_history_transferred=False,
        normalizer_buffers_transferred=True, progress_normalization_changed=False)
