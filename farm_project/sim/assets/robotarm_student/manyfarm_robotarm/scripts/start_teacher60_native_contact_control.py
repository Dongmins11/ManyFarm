"""Validated unique-folder background launch for action-aware native pull only."""
import argparse
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--ready', type=Path, default=ROOT/'outputs/harvest_rl/native_contact_control_ready.json')
    p.add_argument('--iterations', type=int, default=300)
    p.add_argument('--num-envs', type=int, default=2048)
    p.add_argument('--resume-checkpoint', type=Path)
    p.add_argument('--execute', action='store_true')
    a = p.parse_args()
    if min(a.iterations, a.num_envs) < 1:
        p.error('Positive iterations and environment count required')
    ready = json.loads(a.ready.read_text())
    for key in ('preflight', 'warm_checkpoint'):
        if sha(ready[key]) != ready[key+'_sha256']:
            raise ValueError('Readiness evidence changed: '+key)
    preflight = json.loads(Path(ready['preflight']).read_text())
    if not (preflight.get('passed') and preflight.get('native_actor_mask_verified')
            and preflight.get('actor_samples_checked', 0) > 0
            and preflight.get('optimizer_updates') == 0 and preflight.get('learning') is False):
        raise ValueError('Missing no-update control-mask preparation')
    python = Path(os.environ.get('HARVEST_PY', '/home/bhc/isaac/env_isaaclab/bin/python'))
    if not python.is_file():
        raise ValueError('Missing HARVEST_PY interpreter')
    if a.resume_checkpoint and not a.resume_checkpoint.is_file():
        p.error('Resume checkpoint does not exist')
    command = [str(python), '-u', str(ROOT/'scripts/train_teacher60_native_contact_control.py'),
        'train', '--warm-checkpoint', ready['warm_checkpoint'], '--preflight', ready['preflight'],
        '--iterations', str(a.iterations), '--num-envs', str(a.num_envs), '--headless']
    if a.resume_checkpoint:
        command += ['--resume-checkpoint', str(a.resume_checkpoint.resolve())]
    print('CONTROL_TRAIN_PLAN', json.dumps(dict(iterations=a.iterations, num_envs=a.num_envs,
        warm_checkpoint=ready['warm_checkpoint'], physical_hz=60, policy_hz=20,
        actor_samples='Actually applied arm5 proposals only; critic retains physical hold outcomes',
        output='Automatic unique folder', hardware_executed=False)), flush=True)
    if not a.execute:
        return
    fd, log = tempfile.mkstemp(prefix='teacher60_native_contact_control_'+datetime.now().strftime('%Y%m%d_%H%M%S')+'.',
        suffix='.log', dir=ROOT/'runs/harvest_rl')
    os.close(fd); output = Path(log[:-4]); command += ['--output', str(output), '--execute']
    with open(log, 'a') as stream:
        child = subprocess.Popen(command, cwd=ROOT,
            env=dict(os.environ, OPENBLAS_NUM_THREADS='1', OMP_NUM_THREADS='1'),
            stdout=stream, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
            start_new_session=True)
    launch = dict(pid=child.pid, output=str(output), log=log, command=command,
        status='launched_not_yet_verified', planned_iterations=a.iterations, num_envs=a.num_envs,
        hardware_executed=False, session_detached=True)
    target = ROOT/'outputs/harvest_rl/native_contact_control_last_launch.json'
    temporary = target.with_suffix('.tmp.json')
    temporary.write_text(json.dumps(launch, indent=2)+'\n'); temporary.replace(target)
    print('BACKGROUND_LAUNCH', json.dumps(launch), flush=True)
    time.sleep(3)
    if child.poll() is not None:
        raise RuntimeError('Startup exited; inspect '+log)
    print('STARTUP_PROCESS_ALIVE', child.pid, '\nView: tail -f '+log, flush=True)


if __name__ == '__main__':
    main()
