"""New physical/reward contract, warm-started from the completed latest final."""
from dataclasses import asdict
import json
from pathlib import Path
import torch
from .native_policy_transfer import verify_policy as verify_parent
from .native_alignment_training import training_settings, FILES as PARENT_FILES
from .native_contact_refine_v2 import SPEC, TRAIN_ANCHOR_IDS
from .grasp_handoff_60hz import contract_digest, physical_signature
from .teacher_asset_reference import sha

ROOT = Path(__file__).resolve().parents[3]
WARM = ROOT/'runs/harvest_rl/teacher60_native_alignment_20261012_170952.RKKKIl/teacher_final.pt'
PROFILE = ROOT/'src/harvest_robot/config/teacher60_stop_floor_selected_20261012.json'
BASELINE = ROOT/'outputs/harvest_rl/floor_unified_full_20261012_r1'
FILES = list(dict.fromkeys(PARENT_FILES+[
    'scripts/train_teacher60_native_contact.py',
    'scripts/train_teacher60_native_contact.sh',
    'scripts/analyze_teacher60_native_contact.py',
    'scripts/eval_teacher60_native_contact_chain.py',
    'scripts/analyze_teacher60_native_contact_chain.py',
    'scripts/evaluate_teacher60_native_contact.py',
    'src/harvest_robot/harvest_rl/native_contact_refine.py',
    'src/harvest_robot/harvest_rl/native_contact_training.py',
    'src/harvest_robot/harvest_rl/teacher_native_contact_env.py',
    'scripts/train_teacher60_native_contact_v2.py',
    'scripts/train_teacher60_native_contact_v2.sh',
    'scripts/analyze_teacher60_native_contact_v2.py',
    'scripts/eval_teacher60_native_contact_v2_chain.py',
    'scripts/analyze_teacher60_native_contact_v2_chain.py',
    'scripts/evaluate_teacher60_native_contact_v2.py',
    'src/harvest_robot/harvest_rl/native_contact_refine_v2.py',
    'src/harvest_robot/harvest_rl/native_contact_v2_training.py',
    'src/harvest_robot/harvest_rl/teacher_native_contact_v2_env.py',
    'src/harvest_robot/harvest_rl/native_policy_transfer.py',
    'src/harvest_robot/harvest_rl/floor_unified.py',
    'src/harvest_robot/harvest_rl/floor_collision_v4.py',
    'src/harvest_robot/config/teacher60_stop_floor_selected_20261012.json']))


