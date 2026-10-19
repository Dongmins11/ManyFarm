"""Audit U20 demonstrations and preserve a compact, explicitly partial native archive.

Never edits or deletes the source. The collection queue may reclaim only its own
scratch directory after verifying the complete exported file inventory.
"""
import hashlib
import json
from pathlib import Path
import shutil

import numpy as np

SCHEMA = 'student60_u20_audited_compact_v1'
PHASES = ('approach', 'bridge', 'pull', 'transport', 'place')


def read(path):
    return json.loads(Path(path).read_text())


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def require_finished(root):
    root = Path(root)
    m, r, v = (read(root / name) for name in ('dataset_manifest.json', 'run.json', 'verification.json'))
    if (root / 'COLLECTION_IN_PROGRESS.json').exists():
        raise ValueError('Collection is still in progress')
    if not all(r.get(k) for k in ('completed', 'weights_unchanged', 'source_still_matches')):
        raise ValueError('Incomplete runtime/weight/source verification')
    if not v.get('audit_passed') or v.get('student_sensor_schema') != 4:
        raise ValueError('Missing completed U20 native audit')
    if (m.get('schema_version') != 4 or m.get('student_sensor_variant') != 'u20_wrist_rgb_rear_d435_v1'
            or m.get('capture_contract') != 'physics_scheduled_u20_rgb_v1'):
        raise ValueError('Expected separate U20 schema4; D435 data is not interchangeable')
    return m, r, v


def audit_source(root):
    from harvest_runtime.student60 import TargetFilter, encode_command
    from harvest_runtime.student60_contract import ACTION_CONTRACT
    from harvest_sensors.deployment import audit_camera_sample
    from harvest_sensors.u20_deployment import validate_u20, audit_raw_captures
    from .settings import ROOT
    root = Path(root).resolve()
    m, r, _ = require_finished(root)
    validate_u20(m['camera_config'])
    if m['action_contract'] != ACTION_CONTRACT or (r['physics_hz'], r['policy_hz'], r['camera_hz']) != (60, 20, 30):
        raise ValueError('U20 action/clock contract differs')
    if m['visual_scene']['version'] != 'greenhouse_v1':
        raise ValueError('Unexpected visual environment')
    for name, sha in m['visual_scene']['sources'].items():
        if digest(ROOT / name) != sha:
            raise ValueError('Background changed: ' + name)
    for name, sha in r['source_pins'].items():
        current = Path(name)
        if current.is_file() and digest(current) == sha:
            continue
        try:
            snapshot = root / 'source_snapshot' / current.relative_to(ROOT)
        except ValueError:
            raise ValueError('Missing external source evidence: ' + name)
        if not snapshot.is_file() or digest(snapshot) != sha:
            raise ValueError('Missing matching source snapshot: ' + name)
    episodes = []
    for folder in sorted(root.glob('episode_*')):
        result = read(folder / 'result.json')
        native = audit_raw_captures(folder, m, r)
        expected_frames = int(np.floor(result['samples'] * .05 * 30 + 1e-8)) + 1
        if any(n != expected_frames for n in native['native_frames'].values()):
            raise ValueError('Native interval/count mismatch')
        filter_ = TargetFilter(m['box_from_arm'], m['box_min'], m['box_max'])
        previous_note = previous_action = None
        phases = []
        for i in range(result['samples']):
            note = read(folder / f'{i:06d}.json')
            audit_camera_sample(note, .05, previous_note)
            if abs(note['stamp_s'] - i * .05) > 1e-8:
                raise ValueError('Missing control sample')
            for camera, info in note['cameras'].items():
                expected = folder / 'raw_captures' / camera / f"{info['frame_number']:06d}.npz"
                if Path(info['raw_capture']).resolve() != expected.resolve():
                    raise ValueError('Original frame association differs')
            with np.load(folder / f'{i:06d}.npz', allow_pickle=False) as z:
                if set(z.files) != {'rgb', 'depth_m', 'state', 'camera_valid', 'action'}:
                    raise ValueError('U20 input contains missing/extra modalities')
                if (z['rgb'].shape != (2, 90, 160, 3) or z['rgb'].dtype != np.uint8
                        or z['depth_m'].shape != (2, 90, 160) or z['state'].shape != (23,)
                        or z['camera_valid'].shape != (2,) or not z['camera_valid'].all()
                        or any(z['rgb'][c].std() < 1 for c in (0, 1))):
                    raise ValueError('Invalid/blank camera observation')
                if (not np.isfinite(z['depth_m']).all() or np.any(z['depth_m'] < 0)
                        or np.any(z['depth_m'][0] != 0) or not np.isfinite(z['state']).all()):
                    raise ValueError('Invalid U20 depth/state')
                command = encode_command(note['executed_target_rad'], note['servo_command'], m['lower_rad'], m['upper_rad'])
                np.testing.assert_allclose(z['action'], command[:6], atol=1e-6)
                if previous_action is not None:
                    np.testing.assert_allclose(z['state'][12:18], previous_action, atol=1e-6)
                target = filter_.filter(note['raw_target'])
                if target != note['target'] or bool(z['state'][21]) != target['valid'] or note['target_release_latched'] != filter_.released:
                    raise ValueError('Recorded target filter differs')
                relative = np.asarray(target['position_m']) - note['tcp_arm_m'] if target['valid'] else np.zeros(3)
                np.testing.assert_allclose(z['state'][18:21], relative, atol=1e-6)
                previous_action = command[:6]
            filter_.observe_command(note['previous_target_rad'], note['executed_target_rad'], note['tcp_arm_m'])
            previous_note = note
            phases.append(note['phase'])
        reasons = []
        if result['status'] != 'SUCCEEDED':
            reasons.append(result['status'])
        if not result['diagnostics']['initial_association_ok']:
            reasons.append('initial_target_association')
        if set(phases) != set(PHASES) or phases != sorted(phases, key=PHASES.index):
            reasons.append('incomplete_or_repeated_harvest_phases')
        if not filter_.released:
            reasons.append('no_observed_release_latch')
        episodes.append(dict(episode=folder.name, color=read(folder / 'metadata.json')['layout']['target_color'],
            status=result['status'], samples=result['samples'], native=native,
            eligible_success=not reasons, exclusion_reasons=reasons))
    if len(episodes) != len(m['episodes']):
        raise ValueError('Episode manifest mismatch')
    report = dict(schema='student60_u20_full_record_audit_v1', audit_passed=True,
        final_runtime_audit_complete=True, episodes=episodes, learning=False,
        eligible_successes=sum(e['eligible_success'] for e in episodes))
    (root / 'u20_full_audit.json').write_text(json.dumps(report, indent=2) + '\n')
    return report


