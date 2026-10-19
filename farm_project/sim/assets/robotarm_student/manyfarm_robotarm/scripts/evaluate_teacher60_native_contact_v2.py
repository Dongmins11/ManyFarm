"""Uniform96-scene full-chain comparison; no learning or automatic adoption."""
import argparse
from datetime import datetime
import json
from pathlib import Path
import subprocess
import sys
import uuid

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src/harvest_robot'))
BASELINE=ROOT/'outputs/harvest_rl/floor_unified_full_20261012_r1'


def compare(base,new):
    ar,br=[json.loads((p/'run.json').read_text()) for p in (base,new)]
    ae,be=[json.loads((p/'evaluation.json').read_text()) for p in (base,new)]
    if not ar.get('completed') or not br.get('completed') or ar['learning'] or br['learning']:
        raise ValueError('Completed read-only pair required')
    for key in ('task','split','seed','grasp_checkpoint','settle_compliance','posture_comparison',
                'floor_collision_override','transport_speed_m_s','orientation_length_m',
                'opening_rate_rad_s','deposit_timeout_s'):
        if ar[key]!=br[key]:raise ValueError('More than native policy changed: '+key)
    if ar['pull_stability']['mode']!=br['pull_stability']['mode']:
        raise ValueError('Pause mode changed')
    if json.loads((base/'initial_samples.json').read_text())!=json.loads((new/'initial_samples.json').read_text()):
        raise ValueError('Uniform assigned scenes differ')
    if ae['count']!=32 or be['count']!=32:raise ValueError('Incomplete pair')
    sa={e['trial_id'] for e in ae['episodes'] if e['success']}
    sb={e['trial_id'] for e in be['episodes'] if e['success']}
    return dict(split=ar['split'],count=32,baseline_success=len(sa),new_success=len(sb),
        recovered_ids=sorted(sb-sa),regressed_ids=sorted(sa-sb),
        remaining_failed_ids=sorted(set(range(32))-sb),baseline=str(base),evaluation=str(new))


def main():
    p=argparse.ArgumentParser(description=__doc__)
    source=p.add_mutually_exclusive_group(required=True)
    source.add_argument('--checkpoint',type=Path)
    source.add_argument('--latest',action='store_true',help='Use completed pointer written by the new training wrapper')
    p.add_argument('--splits',nargs='+',choices=['train','validation','test'],default=['train','validation','test'])
    p.add_argument('--output',type=Path);p.add_argument('--execute',action='store_true');a=p.parse_args()
    if a.latest:
        pointer=ROOT/'outputs/harvest_rl/native_contact_v2_last_train.json'
        if not pointer.is_file():p.error('No completed native-contact training pointer')
        saved=json.loads(pointer.read_text());a.checkpoint=Path(saved['checkpoint'])
        from harvest_rl.teacher_asset_reference import sha
        if sha(a.checkpoint)!=saved['checkpoint_sha256'] or sha(a.checkpoint.parent/'run.json')!=saved['run_sha256']:
            p.error('Latest training pointer changed')
    if not a.checkpoint.is_file():p.error('Checkpoint does not exist')
    out=(a.output or ROOT/'outputs/harvest_rl'/f'native_contact_v2_full_{datetime.now():%Y%m%d_%H%M%S}_{uuid.uuid4().hex[:8]}').resolve()
    if out.exists():p.error('Use a new output folder or omit --output')
    print('CONTACT_CHAIN_PLAN',a.checkpoint,out,a.splits,'learning=False,hardware=False',flush=True)
    if not a.execute:return
    # Source/model verification occurs before simulator startup in each child.
    out.mkdir(parents=True);results=[]
    (out/'orchestrator_source.py').write_bytes(Path(__file__).read_bytes())
    for split in a.splits:
        cmd=[sys.executable,'-u',str(ROOT/'scripts/eval_teacher60_native_contact_v2_chain.py'),
             '--checkpoint',str(a.checkpoint.resolve()),'--policy-role','trained','--split',split,
             '--pressure-reference',str(BASELINE/split),'--output',str(out/split),'--headless','--execute']
        print('START_CHAIN',split,flush=True)
        with (out/(split+'.log')).open('x') as log:
            child=subprocess.Popen(cmd,cwd=ROOT,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,bufsize=1)
            try:
                for line in child.stdout:
                    log.write(line);log.flush();print(line,end='',flush=True)
                code=child.wait()
            except BaseException:
                child.terminate();child.wait();raise
        if code:raise RuntimeError('Evaluation failed; inspect '+str(out/(split+'.log')))
        result=compare(BASELINE/split,out/split);results.append(result)
        (out/'partial_comparison.json').write_text(json.dumps(results,indent=2)+'\n')
        print('CONTACT_CHAIN_RESULT',json.dumps(result),flush=True)
    report=dict(completed=True,learning=False,hardware_executed=False,production_selection_changed=False,
        comparisons=results,count=32*len(results),baseline_success=sum(r['baseline_success'] for r in results),
        new_success=sum(r['new_success'] for r in results))
    (out/'comparison.json').write_text(json.dumps(report,indent=2)+'\n')
    print('CONTACT_CHAIN_COMPLETE',json.dumps(report),flush=True)


if __name__=='__main__':main()
