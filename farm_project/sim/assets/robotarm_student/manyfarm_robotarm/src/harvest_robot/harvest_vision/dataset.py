"""Episode-scoped, append-only, non-pickle demonstration storage."""
import json
from pathlib import Path
import numpy as np


class EpisodeWriter:
    def __init__(self, root, metadata):
        self.root=Path(root);self.root.mkdir(parents=True,exist_ok=False)
        self.count=0;self.closed=False
        self.version=metadata.get('input_schema_version',2)
        (self.root/'metadata.json').write_text(json.dumps(dict(schema_version=2,**metadata),indent=2))
    def append(self, observation, action, metadata):
        if self.closed: raise RuntimeError('Episode closed')
        expected={'rgb','depth_m','camera_valid','state'}
        if self.version==3:expected|={'wrist_ir_right','wrist_ir_valid'}
        if set(observation)!=expected: raise ValueError('Unexpected student inputs')
        if self.version==3:
            from harvest_rl.student_bc import validate_sample
            validate_sample(dict(observation,action=np.asarray(action,dtype=np.float32)))
        rgb=observation['rgb'];depth=observation['depth_m'];state=observation['state']
        if rgb.shape!=(2,90,160,3) or rgb.dtype!=np.uint8 or depth.shape!=(2,90,160) or state.shape!=(23,) or observation['camera_valid'].shape!=(2,):
            raise ValueError('Invalid observation schema')
        if not np.isfinite(depth).all() or np.any(depth<0) or not np.isfinite(state).all(): raise ValueError('Invalid observation values')
        action=np.asarray(action,dtype=np.float32)
        if action.shape!=(6,) or not np.isfinite(action).all() or np.any(np.abs(action)>1.00001): raise ValueError('Invalid action label')
        path=self.root/f'{self.count:06d}.npz'
        with path.open('xb') as f: np.savez_compressed(f,**observation,action=action)
        path.with_suffix('.json').write_text(json.dumps(metadata,indent=2))
        self.count+=1
    def finish(self, status, diagnostics=None):
        if self.closed: raise RuntimeError('Episode already closed')
        with (self.root/'result.json').open('x') as f:
            json.dump(dict(status=status,samples=self.count,diagnostics=diagnostics or {}),f,indent=2)
        self.closed=True


class Demonstrations:
    """Only finished successful episodes by default; split by episode before using this loader."""
    def __init__(self, root, *, successful_only=True):
        self.samples=[]
        for result in sorted(Path(root).glob('episode_*/result.json')):
            meta=json.loads(result.read_text())
            if successful_only and meta['status']!='SUCCEEDED': continue
            for i in range(meta['samples']): self.samples.append((result.parent,i))
    def __len__(self): return len(self.samples)
    def __getitem__(self,index):
        root,i=self.samples[index];rows=[]
        for j in range(i-2,i+1):
            with np.load(root/f'{max(0,j):06d}.npz',allow_pickle=False) as a: rows.append({k:a[k] for k in a.files})
        keys=('rgb','depth_m','camera_valid','state')
        if 'wrist_ir_right' in rows[0]:keys+=('wrist_ir_right','wrist_ir_valid')
        return {k:np.stack([row[k] for row in rows]) for k in keys},rows[-1]['action']