def verify_compact(root):
    root = Path(root).resolve()
    cert = read(root / 'compact_certificate.json')
    if cert.get('schema') != SCHEMA or cert.get('all_native_images_retained') is not False:
        raise ValueError('Not an explicitly partial U20 compact archive')
    require_finished(root)
    for name, sha in cert['files'].items():
        p = root / name
        if not p.resolve().is_relative_to(root) or not p.is_file() or digest(p) != sha:
            raise ValueError('Compact file missing/changed: ' + name)
    if not read(root / 'u20_full_audit.json')['final_runtime_audit_complete']:
        raise ValueError('Missing full source audit')
    return cert


def export_compact(source, destination):
    source, destination = Path(source).resolve(), Path(destination).resolve()
    if destination.exists() or destination.is_relative_to(source) or source.is_relative_to(destination):
        raise ValueError('Require a new separate compact destination')
    require_finished(source)
    report = read(source / 'u20_full_audit.json')
    if not report.get('audit_passed') or not report.get('final_runtime_audit_complete'):
        raise ValueError('Audit all native/control records before compacting')
    retained = set()
    for episode in sorted(source.glob('episode_*')):
        phases = {}
        for p in sorted(episode.glob('[0-9]*.json')):
            note = read(p)
            phases.setdefault(note['phase'], []).append(note)
        for rows in phases.values():
            # Preserve both camera originals at the middle of every phase.
            for info in rows[len(rows) // 2]['cameras'].values():
                path = Path(info['raw_capture']).resolve()
                if not path.is_relative_to(source) or not path.is_file():
                    raise ValueError('Representative native source missing/outside collection')
                retained.add(path.relative_to(source))
    destination.mkdir(parents=True)
    files = {}
    original = kept = 0
    for p in sorted(source.rglob('*')):
        if not p.is_file():
            continue
        if p.is_symlink():
            raise ValueError('Do not compact symlinked input')
        rel = p.relative_to(source)
        original += p.stat().st_size
        if rel.parts[0] == 'fruit_assets' or ('raw_captures' in rel.parts and p.suffix == '.npz' and rel not in retained):
            continue
        target = destination / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(p, target)
        files[str(rel)] = digest(target)
        if files[str(rel)] != digest(p):
            raise ValueError('Export copy mismatch: ' + str(rel))
        kept += target.stat().st_size
    cert = dict(schema=SCHEMA, source=str(source), schema_version=4,
        native_images_fully_audited_before_export=True, all_native_images_retained=False,
        retention='All 20Hz RGB/depth/state/actions/servo notes, native metadata, periodic preview JPEGs, one native pair per phase',
        original_bytes=original, retained_bytes=kept, files=files,
        retained_native_frames=sorted(map(str, retained)),
        native_path_mapping=dict(recorded_source=str(source), compact_root=str(destination), missing_frames_intentional=True),
        ready_for_u20_bc_training=False)
    (destination / 'compact_certificate.json').write_text(json.dumps(cert, indent=2) + '\n')
    verify_compact(destination)
    return cert
