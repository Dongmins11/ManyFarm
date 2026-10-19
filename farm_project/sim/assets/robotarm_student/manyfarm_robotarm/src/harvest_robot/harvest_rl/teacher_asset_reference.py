"""Pin the actual cached Teacher asset independently of editable CAD sources.

The old Student manifest stays strict and untouched. Only this cached-USD
Teacher launcher permits drift in two authoring files it never loads.
"""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
AUTHORING_ONLY = {
    'src/smartfarm_description/urdf/harvest_robot.urdf',
    'src/smartfarm_description/config/assembly.yaml',
}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def verify_teacher_assets(reference_path, asset_reference_path, source_path, root=ROOT):
    root = Path(root)
    reference_path = Path(reference_path)
    source_path = Path(source_path)
    pins = json.loads(Path(asset_reference_path).read_text())
    if pins['schema'] != 'cached_teacher_asset_reference_v1':
        raise ValueError('Wrong cached Teacher asset reference schema')
    if set(pins['authoring_only']) != AUTHORING_ONLY:
        raise ValueError('Only the two unused CAD authoring files can be separated')
    if sha(reference_path) != pins['student_reference_sha256']:
        raise ValueError('Original Student reference was replaced or edited')
    if sha(source_path) != pins['source_run_sha256']:
        raise ValueError('Cached Teacher source run changed')
    source = json.loads(source_path.read_text())
    usd = Path(source['current_asset']['usd']).resolve()
    if usd != (root/pins['robot_usd']).resolve():
        raise ValueError('Cached Teacher USD path differs from pinned asset')
    if pins['robot_usd'] not in pins['files']:
        raise ValueError('Missing pinned robot USD hash')
    reference = json.loads(reference_path.read_text())
    # Runtime code, original meshes, fruit and visual sources remain protected.
    expected = {name:value for name,value in reference['files'].items()
                if name not in AUTHORING_ONLY}
    for name,value in pins['files'].items():
        if name in expected and expected[name] != value:
            raise ValueError(f'Asset pin conflicts with Student source: {name}')
        expected[name] = value
    wrong = [name for name,value in expected.items()
             if not (root/name).is_file() or sha(root/name) != value]
    if wrong:
        raise ValueError(f'Cached Teacher runtime/source/asset changed: {wrong}')
    drift = []
    for name in sorted(AUTHORING_ONLY):
        current = sha(root/name) if (root/name).is_file() else None
        original = reference['files'][name]
        if current != original:
            drift.append(dict(path=name,original_sha256=original,current_sha256=current,
                used_by_this_run=False,reason='Explicit cached USD; no live URDF conversion or assembly loader'))
    return dict(files=expected,authoring_drift=drift,robot_usd=str(usd),
        original_student_reference_sha256=pins['student_reference_sha256'],
        asset_reference_sha256=sha(asset_reference_path))
