"""Use actual Student prefix observations as history, never as expert labels."""
from pathlib import Path
import numpy as np
from .student60_data import Student60Dataset,read,digest
from .student_v3 import FIELDS
from harvest_runtime.student60 import encode_command


def attach_history_hashes(plan):
    added={}
    episodes=[]
    for episode in plan['train']:
        root=Path(episode['path'])
        prefix=read(root/'metadata.json').get('recovery_prefix')
        if not prefix:continue
        folder=root.parent/'recovery_prefix'/root.name
        result=read(folder/'result.json')
        if not result['completed'] or result['physical_pose_injection'] or result['episode_budget_reset']:
            raise ValueError('Unapproved recovery prefix')
        cert=read(root.parent/'compact_certificate.json')['files']
        paths=[folder/'result.json',folder/'DO_NOT_TRAIN.json',folder/'trace.json']
        paths.extend(folder/f'{i:06d}.npz' for i in range(prefix['steps']-2,prefix['steps']))
        for path in paths:
            expected=cert[str(path.relative_to(root.parent))]
            if digest(path)!=expected:raise ValueError('Recovery history archive changed')
            added[str(path)]=expected
        with np.load(paths[-1],allow_pickle=False) as z:
            last=z['student_command']
        with np.load(root/'000000.npz',allow_pickle=False) as z:
            np.testing.assert_allclose(z['state'][12:18],last[:6],atol=1e-6)
        episodes.append(str(root))
    plan['files'].update(added)
    plan['recovery_history']=dict(schema='student60_actual_prefix_history_v1',episodes=episodes,
        files_added=len(added),prefix_commands_are_labels=False)
    return plan


class Student60RecoveryDataset(Student60Dataset):
    def __init__(self,episodes,contract):
        super().__init__(episodes,contract)
        self.prefix={}
        for e in episodes:
            root=Path(e['path']);p=read(root/'metadata.json').get('recovery_prefix')
            if p:
                self.prefix[root]=(root.parent/'recovery_prefix'/root.name,int(p['steps']))

    def __getitem__(self,index):
        root,i,phase=self.rows[index]
        if root not in self.prefix or i>=2:return super().__getitem__(index)
        folder,count=self.prefix[root];history=[]
        for j in range(i-2,i+1):
            path=folder/f'{count+j:06d}.npz' if j<0 else root/f'{j:06d}.npz'
            with np.load(path,allow_pickle=False) as z:
                history.append({k:z[k] for k in FIELDS})
        obs={k:np.stack([x[k] for x in history]) for k in FIELDS}
        note=read(root/f'{i:06d}.json')
        label=encode_command(note['executed_target_rad'],note['servo_command'],
            self.contract['lower_rad'],self.contract['upper_rad'])
        return obs,label,phase
