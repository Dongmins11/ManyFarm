"""Strict U20-only compact demonstration preparation; truth is diagnostic only."""
from collections import Counter
import json
from pathlib import Path

import numpy as np
import torch
from torch.utils.data import Dataset

from .settings import ROOT
from .student60_u20_archive import digest, read, verify_compact, require_finished, PHASES
from .student60_u20_model import VERSION
from harvest_runtime.student60 import VERSION as COMMAND_VERSION, OBSERVATION, TargetFilter, encode_command


def approach_quality_ok(quality):
    samples = quality.get('samples', 0)
    error = quality.get('error_p95_m')
    return bool(samples > 0 and quality['valid'] / samples >= .8 and error is not None and np.isfinite(error) and error <= .03)


def require_contract(contract):
    from harvest_sensors.u20_deployment import validate_u20, reference_urdf, CAPTURE_CONTRACT
    from .visual_scene import contract as visual_contract
    expected = read(ROOT / 'src/harvest_robot/config/u20_wrist_deployment_v1.json')
    validate_u20(expected)
    if (contract.get('student_schema_version') != 4 or contract.get('model_family') != VERSION
            or contract.get('command_version') != COMMAND_VERSION or contract.get('observation_contract') != OBSERVATION
            or contract.get('camera_config') != expected or contract.get('capture_contract') != CAPTURE_CONTRACT
            or contract.get('camera_order') != ['right', 'rear'] or contract.get('history') != 3
            or contract.get('control_dt') != .05 or contract.get('sensor_dt') != 1 / 30):
        raise ValueError('Require current separate U20 RGB schema4 observations/actions/timing')
    if (contract['sensor_mount_reference_urdf_sha256'] != digest(reference_urdf(expected))
            or contract['deployment_arm_appearance_sha256'] != digest(ROOT / 'src/harvest_robot/config/arm_appearance.json')
            or contract['visual_scene_sha256'] != visual_contract()['sha256']):
        raise ValueError('Current U20 camera mount/appearance/background differs')
    if contract['task']['mass'] != .009 or contract['task']['physics_dt'] != 1 / 60 or contract['task']['decimation'] != 3:
        raise ValueError('Expected collected9g/60Hz physics/20Hz commands')


def contract_for(root):
    m, r, _ = require_finished(root)
    keys = ('observation_contract', 'camera_order', 'camera_config', 'capture_contract', 'history', 'control_dt',
        'sensor_dt', 'timing_contract', 'frame_id', 'lower_rad', 'upper_rad', 'joint_names', 'detector_sha256',
        'action_contract', 'centre_offset_m', 'box_from_arm', 'box_min', 'box_max')
    result = {k: m[k] for k in keys}
    result.update(student_schema_version=4, model_family=VERSION, command_version=m['student60_version'],
        visual_scene_sha256=m['visual_scene']['sha256'], teacher_runtime=r['teacher_runtime'], task=r['task'].copy(),
        sensor_mount_reference_urdf_sha256=r['current_asset']['sensor_mount_reference_urdf_sha256'],
        deployment_arm_appearance_sha256=r['current_asset']['deployment_arm_appearance_sha256'],
        robot_asset_sha256=r['current_asset']['asset_input_sha256'])
    result['task'].pop('seed', None)
    require_contract(result)
    return result


def validate_sample(row):
    if set(row) != {'rgb', 'depth_m', 'camera_valid', 'state', 'action'}:
        raise ValueError('Expected RGB-only wrist; no IR/privileged fields')
    if (row['rgb'].shape != (2, 90, 160, 3) or row['rgb'].dtype != np.uint8
            or row['depth_m'].shape != (2, 90, 160) or row['state'].shape != (23,)
            or row['camera_valid'].shape != (2,) or row['action'].shape != (6,)):
        raise ValueError('Invalid U20 training sample shape')
    if (not np.isfinite(row['depth_m']).all() or np.any(row['depth_m'] < 0) or np.any(row['depth_m'][0] != 0)
            or not np.isfinite(row['state']).all() or not np.isfinite(row['action']).all()
            or np.any(np.abs(row['action']) > 1.000001) or not row['camera_valid'].all()):
        raise ValueError('Invalid U20 modality/value')


