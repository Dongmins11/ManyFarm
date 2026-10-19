"""Read-only verification of the additive mission and both camera model families."""
import hashlib
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'src/harvest_robot'))


def main():
    import torch
    torch.set_num_threads(4)
    manifest=json.loads((ROOT/'handoff/MISSION_MANIFEST.json').read_text())
    for row in manifest['files']:
        path=(ROOT/row['path']).resolve()
        if not path.is_relative_to(ROOT):raise ValueError('Path outside release')
        with path.open('rb') as f:digest=hashlib.file_digest(f,'sha256').hexdigest()
        if digest!=row['sha256'] or path.stat().st_size!=row['bytes']:raise ValueError('Changed release file: '+row['path'])
    release=json.loads((ROOT/'handoff/MISSION_RELEASE.json').read_text())
    from harvest_rl.student60_recurrent import RecurrentCameraInference
    from harvest_rl.student60_u20_model import U20Inference
    for camera,cls in [('d435',RecurrentCameraInference),('u20',U20Inference)]:
        path=ROOT/release['models'][camera]['path']
        saved=torch.load(path,map_location='cpu',weights_only=True)
        cls(path,saved['contract'],'cpu')
    from student60_bundle import check_contract
    check,_,_=check_contract()
    print(json.dumps(dict(passed=True,files=len(manifest['files']),models=['d435','u20'],
        original_baseline_check=check,hardware=False),indent=2))


if __name__=='__main__':main()
