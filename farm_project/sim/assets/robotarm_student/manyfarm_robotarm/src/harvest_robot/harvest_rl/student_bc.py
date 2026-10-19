"""Audited offline BC for dual-camera v2. No simulator, ROS, or motor imports."""
import hashlib
import json
from collections import Counter
from pathlib import Path
import numpy as np
import torch
from torch.utils.data import Dataset

STAGES=(-1,0,1,2)
FIELDS={'rgb','depth_m','camera_valid','state','action'}


def digest(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def read(path): return json.loads(Path(path).read_text())


def validate_sample(row):
    specs={'rgb':((2,90,160,3),np.uint8),'depth_m':((2,90,160),np.float32),
           'camera_valid':((2,),np.bool_),'state':((23,),np.float32),'action':((6,),np.float32)}
    fields=FIELDS
    if 'wrist_ir_right' in row:
        fields=FIELDS|{'wrist_ir_right','wrist_ir_valid'}
        specs.update(wrist_ir_right=((90,160),np.uint8),wrist_ir_valid=((),np.bool_))
        if np.any(row['depth_m'][0]!=0):raise ValueError('Student v3 excludes wrist depth')
    if set(row)!=fields: raise ValueError('Unexpected sample fields / privileged inputs')
    for k,(shape,dtype) in specs.items():
        if row[k].shape!=shape or row[k].dtype!=dtype: raise ValueError(f'Bad {k} shape/dtype')
        if not np.isfinite(row[k]).all(): raise ValueError(f'Non-finite {k}')
    s=row['state']
    if np.any(abs(row['action'])>1.00001) or np.any(row['depth_m']<0) or np.any(row['depth_m']>3): raise ValueError('Action/depth range')
    if s[21] not in (0,1) or not 0<=s[22]<=.30001: raise ValueError('Target validity/age')
    if s[21]==0 and np.any(s[18:21]!=0): raise ValueError('Invalid target must have zero XYZ')


def canonical_teacher_runtime(runtime):
    # These opt-in guards were absent in older manifests and default to False.
    # Do not ignore other fields or collapse enabled guards into legacy behavior.
    result={k:v for k,v in runtime.items() if k!='seed'}
    for key in ('detached_capture_orientation','post_detach_hold_guard'):
        result.setdefault(key,False)
    result.setdefault('entry_capture_shaping',False)
    return result


def input_contract(root):
    """Contract extraction only; callers must independently audit data eligibility."""
    root=Path(root);m=read(root/'dataset_manifest.json')
    contract={k:m[k] for k in ('camera_order','camera_config','frame_id','history','control_dt','lower_rad','upper_rad','joint_names','detector_sha256','action_contract')}
    contract['centre_offset_m']=m.get('centre_offset_m',.035)
    if m.get('capture_contract')=='physics_scheduled_multimodal_v3':
        contract.update(student_schema_version=3,capture_contract=m['capture_contract'],sensor_dt=m['sensor_dt'],timing_contract=m['timing_contract'])
    # Appearance revisions are provenance, not privileged network inputs. Older
    # datasets remain readable, but cannot silently mix with new greenhouse RGB.
    if 'visual_scene' in m:
        contract['visual_scene_sha256']=m['visual_scene'].get('sha256','legacy_unversioned')
    if 'observation_geometry_schema' in m:contract['observation_geometry_schema']=m['observation_geometry_schema']
    if 'initial_target_workspace' in m:contract['initial_target_workspace']=m['initial_target_workspace']
    asset=read(root/'run.json')['current_asset']
    contract['robot_asset_sha256']=asset['asset_input_sha256']
    if 'sensor_mount_reference_urdf_sha256' in asset:
        contract['sensor_mount_reference_urdf_sha256']=asset['sensor_mount_reference_urdf_sha256']
    if 'deployment_arm_appearance_sha256' in asset:
        contract['deployment_arm_appearance_sha256']=asset['deployment_arm_appearance_sha256']
    contract['teacher_runtime']=canonical_teacher_runtime(m['experts']['runtime'])
    contract['action_execution']=m['experts'].get('action_execution',{'version':0,'labels':'legacy_unspecified'})
    for k in ('checkpoint','grasp_expert','transport_expert','place_expert'):contract[k]=m[k]['sha256']
    return contract


def audit_root(root):
    root=Path(root).resolve()
    if (root/'DO_NOT_TRAIN.json').exists(): raise ValueError(f'Quarantined dataset: {root}')
    m=read(root/'dataset_manifest.json')
    if m.get('dagger_schema') or m.get('evaluation_only'):raise ValueError('Evaluation/DAgger data require separate approval; not ordinary BC')
    deployment=m.get('capture_contract')=='physics_scheduled_multimodal_v3'
    verified=(m.get('capture_contract') in ('synchronised_rgbd_v1','physics_scheduled_multimodal_v3'))
    if deployment:
        from harvest_sensors.deployment import validate_deployment
        validate_deployment(m['camera_config'])
        if not np.isclose(m['control_dt'],.05) or not np.isclose(m['sensor_dt'],1/30):
            raise ValueError('Deployment manifest clock mismatch')
        timing=m['timing_contract']
        from harvest_sensors.deployment import PhysicsCaptureClock
        clock=PhysicsCaptureClock(timing['physics_dt'],m['control_dt'])
        if timing['camera_hz']!=30 or timing['policy_hz']!=20 or timing['capture_stride_physics']!=clock.stride:
            raise ValueError('Deployment physics timing contract mismatch')
    v=root/'verification.json'
    if v.exists(): verified |= read(v).get('max_camera_fk_matrix_error',1)<2e-4
    if not verified: raise ValueError(f'Missing synchronized capture evidence: {root}; recollect')
    if m.get('schema_version')!=(3 if deployment else 2) or m.get('camera_order')!=['right','rear'] or m.get('history')!=3:
        raise ValueError('Require matching Student input version')
    contract=input_contract(root)
    episodes=[];skipped=[]
    for folder in sorted(root.glob('episode_*')):
        result=folder/'result.json'
        if not result.exists(): skipped.append(dict(path=str(folder),reason='unfinished'));continue
        outcome=read(result)
        if outcome['status']!='SUCCEEDED': skipped.append(dict(path=str(folder),reason=outcome['status']));continue
        meta=read(folder/'metadata.json');count=outcome['samples']
        if not isinstance(count,int) or count<1: raise ValueError('Empty successful episode')
        if deployment:
            from harvest_sensors.deployment import audit_raw_captures
            audit_raw_captures(folder,m,read(root/'run.json'))
        if len(list(folder.glob('*.npz')))!=count: raise ValueError(f'Incomplete/extra samples: {folder}')
        files={};stages=[];valid=0;identity=None;last=-1.;stage_last=-1;previous=None
        for p in (result,folder/'metadata.json'): files[str(p)]=digest(p)
        for i in range(count):
            path=folder/f'{i:06d}.npz';annotation=path.with_suffix('.json')
            with np.load(path,allow_pickle=False) as z:
                row={k:z[k] for k in z.files};validate_sample(row);valid+=int(row['state'][21])
                if deployment and ('wrist_ir_right' not in row or not row['wrist_ir_valid']):raise ValueError('Missing wrist right IR')
                if not row['camera_valid'].all(): raise ValueError('Missing camera frame')
                # A fully blank camera is a rendering failure, not useful black padding.
                if any(np.ptp(x)==0 for x in row['rgb']): raise ValueError(f'Blank RGB: {path}')
            a=read(annotation);stage=a['expert_stage'];stamp=a['stamp_s']
            if deployment:
                from harvest_sensors.deployment import audit_camera_sample
                audit_camera_sample(a,m['control_dt'],previous)
                for c in a['cameras'].values():
                    raw=Path(c['raw_capture'])
                    if not raw.resolve().is_relative_to(folder.resolve()) or not raw.is_file():
                        raise ValueError('Missing/outside original camera data')
                    files[str(raw)]=digest(raw);files[str(raw.with_suffix('.json'))]=digest(raw.with_suffix('.json'))
                previous=a
            if stage not in STAGES or stage<stage_last: raise ValueError('Invalid/non-monotonic expert stage')
            if not np.isfinite(stamp) or stamp<=last: raise ValueError('Non-monotonic timestamp')
            if i and abs(stamp-last-m['control_dt'])>1e-5: raise ValueError('Missing frame / incorrect time step')
            target=a['target']['target_id']
            if not target or (identity is not None and identity!=target): raise ValueError('Target switch inside episode')
            identity=target;last=stamp;stage_last=stage;stages.append(stage)
            files[str(path)]=digest(path);files[str(annotation)]=digest(annotation)
        if deployment:
            for raw in sorted((folder/'raw_captures').rglob('*')):
                if raw.is_file():files[str(raw)]=digest(raw)
        if set(stages)!=set(STAGES):
            skipped.append(dict(path=str(folder),reason='success_missing_harvest_stages',missing=sorted(set(STAGES)-set(stages))))
            continue
        episodes.append(dict(path=str(folder),seed=meta['seed'],episode=meta['episode'],
                             color=meta['layout']['target_color'],samples=count,stages=stages,
                             target_valid_frames=valid,files=files))
    evidence={str(root/name):digest(root/name) for name in ('dataset_manifest.json','run.json')}
    if v.exists(): evidence[str(v)]=digest(v)
    return contract,episodes,skipped,evidence


def prepare(train_roots, val_roots):
    result=dict(schema_version=2,train=[],validation=[],skipped=[],files={});reference=None
    seen=set()
    for split,roots in [('train',train_roots),('validation',val_roots)]:
        for root in roots:
            root=str(Path(root).resolve())
            role=read(Path(root)/'dataset_manifest.json').get('split_role')
            if role is not None and role!=split:raise ValueError('Reviewed dataset split role mismatch / development-only data')
            if root in seen: raise ValueError('Repeated dataset root')
            seen.add(root)
            contract,episodes,skipped,files=audit_root(root)
            if reference is None: reference=contract
            if contract!=reference: raise ValueError('Incompatible sensor/normalization/teacher contract')
            result[split].extend(episodes);result['skipped'].extend(skipped);result['files'].update(files)
    for split in ('train','validation'):
        if not result[split]: raise ValueError(f'No successful {split} episodes')
        keys=[(e['seed'],e['episode'],e['color']) for e in result[split]]
        if len(keys)!=len(set(keys)): raise ValueError('Duplicate scene provenance')
    if {e['seed'] for e in result['train']} & {e['seed'] for e in result['validation']}:
        raise ValueError('Train/validation seed overlap; recollect separate seeds')
    if any(e['seed'] in {170,171,182,183,282,283} for e in result['train']):
        raise ValueError('Reserved validation/development seed in training')
    result['contract']=reference
    result['schema_version']=reference.get('student_schema_version',2)
    result['summary']={split:dict(episodes=len(result[split]),frames=sum(e['samples'] for e in result[split]),
        colors=dict(Counter(e['color'] for e in result[split])),
        stages=dict(Counter(str(s) for e in result[split] for s in e['stages']))) for split in ('train','validation')}
    result['warnings']=[]
    if len(result['train'])<50: result['warnings'].append('Fewer than 50 successful training episodes: pilot dataset, not a readiness guarantee')
    if len(result['validation'])<10: result['warnings'].append('Fewer than 10 successful validation episodes: noisy validation')
    for split in ('train','validation'):
        if {e['color'] for e in result[split]}!={'Red','Yellow'}: result['warnings'].append(f'{split}: both target colors not represented')
    return result


def verify_prepared(plan):
    files=dict(plan['files'])
    for split in ('train','validation'):
        for e in plan[split]:
            if (Path(e['path']).parent/'DO_NOT_TRAIN.json').exists(): raise ValueError('Dataset was quarantined')
            files.update(e['files'])
    for path,expected in files.items():
        if digest(path)!=expected: raise ValueError(f'Data changed after preparation: {path}')


class BCDataset(Dataset):
    def __init__(self, episodes, augmentation=None):
        self.augmentation=augmentation
        self.rows=[(Path(e['path']),i,stage) for e in episodes for i,stage in enumerate(e['stages'])]
    def __len__(self): return len(self.rows)
    def __getitem__(self,index):
        root,i,stage=self.rows[index];indices=[max(0,j) for j in range(i-2,i+1)]
        def load(j):
            with np.load(root/f'{j:06d}.npz',allow_pickle=False) as a:return {k:a[k] for k in a.files}
        history=[load(j) for j in indices]
        keys=('rgb','depth_m','camera_valid','state')
        if 'wrist_ir_right' in history[0]:
            keys+=('wrist_ir_right','wrist_ir_valid')
            if self.augmentation is not None:raise ValueError('Multimodal augmentation requires measured IR contract; disabled')
        obs={k:np.stack([r[k] for r in history]) for k in keys}
        if self.augmentation is not None:
            delay=self.augmentation.delay(str(root));source=[max(0,j-delay) for j in indices]
            delayed=[load(j) for j in source] if delay else history
            sensor={k:np.stack([r[k] for r in delayed]) for k in keys}
            tcp_current=tcp_sensor=None
            if delay:
                from .student_augmentation import tcp_metadata
                tcp_current=[tcp_metadata(root/f'{j:06d}.json') for j in indices]
                tcp_sensor=[tcp_metadata(root/f'{j:06d}.json') for j in source]
            obs=self.augmentation.apply(str(root),obs,sensor,source,[j-k for j,k in zip(indices,source)],tcp_current,tcp_sensor)
        return obs,history[-1]['action'],stage
    def weights(self):
        counts=Counter(s for _,_,s in self.rows)
        return torch.tensor([1./counts[s] for _,_,s in self.rows],dtype=torch.double)


def action_loss(prediction,label): return (prediction-label).square().mean()


def evaluate(model,loader,device):
    model.eval();total=0;error=torch.zeros(6,dtype=torch.float64);stage_sum={s:0. for s in STAGES};counts=Counter()
    with torch.inference_mode():
        for obs,label,stage in loader:
            pred=model(**{k:v.to(device) for k,v in obs.items()});delta=(pred-label.to(device)).cpu()
            error+=delta.abs().sum(0).double();total+=len(label)
            mse=delta.square().mean(1)
            for s in STAGES:
                mask=stage==s;stage_sum[s]+=float(mse[mask].sum());counts[s]+=int(mask.sum())
    if not total or any(counts[s]==0 for s in STAGES): raise ValueError('Incomplete validation stages')
    by_stage={str(s):stage_sum[s]/counts[s] for s in STAGES}
    return dict(stage_mse=by_stage,macro_mse=sum(by_stage.values())/4,action_mae=(error/total).tolist(),frames=total)


def atomic_save(payload,path):
    path=Path(path);temporary=path.with_suffix('.tmp');torch.save(payload,temporary);temporary.replace(path)
