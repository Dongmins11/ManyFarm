"""Graph-node exit orientation, independent of camera mounting and marker yaw."""
import json
import math
from pathlib import Path

def graph_point(path,node_id):
    doc=json.loads(Path(path).read_text())
    nodes=[f for f in doc['features'] if f.get('geometry',{}).get('type')=='Point' and str(f.get('properties',{}).get('id'))==str(node_id)]
    if len(nodes)!=1:raise ValueError('Exit node missing or duplicated')
    node=nodes[0]
    if node.get('properties',{}).get('frame')!='map':raise ValueError('Exit node must use map frame')
    x,y=node['geometry']['coordinates'][:2]
    if not all(math.isfinite(v) for v in (x,y)):raise ValueError('Invalid exit node coordinates')
    return x,y

def heading_command(current,target,cfg):
    for k in ('yaw_tolerance_rad','alignment_max_angular_rps','alignment_kp'):
        if not math.isfinite(cfg[k]) or cfg[k]<=0:raise ValueError(k)
    if not all(math.isfinite(v) for v in (current,target)):raise ValueError('Invalid heading')
    error=math.atan2(math.sin(target-current),math.cos(target-current))
    if abs(error)<=cfg['yaw_tolerance_rad']:return 0.,True
    limit=cfg['alignment_max_angular_rps']
    return max(-limit,min(limit,cfg['alignment_kp']*error)),False
