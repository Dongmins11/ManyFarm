"""Train entry perception only. Default audits; --execute explicitly trains."""
import argparse,json,hashlib
from pathlib import Path
from collections import Counter
import numpy as np
import torch
from torch.utils.data import Dataset,DataLoader,WeightedRandomSampler
from harvest_rl.entry_aux import EntryAuxModel
from harvest_rl.student_bc import atomic_save,validate_sample


def observation_contract(root):
    m=json.loads((root/'dataset_manifest.json').read_text());r=json.loads((root/'run.json').read_text())
    c={k:m[k] for k in ('camera_order','camera_config','frame_id','history','control_dt','lower_rad','upper_rad','joint_names','detector_sha256','action_contract')}
    c['centre_offset_m']=m.get('centre_offset_m',.035)
    c['robot_asset_sha256']=r['current_asset']['asset_input_sha256']
    c['entry_label_version']=2
    c['entry_geometry']={k:m['experts']['runtime'][k] for k in ('diameter','length','grasp_version')}
    return c


class EntryData(Dataset):
    def __init__(self,roots):
        self.rows=[];self.seeds=set();self.contract=None;self.hashes={};self.seen=set()
        for root in roots:
            root=Path(root);c=observation_contract(root)
            if self.contract is not None and c!=self.contract:raise ValueError('Observation contract mismatch')
            self.contract=c
            if (root/'DO_NOT_TRAIN.json').exists():
                reason=json.loads((root/'DO_NOT_TRAIN.json').read_text()).get('reason')
                if reason!='Student evaluation, not expert demonstrations':raise ValueError('Quarantined data')
            for name in ('dataset_manifest.json','run.json'):
                f=root/name;self.hashes[str(f.resolve())]=hashlib.sha256(f.read_bytes()).hexdigest()
            for ep in sorted(root.glob('episode_*')):
                if not (ep/'result.json').exists():continue
                result=json.loads((ep/'result.json').read_text())
                if result['status'] not in ('SUCCEEDED','FAILED','TIMED_OUT'):continue
                meta=json.loads((ep/'metadata.json').read_text());key=(meta['seed'],meta['episode'],meta['layout']['target_color'])
                if key in self.seen:raise ValueError('Duplicate scene')
                self.seen.add(key);self.seeds.add(meta['seed']);last=-1.;identity=None
                for f in (ep/'result.json',ep/'metadata.json'):self.hashes[str(f.resolve())]=hashlib.sha256(f.read_bytes()).hexdigest()
                for i in range(result['samples']):
                    f=ep/f'{i:06d}.json';a=json.loads(f.read_text());label=a.get('entry_label')
                    if not label or label.get('version')!=2:raise ValueError('Missing entry labels: recollect; do not infer from episode success')
                    if a['stamp_s']<=last or (i and abs(a['stamp_s']-last-c['control_dt'])>1e-5):raise ValueError('Broken history clock')
                    if identity is not None and identity!=a['target']['target_id']:raise ValueError('Target switch')
                    identity=a['target']['target_id'];last=a['stamp_s']
                    with np.load(f.with_suffix('.npz'),allow_pickle=False) as z:validate_sample({k:z[k] for k in z.files})
                    for source in (f,f.with_suffix('.npz')):self.hashes[str(source.resolve())]=hashlib.sha256(source.read_bytes()).hexdigest()
                    if type(label['ready']) is not bool or type(label['usable']) is not bool:raise ValueError('Invalid label')
                    if label['usable']:self.rows.append((ep,i,int(label['ready'])))
        self.counts=Counter(y for _,_,y in self.rows)
        if set(self.counts)!={0,1}:raise ValueError(f'Need entry and non-entry examples; got {dict(self.counts)}')
    def __len__(self):return len(self.rows)
    def __getitem__(self,index):
        ep,i,y=self.rows[index];rows=[]
        for j in range(i-2,i+1):
            with np.load(ep/f'{max(0,j):06d}.npz',allow_pickle=False) as z:rows.append({k:z[k] for k in ('rgb','depth_m','camera_valid','state')})
        return {k:np.stack([r[k] for r in rows]) for k in rows[0]},y


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--train',nargs='+',type=Path,required=True);p.add_argument('--validation',nargs='+',type=Path,required=True)
    p.add_argument('--output',type=Path);p.add_argument('--execute',action='store_true');p.add_argument('--epochs',type=int,default=100);p.add_argument('--patience',type=int,default=20);p.add_argument('--batch-size',type=int,default=32);p.add_argument('--device',default='cuda:0');a=p.parse_args()
    if min(a.epochs,a.patience,a.batch_size)<1:p.error('Positive epochs/patience/batch required')
    train=EntryData(a.train);val=EntryData(a.validation)
    if train.contract!=val.contract or train.seeds & val.seeds:raise ValueError('Contract mismatch or train/validation seed leakage')
    print('ENTRY_DATA_OK',dict(train=dict(train.counts),validation=dict(val.counts)),flush=True)
    if not a.execute:print('CHECK_ONLY');return
    if a.output is None:p.error('--execute requires --output')
    a.output.mkdir(parents=True,exist_ok=False);torch.manual_seed(42);torch.set_num_threads(4)
    model=EntryAuxModel().to(a.device);opt=torch.optim.AdamW(model.parameters(),lr=1e-4)
    sampler=WeightedRandomSampler([1/train.counts[y] for _,_,y in train.rows],len(train),replacement=True)
    tl=DataLoader(train,batch_size=a.batch_size,sampler=sampler);vl=DataLoader(val,batch_size=a.batch_size)
    (a.output/'run.json').write_text(json.dumps(dict(contract=train.contract,source_hashes={**train.hashes,**val.hashes},args={k:str(v) for k,v in vars(a).items()},threshold=.95,consecutive_frames=3),indent=2))
    best=float('inf');stale=0
    with (a.output/'metrics.jsonl').open('x') as log:
        for epoch in range(1,a.epochs+1):
            model.train()
            for obs,y in tl:
                opt.zero_grad();loss=torch.nn.functional.cross_entropy(model(**{k:v.to(a.device) for k,v in obs.items()}),y.to(a.device))
                if not torch.isfinite(loss):raise ValueError('Nonfinite loss')
                loss.backward();torch.nn.utils.clip_grad_norm_(model.parameters(),1);opt.step()
            model.eval();sums=[0.,0.];counts=[0,0];tp=fp=tn=fn=0
            with torch.inference_mode():
                for obs,y in vl:
                    logits=model(**{k:v.to(a.device) for k,v in obs.items()});losses=torch.nn.functional.cross_entropy(logits,y.to(a.device),reduction='none').cpu();pred=logits.softmax(-1)[:,1].cpu()>=.95
                    for c in (0,1):sums[c]+=float(losses[y==c].sum());counts[c]+=int((y==c).sum())
                    tp+=int((pred & (y==1)).sum());fp+=int((pred & (y==0)).sum());tn+=int((~pred & (y==0)).sum());fn+=int((~pred & (y==1)).sum())
            score=sum(sums[c]/counts[c] for c in (0,1))/2
            row=dict(epoch=epoch,balanced_validation_ce=score,tp=tp,fp=fp,tn=tn,fn=fn,precision=tp/max(1,tp+fp),recall=tp/max(1,tp+fn),false_positive_rate=fp/max(1,fp+tn))
            print('ENTRY_EPOCH',row,flush=True);log.write(json.dumps(row)+'\n');log.flush()
            payload=dict(kind='entry_aux_v1',model=model.state_dict(),contract=train.contract,epoch=epoch,metrics=row)
            atomic_save(payload,a.output/'entry_last.pt')
            if score<best:best=score;stale=0;atomic_save(payload,a.output/'entry_best.pt')
            else:stale+=1
            if stale>=a.patience:break
    print('ENTRY_COMPLETE: shadow evaluation required before any motion gating',flush=True)
if __name__=='__main__':main()
