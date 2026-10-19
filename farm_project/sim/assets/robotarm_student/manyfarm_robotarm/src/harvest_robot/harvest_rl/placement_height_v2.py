"""New reset domain: raise only the lower nominal fruit-root height bound."""
import copy
import json
from pathlib import Path

PROFILE=Path(__file__).resolve().parents[1]/'config/teacher60_placement_height_v2.json'


def height_settings(settings, legacy=False):
    result=copy.deepcopy(settings)
    old_lower=[a+b for a,b in zip(settings.region_origin,settings.region_min)]
    upper=[a+b for a,b in zip(settings.region_origin,settings.region_max)]
    profile=json.loads(PROFILE.read_text())
    lower=list(old_lower)
    if abs(upper[2]-profile['nominal_fruit_root_max_z_m'])>1e-9:
        raise ValueError('Height-v2 must preserve original1.063m upper bound')
    if not legacy:
        lower[2]=profile['nominal_fruit_root_min_z_m']
        if not old_lower[2]<=lower[2]<upper[2]:raise ValueError('Invalid raised minimum')
        result.region_min=list(settings.region_min)
        result.region_min[2]=lower[2]-settings.region_origin[2]
    return result,dict(profile=profile,legacy=legacy,original_lower_xyz_m=old_lower,
        lower_xyz_m=lower,upper_xyz_m=upper,minimum_changed=not legacy,
        other_task_values_unchanged=all(v==settings.as_dict()[k] for k,v in result.as_dict().items() if k!='region_min'))
