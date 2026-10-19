"""Build a versioned D435 Student/v20 simulation handoff, preserving originals."""
import argparse
from datetime import datetime
import hashlib
import importlib.metadata
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src/harvest_robot'))
BASE = Path('outputs/harvest_rl/student60_improvement_20261015')


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1048576), b''):
            h.update(block)
    return h.hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def seal(output):
    workspace = output / 'manyfarm_robotarm'
    handoff = workspace / 'handoff'
    required = ['README_KR.md', 'DEPLOYMENT.json', 'robot/robot_with_d435.usdc',
                'robot/export_audit.json', 'verification/relocation_check.json',
                'verification/native_smoke.json']
    for name in required:
        if not (handoff / name).is_file():
            raise FileNotFoundError('Complete verification before sealing: ' + name)
    for name in ['robot/export_audit.json', 'verification/relocation_check.json']:
        if not json.loads((handoff / name).read_text()).get('passed'):
            raise ValueError('Verification failed: ' + name)
    if not json.loads((handoff / 'verification/native_smoke.json').read_text()).get('execution_check_completed'):
        raise ValueError('Native smoke did not finish')
    files = [dict(path=str(f.relative_to(workspace)), bytes=f.stat().st_size, sha256=sha(f))
             for f in sorted(workspace.rglob('*')) if f.is_file()
             and '__pycache__' not in f.parts and f != handoff / 'MANIFEST.json']
    version = json.loads((handoff / 'SOURCE_VERSION.json').read_text())
    write(handoff / 'MANIFEST.json', dict(schema='student60_d435_v20_file_release_v1',
                                        base_commit=version['base_commit'], files=files))
    archive = output / 'harvest_student60_d435_v20_20261016.tar.gz'
    with tarfile.open(archive, 'w:gz', compresslevel=4) as stream:
        for row in files + [dict(path='handoff/MANIFEST.json')]:
            stream.add(workspace / row['path'], arcname='manyfarm_robotarm/' + row['path'], recursive=False)
    (output / 'SHA256SUMS').write_text(sha(archive) + '  ' + archive.name + '\n')
    for name in ['README_KR.md', 'SEND_MESSAGE_KR.txt']:
        shutil.copy2(handoff / name, output / name)
    print(json.dumps(dict(archive=str(archive), bytes=archive.stat().st_size,
                          sha256=sha(archive), files=len(files)), indent=2))


