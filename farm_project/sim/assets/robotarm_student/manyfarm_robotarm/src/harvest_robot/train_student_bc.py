"""Offline supervised BC; default validates only, --execute explicitly starts learning."""
import argparse,json,time
from pathlib import Path
import torch
from torch.utils.data import DataLoader,WeightedRandomSampler,ConcatDataset
from harvest_rl.student_v2 import DualRGBDStudent
from harvest_rl.student_bc import BCDataset,verify_prepared,digest,evaluate,action_loss,atomic_save


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--data',type=Path,required=True);p.add_argument('--output',type=Path)
    p.add_argument('--execute',action='store_true');p.add_argument('--resume',type=Path)
    p.add_argument('--initialize',type=Path,help='Start new BC/DAgger optimizer from same-contract Student weights')
    p.add_argument('--dagger-data',type=Path,help='Separately audited approach recovery plan')
    p.add_argument('--dagger-fraction',type=float,default=.25)
    p.add_argument('--augmentation-profile',type=Path,help='Opt-in measured/provisional observation-shift JSON; labels and physics stay unchanged')
    p.add_argument('--require-current-observations',action='store_true',help='Reject data from older robot/camera/background revisions')
    p.add_argument('--epochs',type=int,default=100);p.add_argument('--batch-size',type=int,default=32)
    p.add_argument('--workers',type=int,default=2);p.add_argument('--learning-rate',type=float,default=1e-4)
    p.add_argument('--approach-weight',type=float,default=1.,help='Relative approach sampling weight; other stages weight 1')
    p.add_argument('--patience',type=int,default=20);p.add_argument('--seed',type=int,default=42)
    p.add_argument('--device',default='cuda:0');a=p.parse_args()
    if min(a.epochs,a.batch_size,a.patience)<=0 or a.workers<0 or not 0<a.learning_rate<1: p.error('Invalid training parameters')
    if not 0<a.approach_weight<=10: p.error('--approach-weight must be in (0,10]')
    plan=json.loads(a.data.read_text());verify_prepared(plan);fingerprint=digest(a.data)
    input_version=plan['contract'].get('student_schema_version',2)
    if input_version not in (2,3):p.error('Unsupported Student input version')
    if input_version==3 and (a.augmentation_profile or a.dagger_data):p.error('v3 requires a separately measured IR augmentation/DAgger contract')
    augmentation=None;augmentation_config=None
    if a.require_current_observations:
        from harvest_rl.student_readiness import require_current_observations
        require_current_observations(plan['contract'])
        print('CURRENT_OBSERVATIONS_OK',flush=True)
    if a.augmentation_profile:
        from harvest_rl.student_augmentation import load_profile,ObservationShift,validate_latency_metadata
        augmentation,augmentation_config=load_profile(a.augmentation_profile)
        camera=plan['contract']['camera_config']
        if augmentation['depth_min_m']!=camera.get('depth_min_m') or augmentation['depth_max_m']!=camera.get('depth_max_m'):
            raise ValueError('Augmentation depth validity must match recorded camera contract')
        if augmentation['camera_delay_steps_max']:
            if plan['contract'].get('observation_geometry_schema')!='arm_tcp_v1':
                raise ValueError('Delay requires new synchronized measured TCP annotations; recollect')
            validate_latency_metadata(plan['train']+plan['validation'])
        print('OBSERVATION_SHIFT_CHECK_OK',json.dumps(augmentation_config),flush=True)
    dagger_plan=None
    if a.resume and a.initialize:p.error('Choose resume or new initialized training')
    if a.dagger_data:
        from harvest_rl.student_dagger import verify_dagger,mixed_weights
        dagger_plan=json.loads(a.dagger_data.read_text());verify_dagger(dagger_plan,plan)
        if not 0<a.dagger_fraction<=.5:p.error('DAgger fraction must be in (0,.5]')
        if augmentation and augmentation['camera_delay_steps_max']:validate_latency_metadata(dagger_plan['train'])
        print('DAGGER_CHECK_OK',dagger_plan['summary'],flush=True)
    print('DATA_CHECK_OK',json.dumps(plan['summary']),flush=True)
    for message in plan['warnings']: print('DATA_WARNING',message,flush=True)
    if not a.execute: print('CHECK_ONLY: add --execute --output <new directory> to train');return
    if a.output is None: p.error('--execute requires --output')
    torch.set_num_threads(4);torch.manual_seed(a.seed)
    if a.device.startswith('cuda') and not torch.cuda.is_available(): raise RuntimeError('CUDA unavailable; select --device cpu explicitly')
    if input_version==3:
        from harvest_rl.student_v3 import MultimodalStudent
        model=MultimodalStudent().to(a.device)
    else:model=DualRGBDStudent().to(a.device)
    optimizer=torch.optim.AdamW(model.parameters(),lr=a.learning_rate,weight_decay=1e-4)
    generator=torch.Generator().manual_seed(a.seed);start=0;best=float('inf');stale=0
    config=dict(batch_size=a.batch_size,learning_rate=a.learning_rate,seed=a.seed,stage_balanced=True)
    if augmentation_config:config['observation_augmentation']=augmentation_config
    if dagger_plan:config.update(dagger_sha256=digest(a.dagger_data),dagger_fraction=a.dagger_fraction)
    if a.approach_weight!=1.:config['approach_weight']=a.approach_weight
    if a.initialize:
        saved=torch.load(a.initialize,map_location='cpu',weights_only=True)
        if saved.get('input_contract')!=plan['contract']:raise ValueError('Initialization input/runtime mismatch; no silent 35g to 9g transfer')
        model.load_state_dict(saved['student'],strict=True)
    if a.resume:
        saved=torch.load(a.resume,map_location='cpu',weights_only=True)
        if saved['data_sha256']!=fingerprint or saved['training_config']!=config or saved['schema_version']!=input_version:
            raise ValueError('Resume data/config mismatch; epochs may increase, other settings must match')
        model.load_state_dict(saved['student']);optimizer.load_state_dict(saved['optimizer'])
        generator.set_state(saved['sampler_rng']);torch.set_rng_state(saved['torch_rng'])
        if a.device.startswith('cuda') and saved.get('cuda_rng'):torch.cuda.set_rng_state_all(saved['cuda_rng'])
        start=saved['epoch'];best=saved['best_macro_mse'];stale=saved['stale_epochs']
        if start>=a.epochs: raise ValueError('--epochs is total target epochs and must exceed resumed epoch')
    a.output.mkdir(parents=True,exist_ok=False)
    (a.output/'run.json').write_text(json.dumps(dict(args={k:str(v) if isinstance(v,Path) else v for k,v in vars(a).items()},
        data_sha256=fingerprint,contract=plan['contract'],summary=plan['summary'],training_config=config),indent=2))
    shift=ObservationShift(augmentation,a.seed,plan['contract']['control_dt']) if augmentation else None
    train=BCDataset(plan['train'],shift);validation=BCDataset(plan['validation'])
    shifted_loader=None
    if augmentation:
        # Fixed held-out perturbations; never change the clean best-checkpoint criterion.
        validation_shift=ObservationShift(augmentation,a.seed+1000003,plan['contract']['control_dt'])
        shifted_loader=DataLoader(BCDataset(plan['validation'],validation_shift),batch_size=a.batch_size,
            shuffle=False,num_workers=a.workers,persistent_workers=a.workers>0)
    weights=train.weights()
    weights*=torch.tensor([a.approach_weight if stage==-1 else 1. for _,_,stage in train.rows],dtype=weights.dtype)
    if dagger_plan:
        recovery=BCDataset(dagger_plan['train'],shift)
        weights=mixed_weights(train,recovery,a.approach_weight,a.dagger_fraction)
        train=ConcatDataset([train,recovery])
    sampler=WeightedRandomSampler(weights,len(train),replacement=True,generator=generator)
    train_loader=DataLoader(train,batch_size=a.batch_size,sampler=sampler,num_workers=a.workers,persistent_workers=a.workers>0)
    val_loader=DataLoader(validation,batch_size=a.batch_size,shuffle=False,num_workers=a.workers,persistent_workers=a.workers>0)
    if a.resume:
        # Preserve the previous best even when no further epoch improves it.
        previous_best=a.resume.parent/'student_best.pt'
        if not previous_best.exists(): raise ValueError('Resume requires sibling student_best.pt')
        old=torch.load(previous_best,map_location='cpu',weights_only=True)
        if old['data_sha256']!=fingerprint: raise ValueError('Best checkpoint data mismatch')
        atomic_save(old,a.output/'student_best.pt')
    with (a.output/'metrics.jsonl').open('x') as log:
        for epoch in range(start+1,a.epochs+1):
            if shift:shift.set_epoch(epoch)
            began=time.monotonic();model.train();loss_sum=0.;count=0
            for step,(obs,label,_) in enumerate(train_loader,1):
                optimizer.zero_grad(set_to_none=True)
                prediction=model(**{k:v.to(a.device) for k,v in obs.items()});loss=action_loss(prediction,label.to(a.device))
                if not torch.isfinite(loss): raise FloatingPointError('Non-finite BC loss')
                loss.backward();torch.nn.utils.clip_grad_norm_(model.parameters(),1.);optimizer.step()
                loss_sum+=loss.item()*len(label);count+=len(label)
                if step%20==0: print(f'BC epoch={epoch} batch={step}/{len(train_loader)} mse={loss_sum/count:.6f}',flush=True)
            metrics=evaluate(model,val_loader,a.device);improved=metrics['macro_mse']<best
            if improved: best=metrics['macro_mse'];stale=0
            else: stale+=1
            record=dict(epoch=epoch,train_mse=loss_sum/count,validation=metrics,best_macro_mse=best,seconds=time.monotonic()-began)
            if shifted_loader:record['validation_observation_shift']=evaluate(model,shifted_loader,a.device)
            record['seconds']=time.monotonic()-began
            log.write(json.dumps(record)+'\n');log.flush();print('BC_EPOCH',json.dumps(record),flush=True)
            payload=dict(schema_version=input_version,camera_order=['right','rear'],student=model.state_dict(),optimizer=optimizer.state_dict(),
                epoch=epoch,best_macro_mse=best,stale_epochs=stale,data_sha256=fingerprint,training_config=config,
                input_contract=plan['contract'],sampler_rng=generator.get_state(),torch_rng=torch.get_rng_state(),
                cuda_rng=torch.cuda.get_rng_state_all() if a.device.startswith('cuda') else [])
            atomic_save(payload,a.output/'student_last.pt')
            if improved: atomic_save(payload,a.output/'student_best.pt')
            if stale>=a.patience: print('EARLY_STOP: validation did not improve',flush=True);break
    print('BC_COMPLETE',a.output/'student_best.pt','Offline action error is NOT harvest success rate.',flush=True)
if __name__=='__main__':main()
