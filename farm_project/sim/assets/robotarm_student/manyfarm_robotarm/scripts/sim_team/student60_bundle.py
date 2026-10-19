"""Release preflight independent of the author's raw training directories."""
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src/harvest_robot'))


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1048576), b''):
            h.update(block)
    return h.hexdigest()


def deployment():
    return json.loads((ROOT / 'handoff/DEPLOYMENT.json').read_text())


def verify_manifest():
    manifest = ROOT / 'handoff/MANIFEST.json'
    if not manifest.is_file():
        raise FileNotFoundError('Release manifest missing; use --building only while preparing this release')
    rows = json.loads(manifest.read_text())['files']
    for row in rows:
        path = (ROOT / row['path']).resolve()
        if not path.is_relative_to(ROOT) or path.stat().st_size != row['bytes'] or sha(path) != row['sha256']:
            raise ValueError('Release checksum mismatch: ' + row['path'])
    return len(rows)


def check_contract(building=False):
    import numpy as np
    import torch
    from harvest_rl.student60_recurrent import RecurrentCameraInference, FAMILY
    from harvest_rl.friction_selected import load_selected
    from harvest_rl.settings import URDF
    d = deployment()
    file_count = None if building else verify_manifest()
    for record in d['models'].values():
        if sha(ROOT / record['path']) != record['sha256']:
            raise ValueError('Model checksum differs')
    checkpoint = ROOT / d['models']['student']['path']
    saved = torch.load(checkpoint, map_location='cpu', weights_only=True)
    c = d['contract']
    if saved['contract'] != c or saved['model_family'] != FAMILY or saved['data_sha256'] != d['data_sha256']:
        raise ValueError('Model/observation contract differs')
    if sha(ROOT / d['data_path']) != d['data_sha256']:
        raise ValueError('Original training-plan fingerprint differs')
    camera_path = ROOT / 'src/harvest_robot/config/d435_deployment_20261013_overhead30.json'
    if json.loads(camera_path.read_text()) != c['camera_config'] or sha(URDF) != c['sensor_mount_reference_urdf_sha256']:
        raise ValueError('Camera or sensor FK reference differs')
    runtime, runtime_path, physical = load_selected()
    if runtime != c['teacher_runtime']:
        raise ValueError('Physical runtime profile differs')
    torch.set_num_threads(4)
    policy = RecurrentCameraInference(checkpoint, c, 'cpu')
    with np.load(ROOT / 'handoff/contract_sample.npz') as sample:
        predictions = []
        for i in range(len(sample['expected'])):
            if i:
                policy.acknowledge(sample['acknowledgements'][i - 1])
            observation = {k: sample[k][i] for k in sample.files if k not in ('expected', 'acknowledgements')}
            predictions.append(policy.predict(observation, 'release-contract-test'))
        np.testing.assert_allclose(predictions, sample['expected'], atol=1e-6, rtol=1e-6)
    return dict(passed=True, files_verified=file_count, model_family=FAMILY,
        checkpoint_path=str(checkpoint), checkpoint_sha256=sha(checkpoint), checkpoint_epoch=saved['epoch'],
        data_path=str(ROOT / d['data_path']), data_sha256=d['data_sha256'],
        student60_version=saved['student60_version'], history_forward_matches_offline=True,
        input_sources_checked=len(runtime['pins']) + len(physical['pins']),
        input_seeds=d['input_seeds'], native_hz=30, policy_hz=20, physics_hz=60,
        teacher_actors_loaded=False, model_observations=3,
        runtime_profile_path=str(runtime_path), camera_config_path=str(camera_path),
        observation_extension=saved['observation_extension'],
        note='Offline release check; not a new completed harvest evaluation'), c, physical


def relocate_physics_input():
    """Rebase only the input USD pathname; preserve all original source bytes."""
    from harvest_sensors import deployment_asset
    original = deployment_asset.prepare_deployment_robot
    d = deployment()

    def prepare(previous, config):
        previous = dict(previous, usd=str(ROOT / d['frozen_physics_usd']))
        return original(previous, config)

    deployment_asset.prepare_deployment_robot = prepare