def prepare(output, detector, vision_python):
    if output.exists():
        raise FileExistsError('Use a new output folder; existing releases are preserved')
    from harvest_rl.friction_selected import load_selected
    runtime, runtime_path, physical = load_selected()
    active = json.loads((ROOT / 'src/harvest_robot/config/teacher60_active_environment.json').read_text())
    workspace = output / 'manyfarm_robotarm'
    workspace.mkdir(parents=True)
    files = set(physical['pins']) | set(runtime['pins'])
    files.update([active['profile'], str(runtime_path.relative_to(ROOT))])
    for directory in ['src/harvest_robot', 'src/smartfarm_description/meshes',
                      'src/smartfarm_description/config', 'src/smartfarm_description/urdf',
                      'src/smartfarm_description/scripts', 'src/Pepper_RL_Demo/assets',
                      'outputs/harvest_rl/assets',
                      'outputs/harvest_rl/current_robot/b73ed90a6e56216d']:
        files.update(str(f.relative_to(ROOT)) for f in (ROOT / directory).rglob('*')
                     if f.is_file() and '__pycache__' not in f.parts and f.suffix not in ('.pyc', '.log'))
    files.update(['scripts/view_student60_camera.py', 'scripts/run_student60_camera_followthrough.py',
                  'scripts/run_student60_after_collection.py', 'scripts/monitor_student60.py',
                  'scripts/eval_student60_faster_capture_box.py', 'scripts/package_student60_sim.py'])
    files.update(str(f.relative_to(ROOT)) for f in (ROOT / 'scripts/sim_team').glob('*student60*.py'))
    files.add('scripts/sim_team/verify_bundle.py')
    files.add('docs/manipulation/SIM_TEAM_STUDENT60_D435_RECEIVER_KR.md')
    files.add('docs/manipulation/SIM_TEAM_STUDENT60_SEND_MESSAGE_KR.txt')
    files.add('docs/INTERFACES.md')
    # Original hashes remain verifiable. These four small Teacher checkpoints
    # are provenance pins only; the Student evaluator never loads their actors.
    for row in physical['policies'].values():
        files.add(row['path'])
        files.update(str(f.relative_to(ROOT)) for f in (ROOT / row['path']).parent.glob('*.json'))
    evidence = BASE / 'faster_capture_followthrough_v20'
    files.update(str(f.relative_to(ROOT)) for f in (ROOT / evidence).glob('*.json'))
    files.add(str(evidence / 'fresh_test/result.json'))
    files.update(str(f.relative_to(ROOT)) for f in (ROOT / evidence / 'fresh_test').glob('episode_*/result.json'))
    files.update(str(f.relative_to(ROOT)) for f in (ROOT / evidence / 'fresh_test').glob('episode_*/*jpg'))
    for name in ['FINAL_REPORT.json', 'CURRENT_STATUS.json', 'round2/data.json']:
        files.add(str(BASE / name))
    files.update(['scripts/audit_student60_real_inputs.py',
                  'outputs/harvest_rl/student60_real_input_audit_20261016/audit_final.json'])
    for name in sorted(files):
        src, dst = ROOT / name, workspace / name
        if not src.is_file():
            raise FileNotFoundError(src)
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
    models = {'student': ROOT / BASE / 'round2_train_lr1e4/student_best.pt',
              'center': ROOT / BASE / 'camera_only_center/center_best.pt', 'detector': detector}
    model_record = {}
    for name, src in models.items():
        dst = workspace / 'handoff/models' / (name + '.pt')
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        model_record[name] = dict(path=str(dst.relative_to(workspace)), sha256=sha(src))
    import numpy as np
    import torch
    from harvest_rl.student60_data import Student60Dataset
    from harvest_rl.student60_crop import from_record
    from harvest_rl.student60_recurrent import RecurrentCameraInference
    torch.set_num_threads(4)
    plan = json.loads((ROOT / BASE / 'round2/data.json').read_text())
    contract = plan['contract']
    dataset = Student60Dataset(plan['validation'], contract)
    policy = RecurrentCameraInference(models['student'], contract, 'cpu')
    observations, predictions, acknowledgements = [], [], []
    for index in range(3):
        sample, _, _ = dataset[index]
        observation = {k: v[-1] for k, v in sample.items()}
        folder, step, _ = dataset.rows[index]
        observation.update(from_record(observation, json.loads((folder / f'{step:06d}.json').read_text()), contract))
        if index:
            acknowledgement = np.r_[observation['state'][12:18], [-1., 1.]].astype('float32')
            policy.acknowledge(acknowledgement)
            acknowledgements.append(acknowledgement)
        predictions.append(policy.predict(observation, 'release-contract-test'))
        observations.append(observation)
    np.savez_compressed(workspace / 'handoff/contract_sample.npz',
                        **{k: np.stack([o[k] for o in observations]) for k in observations[0]},
                        expected=np.stack(predictions), acknowledgements=np.stack(acknowledgements))
    source = json.loads((ROOT / physical['policies']['grasp']['path']).parent.joinpath('run.json').read_text())
    write(workspace / 'handoff/DEPLOYMENT.json', dict(
        schema='student60_d435_v20_sim_handoff_v1', created_date='2026-10-16',
        role='camera Student + explicit v20 assistance; right arm only',
        model_family='student60_camera_recurrent_delta_v1', models=model_record,
        contract=contract, data_path=str(BASE / 'round2/data.json'),
        data_sha256=sha(ROOT / BASE / 'round2/data.json'),
        input_seeds=sorted({e['seed'] for split in ['train', 'validation'] for e in plan[split]}),
        source_root=str(ROOT), robot_root_to_policy_world=source['current_base_to_policy_world'],
        frozen_physics_usd='outputs/harvest_rl/current_robot/b73ed90a6e56216d/harvest_current.usd',
        robot_with_cameras='handoff/robot/robot_with_d435.usdc',
        validation=dict(development='4/4', frozen_fresh_test='4/4', fresh_seed=106146,
                        criterion='box_outcome_v2', fruit_mass_kg=.009,
                        neural_policy_only=False, hardware_executed=False,
                        wall_clock_20hz_verified=False, latency_candidate_harvest='0/4; excluded from defaults'),
        teacher_checkpoint_role='Original physical-profile integrity pins only; actor loads=0 in Student evaluation',
        detector_provenance=dict(original_filename=detector.name,
            note='Existing user-supplied custom Ultralytics segmentation weight; training data/redistribution terms not established here'),
        raw_training_data_included=False))
    shutil.copy2(ROOT / 'docs/manipulation/SIM_TEAM_STUDENT60_D435_RECEIVER_KR.md', workspace / 'handoff/README_KR.md')
    shutil.copy2(ROOT / 'docs/manipulation/SIM_TEAM_STUDENT60_SEND_MESSAGE_KR.txt', workspace / 'handoff/SEND_MESSAGE_KR.txt')
    versions = {}
    for name in ['torch', 'numpy', 'scipy', 'Pillow', 'trimesh', 'isaacsim', 'isaaclab']:
        try:
            versions[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            pass
    write(workspace / 'handoff/EXECUTION_ENVIRONMENT.json', dict(python=sys.version, versions=versions,
          note='Isaac environment and a separate Ultralytics vision Python; no virtual environments shipped'))
    vision = subprocess.check_output([str(vision_python), '-c',
        "import importlib.metadata as m,json,sys; "
        "print(json.dumps(dict(python=sys.version,versions={n:m.version(n) for n in "
        "['ultralytics','torch','torchvision','numpy','opencv-python','Pillow']})))"], text=True)
    write(workspace / 'handoff/VISION_ENVIRONMENT.json', json.loads(vision))
    write(workspace / 'handoff/SOURCE_VERSION.json', dict(
        base_commit=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
        source_is_dirty=True, included_files=sorted(files),
        original_source_hashes={name: sha(ROOT / name) for name in sorted(files)},
        excluded=['.git', 'virtual environments', 'raw training collections', 'U20 weights', 'timing candidate defaults']))
    print('PREPARED', workspace, flush=True)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--detector', type=Path, default=Path('/home/bhc/Downloads/model_yolo11_seg_ver1.2.pt'))
    p.add_argument('--vision-python', type=Path, default=ROOT / '.venvs/harvest_vision/bin/python')
    p.add_argument('--seal', action='store_true')
    args = p.parse_args()
    if args.seal:
        seal(args.output.resolve())
    else:
        prepare(args.output.resolve(), args.detector.resolve(), args.vision_python.resolve())


if __name__ == '__main__':
    main()
