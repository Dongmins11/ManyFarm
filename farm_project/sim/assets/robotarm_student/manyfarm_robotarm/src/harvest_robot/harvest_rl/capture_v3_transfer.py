"""Explicit V2-to-V3 weight transfer; never an optimizer/resume shortcut."""
import hashlib
import json
from pathlib import Path
from .teacher_asset_reference import sha


def verify_v2_transfer(checkpoint, saved, new_contract, root):
    path = Path(checkpoint).parent/'domain_contract.json'
    old = json.loads(path.read_text())
    digest = hashlib.sha256(json.dumps(old,sort_keys=True).encode()).hexdigest()
    if saved.get('infos', {}).get('domain_contract_sha256') != digest:
        raise ValueError('V2 checkpoint has no matching original domain contract')
    if old['domain']['name'] != 'teacher_60hz_capture_v2':
        raise ValueError('Only the verified V2 capture weights may transfer')
    if saved['infos']['domain_state']['stage'] != 0:
        raise ValueError('This transfer is validated only for the close stage 0')
    for key in ('physics_profile','cached_asset_reference_sha256','source_run_sha256',
                'robot_usd_sha256','frozen_source_files','task'):
        if old[key] != new_contract[key]:
            raise ValueError(f'V2 transfer physical/task reference differs: {key}')
    for key,value in old['domain'].items():
        if key not in ('name','status') and new_contract['domain'].get(key) != value:
            raise ValueError(f'V2 transfer domain differs: {key}')
    wrong=[name for name,value in old['domain_files'].items()
           if sha(Path(root)/name) != value]
    if wrong: raise ValueError(f'Original V2 source changed: {wrong}')
    return dict(source_checkpoint=str(Path(checkpoint).resolve()),
        source_checkpoint_sha256=sha(checkpoint), source_contract_sha256=digest,
        source_completed_iteration=saved['infos']['completed_iteration'],
        optimizer_transferred=False, curriculum_history_transferred=False,
        normalizer_buffers_transferred=True, progress_normalization_changed=True)