def make_contract(metadata, parent_checkpoint, warm_checkpoint=WARM):
    warm_checkpoint = Path(warm_checkpoint).resolve()
    if warm_checkpoint != WARM.resolve():
        raise ValueError('This branch starts from exactly the latest completed native final')
    warm, provenance = verify_parent(metadata, parent_checkpoint, warm_checkpoint, 'trained')
    if provenance['checkpoint_sha256'] != '2f70ab7870955b7f833a98b197b507dee9b2c66dfb6eb2307d2d3ac262af7491':
        raise ValueError('Latest warm model changed')
    selected = json.loads(PROFILE.read_text())
    # Selected profile has a declared unified floor; also pin completed original
    # inference artifacts as reference. No held-out state/labels enter sampling.
    floor = dict(mode='unified', added_shapes=1, disabled_shapes=8,
        added_rigid_bodies=0, contact_offset_m=.04, rest_offset_m=0.,
        depth_m=.05, visible_top_z_m=.501, original_usd_modified=False)
    evidence = {}; frozen_files = {}
    for split in ('train', 'validation', 'test'):
        run = json.loads((BASELINE/split/'run.json').read_text())
        result = json.loads((BASELINE/split/'evaluation.json').read_text())
        if (not run.get('completed') or run.get('learning') or result['count'] != 32
                or run['evaluation_checkpoint_sha256'] != provenance['checkpoint_sha256']
                or run['floor_collision_override']['mode'] != 'unified'):
            raise ValueError('Selected full-chain reference is incomplete or mismatched')
        for name in ('run.json', 'evaluation.json', 'initial_samples.json', 'bridge_pull_contract.json'):
            path = BASELINE/split/name
            evidence[str(path.relative_to(ROOT))] = sha(path)
        reference = json.loads((BASELINE/split/'bridge_pull_contract.json').read_text())
        for name, h in reference['files'].items():
            if sha(ROOT/name) != h or sha(BASELINE/split/'source_snapshot'/name) != h:
                raise ValueError('Selected chain implementation changed: '+name)
            frozen_files[name] = h
    prior = provenance['native_training_contract']
    cfg = training_settings(metadata, 5042)
    return warm, dict(schema='teacher60_native_contact_training_v2',
        parent=prior, parent_contract_sha256=provenance['native_training_contract_sha256'],
        spec=prior['spec'], alignment=prior['alignment'], contact_refine=asdict(SPEC),
        source_grasp_sha256=metadata['source_checkpoint_sha256'],
        source_grasp_contract_sha256=metadata['source_contract_sha256'],
        pull_transfer=prior['pull_transfer'], physical_signature=physical_signature(cfg.as_dict()),
        placement_height_v2=prior['placement_height_v2'],
        domain=metadata['source_run']['domain'], source_domain_files=metadata['source_contract']['domain_files'],
        warm_start=dict(checkpoint=str(warm_checkpoint), checkpoint_sha256=sha(warm_checkpoint),
            run_sha256=sha(warm_checkpoint.parent/'run.json'), weights_and_normalizers=True,
            optimizer_transferred=False),
        floor_collision_override=floor, selected_chain_profile=str(PROFILE.relative_to(ROOT)),
        selected_chain_profile_sha256=sha(PROFILE), selected_profile_schema=selected.get('schema'),
        baseline_artifacts=evidence,
        sampling=dict(train_anchor_bank_ids=list(TRAIN_ANCHOR_IDS), mixture='75% unique reachable candidates uniform +25% distinct train neighbors',
            original_far_repetitions_removed_in_train_only=True,
            pose='Original random tilt/yaw/color/threshold/HOME jitter; no fixed failure-pose replay',
            held_out_ids_used_for_learning=False, evaluation='Original uniform split/seed, no oversampling'),
        files={**frozen_files, **{name:sha(ROOT/name) for name in FILES}},
        split='train', domain_stage=3, controller=prior['controller'],
        optimizer_transferred=False, grasp_actor_learns=False, bank_restore=False,
        old_probe_gate_reused=False, original_success_failure_gates=True,
        production_selection_changed=False,
        scope='Native arm5 pull -> valid detachment -> actual0.5s retention. Frozen HOME/bridge and selected full-chain transport/stop/release.')


def verify_policy(metadata, parent_checkpoint, checkpoint, role):
    warm, contract = make_contract(metadata, parent_checkpoint)
    digest = contract_digest(contract); checkpoint = Path(checkpoint).resolve()
    if role == 'warm':
        if checkpoint != WARM.resolve():
            raise ValueError('Warm inference must use the latest parent final')
        saved = warm
    elif role == 'trained':
        run = json.loads((checkpoint.parent/'run.json').read_text())
        stored = json.loads((checkpoint.parent/'bridge_pull_contract.json').read_text())
        saved = torch.load(checkpoint, map_location='cpu', weights_only=True)
        if (not run.get('completed') or not run.get('source_still_matches')
                or not run.get('grasp_actor_unchanged') or not run.get('normalizers_unchanged')
                or stored != contract or run['contract_sha256'] != digest
                or saved.get('infos', {}).get('bridge_pull_contract_sha256') != digest):
            raise ValueError('Requires a completed matching native-contact training')
        for name, h in contract['files'].items():
            if sha(ROOT/name) != h or sha(checkpoint.parent/'source_snapshot'/name) != h:
                raise ValueError('Native-contact source changed: '+name)
        for key, value in saved['model_state_dict'].items():
            if not torch.isfinite(value).all():
                raise ValueError('Nonfinite trained policy')
            if 'normalizer' in key and not torch.equal(value, warm['model_state_dict'][key]):
                raise ValueError('Transferred normalization changed')
    else:
        raise ValueError('Unknown policy role')
    return saved, dict(role=role, checkpoint=str(checkpoint), checkpoint_sha256=sha(checkpoint),
        native_training_contract_sha256=digest, native_training_contract=contract,
        control='Preserved native pause/risk/retention and selected stopV4/unified floor',
        production_selection_changed=False, learning=False)
