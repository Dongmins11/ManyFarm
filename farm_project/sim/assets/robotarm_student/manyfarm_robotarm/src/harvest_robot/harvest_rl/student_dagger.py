"""Dedicated, success-qualified approach DAgger audit. Standard BC remains strict."""
from pathlib import Path
from collections import Counter
import numpy as np
import torch
from .student_bc import read,digest,validate_sample,input_contract,verify_prepared,BCDataset

QUARANTINE='DAgger recovery collection; dedicated audit required, never standard BC'


def prepare_dagger(base, roots):
    verify_prepared(base)
    heldout={170,171,182,183,282,283}|{e['seed'] for e in base['validation']}
    seen=set();episodes=[];skipped=[];files={}
    for root in roots:
        root=Path(root).resolve()
        if str(root) in seen:raise ValueError('Duplicate DAgger root')
        seen.add(str(root));m=read(root/'dataset_manifest.json')
        if m.get('smoke_test_only'):raise ValueError('Untrained plumbing probe is not approved Student DAgger data')
        if read(root/'DO_NOT_TRAIN.json').get('reason')!=QUARANTINE:raise ValueError('Unexpected quarantine / OOM; cannot approve')
        if m.get('dagger_schema')!='approach_oracle_v1' or m.get('capture_contract')!='synchronised_rgbd_v1':raise ValueError('Missing DAgger capture evidence')
        if input_contract(root)!=base['contract']:raise ValueError('DAgger/base input or Teacher contract mismatch')
        for name in ('dataset_manifest.json','run.json','DO_NOT_TRAIN.json'):files[str(root/name)]=digest(root/name)
        for folder in sorted(root.glob('episode_*')):
            if not (folder/'result.json').exists():continue
            outcome=read(folder/'result.json');d=outcome.get('diagnostics',{}).get('dagger') or {}
            if outcome['status']!='SUCCEEDED' or not d.get('recovery_succeeded') or not d.get('recovery_eligible'):
                skipped.append(dict(path=str(folder),reason='recovery_not_qualified'));continue
            meta=read(folder/'metadata.json');count=d['prefix_frames']
            if meta['seed'] in heldout:raise ValueError('Held-out seed in DAgger training')
            if type(count)!=int or not 0<=count<=outcome['samples']:raise ValueError('Invalid prefix length')
            if count<3:
                skipped.append(dict(path=str(folder),reason='insufficient_approach_prefix',prefix_frames=count));continue
            evidence={str(folder/name):digest(folder/name) for name in ('result.json','metadata.json')}
            previous=np.zeros(6,np.float32);identity=None;student_frames=0
            for i in range(count):
                path=folder/f'{i:06d}.npz';ann=path.with_suffix('.json');a=read(ann);label=a.get('dagger') or {}
                with np.load(path,allow_pickle=False) as z:row={k:z[k] for k in z.files}
                validate_sample(row)
                if not row['camera_valid'].all() or any(np.ptp(x)==0 for x in row['rgb']):raise ValueError('Missing/blank DAgger camera')
                if not row['state'][21] or not label.get('eligible') or not label.get('attached') or label.get('confirmed'):raise ValueError('Invalid approach label state')
                if label.get('schema')!='approach_oracle_v1' or label.get('label_source')!='readonly_entry_oracle':raise ValueError('Wrong oracle')
                executed=np.asarray(label.get('executed_action'),np.float32)
                if executed.shape!=(6,) or not np.isfinite(executed).all() or np.any(abs(executed)>1):raise ValueError('Invalid executed action')
                if not np.allclose(row['action'],label.get('label_action'),atol=1e-6):raise ValueError('Teacher label mismatch')
                if not np.allclose(row['state'][12:18],previous,atol=1e-6):raise ValueError('Previous action must be actual executed command')
                if abs(a['stamp_s']-i*m['control_dt'])>1e-5:raise ValueError('Non-contiguous DAgger history')
                target=a['target']['target_id']
                if not target or (identity is not None and target!=identity):raise ValueError('Target changed')
                source=label.get('executed_source')
                if source not in ('student','entry_oracle'):raise ValueError('Unknown executed source')
                student_frames+=int(source=='student');identity=target;previous=executed
                evidence[str(path)]=digest(path);evidence[str(ann)]=digest(ann)
            if not student_frames:
                skipped.append(dict(path=str(folder),reason='no_student_states'));continue
            episodes.append(dict(path=str(folder),seed=meta['seed'],episode=meta['episode'],color=meta['layout']['target_color'],
                samples=count,stages=[-1]*count,student_frames=student_frames,files=evidence))
    keys=[(e['seed'],e['episode'],e['color']) for e in episodes]
    if len(keys)!=len(set(keys)):raise ValueError('Repeated DAgger scene')
    if not episodes:raise ValueError('No success-qualified DAgger approach recoveries')
    return dict(schema='approved_approach_dagger_v1',contract=base['contract'],train=episodes,files=files,skipped=skipped,
        summary=dict(episodes=len(episodes),frames=sum(e['samples'] for e in episodes)))


def verify_dagger(plan, base):
    if plan.get('schema')!='approved_approach_dagger_v1' or plan['contract']!=base['contract']:raise ValueError('DAgger contract mismatch')
    files=dict(plan['files'])
    for e in plan['train']:files.update(e['files'])
    for path,expected in files.items():
        if digest(path)!=expected:raise ValueError('DAgger data changed after audit')


def mixed_weights(base_dataset, dagger_dataset, approach_weight, fraction):
    """Fraction applies within approach; pull/transport/place only use original BC."""
    if not 0<fraction<=.5:raise ValueError('Recovery fraction must be in (0,.5]')
    counts=Counter(s for _,_,s in base_dataset.rows)
    if -1 not in counts or not dagger_dataset.rows:raise ValueError('Missing approach samples')
    baseline=[(approach_weight*(1-fraction) if s==-1 else 1.)/counts[s] for _,_,s in base_dataset.rows]
    recovery=[approach_weight*fraction/len(dagger_dataset)]*len(dagger_dataset)
    return torch.tensor(baseline+recovery,dtype=torch.double)
