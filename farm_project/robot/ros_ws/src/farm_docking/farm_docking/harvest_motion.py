"""Harvest-only relative motion. No global-map or station coordinates."""
import math

def positive(v, key):
    if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or v <= 0:
        raise ValueError('Positive measured/configured value required: ' + key)

def validate_independent_profile(p, operation):
    if operation not in p.get('allowed_operations', []):raise ValueError('Operation disabled')
    if not p.get('collision_guard'):raise ValueError('Collision guard required outside lidar approach')
    if p.get('relative_backout'):
        if operation != 'CLEAR':raise ValueError('Relative backout requires CLEAR')
        for key,value in p['relative_backout'].items():positive(value,key)
        c=p['relative_backout']
        if c['min_linear_mps']>c['max_linear_mps'] or c['distance_tolerance_m']>=c['distance_m']:
            raise ValueError('Invalid backout speed/tolerance')
    elif p.get('observation_only'):
        if operation != 'DOCK':raise ValueError('Observation-only approach requires DOCK')
        positive(p['marker_installation']['marker_size_m'],'marker_size_m')
        c=p['distance_heading_trial']
        if c['marker_id']!=p['target_marker_id'] or p['target_marker_id']!=p['docking_marker_id']:
            raise ValueError('Marker roles differ')
        for key in ('max_lateral_m','max_bearing_rad','acquire_timeout_s','alignment_tolerance_rad','alignment_kp','alignment_max_angular_rps'):
            positive(c[key],key)

def backout_command(c, origin, pose, elapsed):
    if elapsed>c['timeout_s']:raise TimeoutError('Harvest relative backout timeout')
    x,y,heading=origin;px,py,yaw=pose
    dx,dy=px-x,py-y
    reverse=-(dx*math.cos(heading)+dy*math.sin(heading))
    lateral=-dx*math.sin(heading)+dy*math.cos(heading)
    error=math.atan2(math.sin(heading-yaw),math.cos(heading-yaw))
    if abs(lateral)>c['max_lateral_m']:raise RuntimeError('Harvest backout lateral limit')
    if abs(error)>c['max_heading_error_rad']:raise RuntimeError('Harvest backout heading limit')
    remaining=c['distance_m']-reverse
    if remaining<=c['distance_tolerance_m']:return 0.,0.,True
    v=-min(c['max_linear_mps'],max(c['min_linear_mps'],remaining*.5))
    w=max(-c['max_angular_rps'],min(c['max_angular_rps'],c['heading_kp']*error))
    return v,w,False
