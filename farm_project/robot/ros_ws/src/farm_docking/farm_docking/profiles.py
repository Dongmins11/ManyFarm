"""Resolve per-destination marker targets and robot controller settings.

No ROS or hardware dependency. Existing shared shadow_controller is the fallback.
"""
from copy import deepcopy
from pathlib import Path
import math
import yaml
from .pose_control import PoseController
from .departure import DepartureController
from .station_entry import StationEntry


def marker_profile(profile, default_file, base_frame):
    path=Path(profile.get('pose_control_file') or default_file).expanduser()
    if not path.is_absolute():raise ValueError('pose_control_file must be resolved to an absolute path')
    doc=yaml.safe_load(path.read_text())
    target=deepcopy(doc['targets'][profile['pose_target']])
    if target['base_frame']!=base_frame or profile.get('base_frame',base_frame)!=base_frame:
        raise ValueError('Marker target/profile/sensor base frames differ')
    if target['marker_id']!=profile['docking_marker_id']:raise ValueError('Marker target ID differs from docking marker ID')
    if not math.isfinite(target['marker_size_m']) or target['marker_size_m']<=0:raise ValueError('Invalid marker size')
    control=deepcopy(doc['shadow_controller'])
    overrides=profile.get('pose_controller',{})
    if set(overrides)-set(control):raise ValueError('Unknown pose controller setting: '+str(set(overrides)-set(control)))
    for key,value in overrides.items():
        if key in ('linear_pid','angular_pid'):
            if set(value)-{'kp','ki','kd'}:raise ValueError('Unknown PID gain')
            control[key].update(value)
        else:control[key]=value
    controller=(DepartureController(target,control,profile['departure']) if profile.get('departure') else PoseController(target,control))
    return target,controller


def validate_recovery(profile):
    cfg=profile.get('recovery')
    if not cfg:return
    for key in ('wait_timeout_s','marker_timeout_s','stable_s','search_angle_rad','search_speed_rps','search_dwell_s'):
        value=cfg[key]
        if isinstance(value,bool) or not isinstance(value,(float,int)) or not math.isfinite(value) or value<=0:
            raise ValueError('Invalid recovery '+key)
    if type(cfg['max_episodes']) is not int or cfg['max_episodes']<1:raise ValueError('Invalid max_episodes')
    if type(cfg['search_enabled']) is not bool:raise ValueError('Invalid search_enabled')
    if cfg['search_angle_rad']>math.pi/2:raise ValueError('Marker search exceeds quarter turn')
    if profile.get('entry',{}).get('enabled'):StationEntry(profile['entry'])
