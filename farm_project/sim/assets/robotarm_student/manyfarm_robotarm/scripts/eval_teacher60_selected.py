"""Live, uniquely named full harvest evaluation of the selected inference revision."""
import argparse
from datetime import datetime
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import uuid
from zoneinfo import ZoneInfo

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src/harvest_robot'))
from harvest_rl.friction_selected import load_selected,bind_selected
from harvest_rl.environment_version import rooted


def command_for(profile,environment,output,split,seed,headless,execute):
    cmd=[os.environ.get('HARVEST_PY','/home/bhc/isaac/env_isaaclab/bin/python'),'-u',str(ROOT/profile['worker']),
        '--checkpoint',str(rooted(environment['policies']['native']['path'])),
        '--effective-friction','1.6','--bridge-velocity-cap','0.15','--bridge-rate','6',
        '--transport-mode','progress_budget','--split',split,'--output',str(output)]
    if seed is not None:cmd+=['--seed',str(seed)]
    if headless:cmd+=['--headless']
    if execute:cmd+=['--execute']
    return cmd


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--profile',type=Path);p.add_argument('--output',type=Path)
    p.add_argument('--split',choices=['train','validation','test'],default='validation')
    p.add_argument('--seed',type=int);p.add_argument('--headless',action='store_true');p.add_argument('--execute',action='store_true')
    a=p.parse_args();profile,path,environment=load_selected(a.profile)
    stamp=datetime.now(ZoneInfo('Asia/Seoul')).strftime('%Y%m%d_%H%M%S')
    output=(a.output or ROOT/'outputs/harvest_rl'/f'{profile["version"]}_{a.split}_{stamp}_{uuid.uuid4().hex[:8]}').resolve()
    if output.exists():p.error('Omit --output to get an automatic unique folder')
    command=command_for(profile,environment,output,a.split,a.seed,a.headless,a.execute)
    print('SELECTED_ENVIRONMENT',profile['version'],'learning=False',flush=True)
    print('OUTPUT',output,flush=True);print('COMMAND',shlex.join(command),flush=True)
    if not a.execute:return
    subprocess.run(command,cwd=ROOT,env=dict(os.environ,OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',PYTHONUNBUFFERED='1'),check=True)
    load_selected(path)
    result=bind_selected(output,profile,path,environment)
    (output/'selected_runtime.json').write_text(json.dumps(result,indent=2)+'\n')
    print('SELECTED_FULL_HARVEST_COMPLETE',result['success'],'/',result['count'],flush=True)


if __name__=='__main__':main()
