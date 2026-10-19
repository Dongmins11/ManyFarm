"""Deployable configured initial target ROI; no actor positions or simulator dependency."""
import hashlib
import json
from pathlib import Path
import numpy as np

DEFAULT=Path(__file__).resolve().parents[1]/'config/initial_target_workspace.json'


def load_workspace(path=DEFAULT):
    raw=Path(path).read_bytes();p=json.loads(raw)
    lo=np.asarray(p['min_m'],float);hi=np.asarray(p['max_m'],float);margin=p['measurement_margin_m']
    if (p['version']!='initial_target_workspace_v1' or p['frame_id']!='arm_2/base_link' or
        lo.shape!=(3,) or hi.shape!=(3,) or not np.isfinite(np.r_[lo,hi]).all() or
        not (lo<hi).all() or type(margin) not in (int,float) or not np.isfinite(margin) or not 0<=margin<=.05):
        raise ValueError('Invalid arm-frame initial target workspace')
    return (lo-margin,hi+margin),dict(profile=p,sha256=hashlib.sha256(raw).hexdigest())
