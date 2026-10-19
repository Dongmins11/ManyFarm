"""Inspect v2 demonstrations and test network input, without training."""
import argparse,json
from pathlib import Path
import numpy as np
import torch
from harvest_vision.dataset import Demonstrations
from harvest_rl.student_v2 import DualRGBDStudent


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('root',type=Path);a=p.parse_args()
    results=[json.loads(x.read_text()) for x in sorted(a.root.glob('episode_*/result.json'))]
    dataset=Demonstrations(a.root)
    report=dict(episodes=len(results),statuses={s:sum(r['status']==s for r in results) for s in sorted({r['status'] for r in results})},
                all_frames=sum(r['samples'] for r in results),successful_frames=len(dataset))
    stages={};valid=0
    for path in a.root.glob('episode_*/*.npz'):
        with np.load(path,allow_pickle=False) as row:
            valid+=bool(row['state'][21])
            from harvest_rl.student_bc import validate_sample
            validate_sample({k:row[k] for k in row.files})
        stage=str(json.loads(path.with_suffix('.json').read_text())['expert_stage']);stages[stage]=stages.get(stage,0)+1
    report.update(target_valid_frames=valid,expert_stage_frames=stages)
    manifest=json.loads((a.root/'dataset_manifest.json').read_text())
    if manifest.get('capture_contract')=='physics_scheduled_multimodal_v3':
        from harvest_sensors.deployment import audit_raw_captures,audit_camera_sample
        from harvest_rl.student_bc import validate_sample
        run=json.loads((a.root/'run.json').read_text());timing=[]
        for folder in sorted(a.root.glob('episode_*')):
            previous=None
            for path in sorted(folder.glob('*.npz')):
                with np.load(path,allow_pickle=False) as z:validate_sample({k:z[k] for k in z.files})
                row=json.loads(path.with_suffix('.json').read_text())
                audit_camera_sample(row,manifest['control_dt'],previous)
                if previous is not None and abs(row['stamp_s']-previous['stamp_s']-.05)>1e-8:raise ValueError('Control clock drift')
                previous=row
            timing.append(dict(episode=folder.name,**audit_raw_captures(folder,manifest,run)))
        report.update(capture_contract=manifest['capture_contract'],policy_hz=20,timing_checks=timing)
    if len(dataset):
        observation,_=dataset[0]
        if 'wrist_ir_right' in observation:
            from harvest_rl.student_v3 import MultimodalStudent
            model=MultimodalStudent().eval()
        else:model=DualRGBDStudent().eval()
        with torch.inference_mode(): prediction=model(**{k:torch.as_tensor(v[None]) for k,v in observation.items()})
        report['untrained_network_shape_check']=list(prediction.shape)
    print(json.dumps(report,indent=2))
    if not len(dataset): print('No successful demonstrations yet; do not start BC from this dataset.')
if __name__=='__main__':main()
