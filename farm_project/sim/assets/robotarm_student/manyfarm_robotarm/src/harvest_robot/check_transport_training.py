"""Validate transport fine-tuning inputs without starting Isaac or learning."""
import argparse
import hashlib
import json
from pathlib import Path
from harvest_rl.settings import TaskSettings
from harvest_rl.behavior_contract import prepare_harvest_transfer
from harvest_rl.stage_bank import StageStartBank


def check(checkpoint, bank):
    checkpoint=Path(checkpoint)
    metadata=json.loads((checkpoint.parent/'run.json').read_text())
    settings=TaskSettings(**metadata['task'])
    if settings.task!='transport':
        raise ValueError('Expected an existing transport checkpoint')
    prepare_harvest_transfer(settings)
    settings.task='transport';settings.start_bank=str(bank)
    settings.workspace_split='train';settings.target_mode='random';settings.sequence=False
    settings.num_fruits=1;settings.transport_start_min=0.;settings.transport_start_max=0.
    settings.transport_replay_fraction=0.;settings.pregrasp_fraction=0.;settings.curriculum=0.
    settings.shape_placement=True;settings.box_bottom_contact_tolerance=.010
    settings.legacy_box_bottom_margin=.010;settings.contact_substeps=2
    settings.detached_grip_hold=True;settings.release_intent_mode=True
    settings.transport_adaptive_grip=True;settings.transport_pose_stop=True
    settings.validate()
    loaded=StageStartBank(bank,settings,'cpu')
    return dict(checkpoint=str(checkpoint.resolve()),
        checkpoint_sha256=hashlib.sha256(checkpoint.read_bytes()).hexdigest(),
        bank=str(Path(bank).resolve()),bank_sha256=loaded.sha256,states=loaded.count,
        task=settings.as_dict(),learning_started=False)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--checkpoint',type=Path,required=True)
    p.add_argument('--bank',type=Path,required=True)
    p.add_argument('--report',type=Path)
    a=p.parse_args();result=check(a.checkpoint,a.bank)
    if a.report:
        with a.report.open('x') as f:json.dump(result,f,indent=2)
    print('TRANSPORT_PREFLIGHT_OK',result['states'],'states; no learning started')