def prepare(roots_by_split, minimum_train=50, minimum_validation=10):
    plan = dict(student60_version=VERSION, train=[], validation=[], files={}, skipped=[], warnings=[],
        ready_for_initial_bc=False, closed_loop_harvest_evaluated=False,
        quality_gates=dict(approach_minimum_valid_fraction=.8, approach_maximum_error_p95_m=.03))
    reference = None
    seeds = {s: set() for s in ('train', 'validation')}
    identities = {s: set() for s in seeds}
    scene_poses = {s: set() for s in seeds}
    roots_seen = set()
    for split in ('train', 'validation'):
        for supplied in roots_by_split[split]:
            root = Path(supplied).resolve()
            if root in roots_seen or (root / 'DO_NOT_TRAIN.json').exists():
                raise ValueError('Repeated or quarantined collection root')
            roots_seen.add(root)
            cert = verify_compact(root)
            m, _, _ = require_finished(root)
            if m['split_role'] != split:
                raise ValueError('Collection split differs from requested role')
            contract = contract_for(root)
            if reference is None:
                reference = contract
            if contract != reference:
                raise ValueError('Mixed U20 camera/physics/servo/Teacher contracts')
            seeds[split].add(m['seed'])
            plan['files'][str(root / 'compact_certificate.json')] = digest(root / 'compact_certificate.json')
            # Preserve and verify every archived file, including source snapshot and selected raw evidence.
            for name, sha in cert['files'].items():
                plan['files'][str(root / name)] = sha
            approved = {e['episode']: e for e in read(root / 'u20_full_audit.json')['episodes']}
            for folder in sorted(root.glob('episode_*')):
                result, meta = read(folder / 'result.json'), read(folder / 'metadata.json')
                decision = approved[folder.name]
                if result['status'] != decision['status']:
                    raise ValueError('Outcome differs from full source audit')
                if not decision['eligible_success']:
                    plan['skipped'].append(dict(path=str(folder), reasons=decision['exclusion_reasons']))
                    continue
                phases = []
                previous = first = None
                initial_joint = None
                target_filter = TargetFilter(contract['box_from_arm'], contract['box_min'], contract['box_max'])
                quality = {}
                for i in range(result['samples']):
                    path = folder / f'{i:06d}.npz'
                    note = read(path.with_suffix('.json'))
                    with np.load(path, allow_pickle=False) as z:
                        row = {k: z[k] for k in z.files}
                    validate_sample(row)
                    if i == 0:
                        initial_joint = np.asarray(note['joint_rad'], dtype=float)
                        if initial_joint.shape != (6,) or not np.isfinite(initial_joint).all():
                            raise ValueError('Invalid initial measured joint state')
                        normalized = 2 * (initial_joint - np.asarray(contract['lower_rad'])) / (
                            np.asarray(contract['upper_rad']) - np.asarray(contract['lower_rad'])) - 1
                        np.testing.assert_allclose(row['state'][:6], normalized, atol=1e-6)
                    command = encode_command(note['executed_target_rad'], note['servo_command'], contract['lower_rad'], contract['upper_rad'])
                    np.testing.assert_allclose(row['action'], command[:6], atol=1e-6)
                    if previous is not None:
                        np.testing.assert_allclose(row['state'][12:18], previous, atol=1e-6)
                    target = target_filter.filter(note['raw_target'])
                    if target != note['target'] or bool(row['state'][21]) != target['valid'] or note['target_release_latched'] != target_filter.released:
                        raise ValueError('Target timing/release filtering differs from inference')
                    relative = np.asarray(target['position_m']) - note['tcp_arm_m'] if target['valid'] else np.zeros(3)
                    np.testing.assert_allclose(row['state'][18:21], relative, atol=1e-6)
                    if first is None and target['valid']:
                        first = (note['stamp_s'], note['target_error_m'])
                    target_filter.observe_command(note['previous_target_rad'], note['executed_target_rad'], note['tcp_arm_m'])
                    previous = command[:6]
                    phase = note['phase']
                    phases.append(phase)
                    q = quality.setdefault(phase, dict(samples=0, valid=0, fresh=0, errors_m=[]))
                    q['samples'] += 1
                    q['valid'] += int(target['valid'])
                    q['fresh'] += int(target['valid'] and target['age_s'] <= .05)
                    if note['target_error_m'] is not None:
                        q['errors_m'].append(note['target_error_m'])
                if (set(phases) != set(PHASES) or phases != sorted(phases, key=PHASES.index)
                        or not target_filter.released or first is None or first[0] > .5 or first[1] is None or first[1] > .03):
                    raise ValueError('Full-source eligibility does not match archived samples')
                # Fruit pose can recur legitimately with a different randomized HOME.
                # Keep such distinct trials, deduplicate identical recorded initial
                # states, and still reject target-pose overlap across held-out splits.
                identity = json.dumps([meta['layout']['domain_sample'], meta['layout']['fruit_world_m'],
                    initial_joint.tolist()], sort_keys=True)
                pose = json.dumps(meta['layout']['domain_sample'], sort_keys=True)
                for q in quality.values():
                    values = q.pop('errors_m')
                    q['error_p95_m'] = float(np.percentile(values, 95)) if values else None
                approach = quality['approach']
                if not approach_quality_ok(approach):
                    plan['skipped'].append(dict(path=str(folder), reasons=['approach_observation_quality'], quality=quality))
                    continue
                if identity in identities[split]:
                    plan['skipped'].append(dict(path=str(folder), reasons=['duplicate_recorded_initial_state']))
                    continue
                identities[split].add(identity)
                scene_poses[split].add(pose)
                plan[split].append(dict(path=str(folder), samples=result['samples'], phases=phases,
                    seed=m['seed'], color=meta['layout']['target_color'], domain_sample=meta['layout']['domain_sample'],
                    fruit_world_m=meta['layout']['fruit_world_m'], initial_joint_rad=initial_joint.tolist(), observation_quality=quality))
        minimum = minimum_train if split == 'train' else minimum_validation
        colors = Counter(e['color'] for e in plan[split])
        if len(plan[split]) < minimum or any(colors[c] < (minimum + 1) // 2 for c in ('Red', 'Yellow')):
            raise ValueError(f'Need >= {minimum} balanced eligible {split} demonstrations')
    if seeds['train'] & seeds['validation'] or scene_poses['train'] & scene_poses['validation']:
        raise ValueError('Train/validation seed or scene leakage')
    plan['contract'] = reference
    plan['summary'] = {s: dict(episodes=len(plan[s]), samples=sum(e['samples'] for e in plan[s]),
        colors=dict(Counter(e['color'] for e in plan[s])),
        phases=dict(Counter(p for e in plan[s] for p in e['phases'])),
        unique_bank_points=len({int(e['domain_sample'][0]) for e in plan[s]}),
        unique_target_poses=len({json.dumps(e['domain_sample'], sort_keys=True) for e in plan[s]}),
        tilt_range_deg=[min(e['domain_sample'][1] for e in plan[s]), max(e['domain_sample'][1] for e in plan[s])],
        fruit_world_min_m=np.min([e['fruit_world_m'] for e in plan[s]], axis=0).tolist(),
        fruit_world_max_m=np.max([e['fruit_world_m'] for e in plan[s]], axis=0).tolist()) for s in ('train', 'validation')}
    plan['warnings'] = ['Offline held-out action error is not autonomous harvest success.',
        'This capture contains160x90 policy samples. Full-resolution RGB was compacted; do not claim320x180 training.',
        'Mount geometry/nominal U20 optics are not real hand-eye calibration.']
    plan['ready_for_initial_bc'] = True
    return plan


def verify(plan):
    if plan.get('student60_version') != VERSION or not plan.get('ready_for_initial_bc'):
        raise ValueError('Not a prepared U20 BC plan')
    require_contract(plan['contract'])
    for split in ('train', 'validation'):
        for e in plan[split]:
            root = Path(e['path']).parent
            if (root / 'DO_NOT_TRAIN.json').exists() or (root / 'COLLECTION_IN_PROGRESS.json').exists():
                raise ValueError('Quarantined/incomplete U20 collection')
    for name, sha in plan['files'].items():
        if digest(name) != sha:
            raise ValueError('Prepared U20 data changed: ' + name)


class U20Dataset(Dataset):
    def __init__(self, episodes, contract):
        self.rows = [(Path(e['path']), i, PHASES.index(phase)) for e in episodes for i, phase in enumerate(e['phases'])]
        self.contract = contract

    def __len__(self):
        return len(self.rows)

    def __getitem__(self, index):
        folder, i, phase = self.rows[index]
        frames = []
        for j in range(i - 2, i + 1):
            with np.load(folder / f'{max(0, j):06d}.npz', allow_pickle=False) as z:
                frames.append({k: z[k] for k in z.files if k != 'action'})
        observation = {k: np.stack([f[k] for f in frames]) for k in frames[0]}
        note = read(folder / f'{i:06d}.json')
        command = encode_command(note['executed_target_rad'], note['servo_command'], self.contract['lower_rad'], self.contract['upper_rad'])
        return observation, command, phase

    def weights(self):
        counts = Counter(phase for _, _, phase in self.rows)
        return torch.tensor([1 / counts[phase] for _, _, phase in self.rows], dtype=torch.double)
