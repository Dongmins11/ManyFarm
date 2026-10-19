"""Evaluate the active versioned environment, same-terminal live output.

Delegates to the frozen verified full-chain worker and binds its actual result
to the adopted version. This script has no training or hardware execution mode.
"""
import argparse
from datetime import datetime
import json
import os
from pathlib import Path
import subprocess
import sys
import uuid

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src/harvest_robot'))
from harvest_rl.environment_version import load_profile,rooted,sha,validate_settings,material_signature


def command_for(profile,output,split,seed,headless,execute):
    python=os.environ.get('HARVEST_PY','/home/bhc/isaac/env_isaaclab/bin/python')
    # Paired references require the exact same reset seed. A fresh seed or a
    # not-yet-measured split uses its own run for physics/control auditing only.
    baseline=profile['baseline_evaluations'].get(split)
    if baseline is None or (seed is not None and seed!=profile['evaluation_seeds'][split]):
        baseline=output
    command=[python,'-u',str(ROOT/profile['evaluation_worker']),
        '--checkpoint',str(rooted(profile['policies']['native']['path'])),
        '--pressure-reference',str(rooted(baseline)),
        '--split',split,'--effective-friction','1.6','--pad-mode','none','--output',str(output)]
    if seed is not None:command+=['--seed',str(seed)]
    if headless:command+=['--headless']
    if execute:command+=['--execute']
    return command


def bind_result(output,profile,path):
    output=Path(output);run=json.loads((output/'run.json').read_text())
    audit=json.loads((output/'jaw_surface_audit_end.json').read_text())
    override=json.loads((output/'jaw_surface_override.json').read_text())
    validate_settings(run['task'],profile)
    if not run.get('completed') or run['learning'] or run['hardware_executed'] or not run['normalizers_unchanged']:
        raise ValueError('Not a completed inference-only environment application')
    if (run['evaluation_checkpoint_sha256']!=profile['policies']['native']['sha256']
            or run['jaw_surface_comparison']['effective_friction']!=1.6
            or run['jaw_surface_comparison']['pad_mode']!='none'
            or audit['pad_shapes'] or not audit['all_clones_verified']
            or not audit['jaw_material_verified'] or not audit['fruit_material_unchanged']
            or audit['added_rigid_bodies'] or audit['original_assets_modified']
            or not audit['camera_motor_materials_unchanged']
            or not audit['full_mass_inertia_attributes_unchanged']
            or override['jaw_static_dynamic_friction']!=2.2
            or override['fruit_static_dynamic_friction']!=1.
            or abs(run['actual_physics_dt_s']-1/60)>1e-12 or abs(run['actual_policy_dt_s']-.05)>1e-12):
        raise ValueError('Worker did not apply the adopted material/environment')
    result=dict(schema='teacher60_environment_application_v1',environment_version=profile['version'],
        profile=str(path),profile_sha256=sha(path),actual_contact_material=material_signature(profile),
        actual_material_scope=override['material_scope'],worker_run_sha256=sha(output/'run.json'),
        policy_sha256=run['evaluation_checkpoint_sha256'],learning=False,hardware_executed=False,
        actual_applied=True,success=json.loads((output/'evaluation.json').read_text())['success'],count=run['num_envs'],
        paired_baseline=profile['baseline_evaluations'].get(run['split'])
            if run['seed']==profile['evaluation_seeds'][run['split']] else None)
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--profile',type=Path);p.add_argument('--output',type=Path)
    p.add_argument('--split',choices=['train','validation','test'],default='validation')
    p.add_argument('--seed',type=int);p.add_argument('--headless',action='store_true');p.add_argument('--execute',action='store_true')
    a=p.parse_args();profile,path=load_profile(a.profile)
    output=(a.output or ROOT/'outputs/harvest_rl'/f'{profile["version"]}_{a.split}_{datetime.now():%Y%m%d_%H%M%S}_{uuid.uuid4().hex[:8]}').resolve()
    if output.exists():p.error('Use a new output folder; omit --output for automatic unique output')
    command=command_for(profile,output,a.split,a.seed,a.headless,a.execute)
    print('ENVIRONMENT',profile['version'],'contact_pair_mu=1.6 finger_only; learning=False',flush=True)
    print('OUTPUT',output,flush=True)
    print('COMMAND',__import__('shlex').join(command),flush=True)
    if not a.execute:return
    env=dict(os.environ,OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',PYTHONUNBUFFERED='1')
    process=subprocess.Popen(command,cwd=ROOT,env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,bufsize=1,start_new_session=True)
    try:
        for line in process.stdout:
            if output.exists():
                with (output/'terminal.log').open('a') as log:log.write(line)
            print(line,end='',flush=True)
        if process.wait():raise RuntimeError('Evaluation failed; inspect '+str(output))
    except BaseException:
        if process.poll() is None:
            import signal
            os.killpg(process.pid,signal.SIGTERM)
            try:process.wait(timeout=15)
            except subprocess.TimeoutExpired:os.killpg(process.pid,signal.SIGKILL)
        raise
    load_profile(path)  # source/profile/evidence still pinned after evaluation
    result=bind_result(output,profile,path)
    (output/'environment_version.json').write_text(json.dumps(result,indent=2)+'\n')
    print('ENVIRONMENT_APPLIED',result['environment_version'],result['success'],'/32',flush=True)


if __name__=='__main__':main()
