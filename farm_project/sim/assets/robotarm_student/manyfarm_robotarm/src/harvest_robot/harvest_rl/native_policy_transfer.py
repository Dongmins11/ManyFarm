"""Verify a new native-pull model explicitly before unchanged chain inference."""
import json
from pathlib import Path
import torch
from .native_alignment_training import make_contract
from .grasp_handoff_60hz import contract_digest
from .teacher_asset_reference import sha

ROOT=Path(__file__).resolve().parents[3]
WARM=ROOT/'runs/harvest_rl/teacher60_bridge_pull_20261011_183519.81Q1hV/teacher_final.pt'


def verify_policy(metadata,parent_checkpoint,checkpoint,role):
    warm,contract=make_contract(metadata,parent_checkpoint,WARM)
    digest=contract_digest(contract);checkpoint=Path(checkpoint).resolve()
    saved=torch.load(checkpoint,map_location='cpu',weights_only=True)
    if role=='warm':
        if checkpoint!=WARM.resolve() or sha(checkpoint)!=contract['warm_start']['checkpoint_sha256']:
            raise ValueError('Warm comparison must use exactly the verified parent final')
    elif role=='trained':
        run=json.loads((checkpoint.parent/'run.json').read_text())
        stored=json.loads((checkpoint.parent/'bridge_pull_contract.json').read_text())
        if (not run.get('completed') or not run.get('source_still_matches') or not run.get('grasp_actor_unchanged')
                or not run.get('normalizers_unchanged') or stored!=contract or run['contract_sha256']!=digest
                or saved.get('infos',{}).get('bridge_pull_contract_sha256')!=digest):
            raise ValueError('New pull policy is not a completed matching native-alignment training')
        for name,h in contract['files'].items():
            if sha(ROOT/name)!=h or sha(checkpoint.parent/'source_snapshot'/name)!=h:
                raise ValueError('Native policy source changed: '+name)
        for k,v in saved['model_state_dict'].items():
            if not torch.isfinite(v).all():raise ValueError('Nonfinite native policy')
            if 'normalizer' in k and not torch.equal(v,warm['model_state_dict'][k]):
                raise ValueError('Native normalization changed')
    else:raise ValueError('Unknown explicit policy role')
    return saved,dict(role=role,checkpoint=str(checkpoint),checkpoint_sha256=sha(checkpoint),
        native_training_contract_sha256=digest,native_training_contract=contract,
        control='Unchanged26/32 posture/pause/gain1 chain; new reward is training-only',
        production_selection_changed=False,learning=False)
