"""Strict, separate data preparation for executed targets and jaw commands."""
from collections import Counter
import hashlib
import json
from pathlib import Path
import numpy as np
import torch
from torch.utils.data import Dataset
from .student_bc import validate_sample
from harvest_runtime.student60 import VERSION, OBSERVATION, TargetFilter, encode_command

PHASES=('approach','bridge','pull','transport','place')

def read(path):return json.loads(Path(path).read_text())
def digest(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
    return h.hexdigest()


def contract_for(root):
    root=Path(root);m=read(root/'dataset_manifest.json');r=read(root/'run.json')
    if m.get('student60_version')!=VERSION or m.get('observation_contract')!=OBSERVATION:
        raise ValueError('Old/pilot action, servo, or target-observation contract')
    keys=('student60_version','observation_contract','camera_order','camera_config','capture_contract',
          'history','control_dt','sensor_dt','timing_contract','frame_id','lower_rad','upper_rad',
          'joint_names','detector_sha256','action_contract','centre_offset_m','box_from_arm','box_min','box_max')
    result={k:m[k] for k in keys}
    result.update(student_schema_version=3,visual_scene_sha256=m['visual_scene']['sha256'],
        teacher_runtime=r['teacher_runtime'],task=r['task'].copy(),
        sensor_mount_reference_urdf_sha256=r['current_asset']['sensor_mount_reference_urdf_sha256'],
        deployment_arm_appearance_sha256=r['current_asset']['deployment_arm_appearance_sha256'],
        robot_asset_sha256=r['current_asset']['asset_input_sha256'])
    result['task'].pop('seed',None)
    from .student_readiness import require_current_observations
    require_current_observations(result)
    return result


def prepare(roots_by_split):
    plan=dict(student60_version=VERSION,train=[],validation=[],files={},skipped=[],warnings=[])
    reference=None;seen=set();seeds={};scene_sets={}
    for split in ('train','validation'):
        seeds[split]=set();scene_sets[split]=set()
        for root in roots_by_split[split]:
            root=Path(root).resolve()
            if root in seen:raise ValueError('Repeated root')
            seen.add(root)
            if (root/'DO_NOT_TRAIN.json').exists() or (root/'COLLECTION_IN_PROGRESS.json').exists():
                raise ValueError('Pilot/quarantined/incomplete data')
            m=read(root/'dataset_manifest.json');run=read(root/'run.json');v=read(root/'verification.json')
            if m['split_role']!=split or not run.get('completed') or not v.get('audit_passed') or not v.get('final_runtime_audit_complete'):
                raise ValueError('Split or completion/native audit mismatch')
            c=contract_for(root)
            if reference is None:reference=c
            if c!=reference:raise ValueError('Mixed camera, physics, servo or action contracts')
            seeds[split].add(m['seed'])
            if (root/'compact_certificate.json').exists():
                from .student60_compact import verify_compact
                verify_compact(root)
                plan['files'][str(root/'compact_certificate.json')]=digest(root/'compact_certificate.json')
            for name in ('run.json','dataset_manifest.json','verification.json'):
                plan['files'][str(root/name)]=digest(root/name)
            for folder in sorted(root.glob('episode_*')):
                result=read(folder/'result.json');meta=read(folder/'metadata.json')
                if result['status']!='SUCCEEDED':
                    plan['skipped'].append(dict(path=str(folder),reason=result['status'] if result['status']!='SUCCEEDED' else 'wrong_initial_target'));continue
                count=result['samples'];phases=[];previous=None;first_observed=None
                filter_=TargetFilter(c['box_from_arm'],c['box_min'],c['box_max'])
                for name in ('result.json','metadata.json'):plan['files'][str(folder/name)]=digest(folder/name)
                for i in range(count):
                    path=folder/f'{i:06d}.npz';note=read(path.with_suffix('.json'))
                    with np.load(path,allow_pickle=False) as z:
                        row={k:z[k] for k in z.files};validate_sample(row)
                    command=encode_command(note['executed_target_rad'],note['servo_command'],c['lower_rad'],c['upper_rad'])
                    np.testing.assert_allclose(row['action'],command[:6],atol=1e-6)
                    if previous is not None:np.testing.assert_allclose(row['state'][12:18],previous,atol=1e-6)
                    expected=filter_.filter(note['raw_target'])
                    if first_observed is None and expected['valid']:
                        first_observed=(note['stamp_s'],note['target_error_m'])
                    if note['target']!=expected or bool(row['state'][21])!=expected['valid'] or note['target_release_latched']!=filter_.released:
                        raise ValueError('Target filtering differs between recorded and execution path')
                    relative=np.asarray(expected['position_m'])-note['tcp_arm_m'] if expected['valid'] else np.zeros(3)
                    np.testing.assert_allclose(row['state'][18:21],relative,atol=1e-6)
                    filter_.observe_command(note['previous_target_rad'],note['executed_target_rad'],note['tcp_arm_m'])
                    previous=command[:6];phases.append(note['phase'])
                    for p in (path,path.with_suffix('.json')):plan['files'][str(p)]=digest(p)
                if first_observed is None or first_observed[0]>.5 or first_observed[1] is None or first_observed[1]>.03:
                    plan['skipped'].append(dict(path=str(folder),reason='initial_vision_assignment_not_verified_within_500ms_30mm'));continue
                if set(phases)!=set(PHASES):raise ValueError('Missing complete harvest stages')
                if not filter_.released:raise ValueError('No observable tray-opening latch; inspect rather than silently train')
                if phases!=sorted(phases,key=PHASES.index):raise ValueError('Non-monotonic harvest stages')
                identity=json.dumps([m['seed'],meta['layout']['domain_sample']],sort_keys=True)
                if identity in scene_sets[split]:raise ValueError('Duplicate scene')
                scene_sets[split].add(identity)
                plan[split].append(dict(path=str(folder),samples=count,phases=phases,seed=m['seed'],color=meta['layout']['target_color']))
        if not plan[split]:raise ValueError('No eligible successful '+split+' data')
        if {e['color'] for e in plan[split]}!={'Red','Yellow'}:raise ValueError('Both colors required in '+split)
    if seeds['train']&seeds['validation']:raise ValueError('Train/validation seed overlap')
    if scene_sets['train']&scene_sets['validation']:raise ValueError('Scene leakage')
    plan['contract']=reference
    plan['summary']={s:dict(episodes=len(plan[s]),samples=sum(e['samples'] for e in plan[s]),
        colors=dict(Counter(e['color'] for e in plan[s])),phases=dict(Counter(p for e in plan[s] for p in e['phases']))) for s in ('train','validation')}
    if len(plan['train'])<50 or len(plan['validation'])<10:
        plan['warnings'].append('Small initial BC dataset: pipeline-ready, not a Student harvest/generalization guarantee. Expand train>=50 and validation>=10 successes.')
    plan['ready_for_initial_bc']=True
    return plan


def verify(plan):
    if plan.get('student60_version')!=VERSION or not plan.get('ready_for_initial_bc'):raise ValueError('Not prepared Student60 data')
    from .student_readiness import require_current_observations
    require_current_observations(plan['contract'])
    for s in ('train','validation'):
        for e in plan[s]:
            root=Path(e['path']).parent
            if (root/'DO_NOT_TRAIN.json').exists() or (root/'COLLECTION_IN_PROGRESS.json').exists():raise ValueError('Data quarantined/incomplete')
    for path,sha in plan['files'].items():
        if digest(path)!=sha:raise ValueError('Prepared data changed: '+path)


class Student60Dataset(Dataset):
    def __init__(self,episodes,contract):
        self.rows=[(Path(e['path']),i,PHASES.index(p)) for e in episodes for i,p in enumerate(e['phases'])]
        self.contract=contract
    def __len__(self):return len(self.rows)
    def __getitem__(self,index):
        root,i,phase=self.rows[index];history=[]
        for j in range(i-2,i+1):
            with np.load(root/f'{max(j,0):06d}.npz',allow_pickle=False) as z:history.append({k:z[k] for k in z.files})
        obs={k:np.stack([row[k] for row in history]) for k in history[0] if k!='action'}
        note=read(root/f'{i:06d}.json')
        command=encode_command(note['executed_target_rad'],note['servo_command'],self.contract['lower_rad'],self.contract['upper_rad'])
        return obs,command,phase
    def weights(self):
        counts=Counter(p for _,_,p in self.rows)
        return torch.tensor([1/counts[p] for _,_,p in self.rows],dtype=torch.double)
