"""Independent saved-pose audit; no Isaac runtime needed."""
import ast, hashlib, json, math, re, sys
from pathlib import Path
import numpy as np
from scipy.spatial.transform import Rotation
root=Path(__file__).resolve().parents[4]
base=root/'outputs/sorting_station/hcr_sim'
directory=Path(sys.argv[1])
report=json.loads((directory/'report.json').read_text())
cfg=json.loads((directory/'configuration.json').read_text())
source=json.loads((base/'validation/existing_transport_sources.json').read_text())['source_sha256']
assert len(source)==98
assert all(hashlib.sha256((root/p).read_bytes()).hexdigest()==h for p,h in source.items())
assert (directory/'zones.json').read_bytes()==(base/'validation/before_transport/zones.json').read_bytes()
transport=report['transport']
loading=transport['loading_snapshot']
assert loading['all_inside'] and loading['settled'] and len(loading['bodies'])==8
assert all(b['inside'] and b['linear_speed']<.035 and b['angular_speed']<.4 for b in loading['bodies'])
meshes={}
for color in ('red','yellow'):
    for p in (base/'assets/peppers').glob(f'pepper_{color}_*.usda'):
        s=p.read_text().split('def Mesh "Collision"',1)[1]
        points=np.array(ast.literal_eval(re.search(r'point3f\[\] points = (\[[^\n]+\])',s)[1]))
        if abs(np.ptp(points[:,2])-.075)<1e-6: meshes[color.upper()]=points
assert len(meshes)==2
# Unload-only ends at READY. Use its full saved XYZ+quat for independent hull test.
if report['stop_after_sorted']==0:
    axis=np.array([cfg['transport']['dock_front_x'],0,.255])
    boxrot=np.diag([-1.,-1.,1.])@Rotation.from_euler('y',math.radians(transport['box_angle_deg'])).as_matrix()
    bounds=[]
    for f in report['fruits']:
        q=np.array(f['quat_wxyz'])
        r=Rotation.from_quat(q[[1,2,3,0]]).as_matrix()
        hull=(meshes[f['color']]@r.T+f['xyz']-axis)@boxrot
        bounds.append(float(hull[:,0].min()))
    assert all(v>0 for v in bounds),bounds
else: bounds=None
completed=[f for f in report['fruits'] if f['sorted']]
s=cfg['storage']; run=math.sqrt(s['ramp_length']**2-s['ramp_rise']**2); edge=s['drop_x']-run
for f in completed:
    x,y,z=f['xyz']; sign=1 if f['color']=='RED' else -1
    surface=s['drop_z']-s['ramp_rise']+max(0,min(run,x-edge))*s['ramp_rise']/run
    assert edge-s['bin_length']+.015<x<s['drop_x']-.01
    assert .005<sign*y<s['width']/2-.008
    assert surface-.005<z<surface+cfg['physics']['pepper_length']+.02
assert sum(report['counts'])==len(completed)
audit=dict(original_98_sources_unchanged=True,saved_manual_roi_unchanged=True,
    loading_inside_and_settled=True,payload_count=8,payload_seed=transport['payload_seed'],
    initial_positions_unique=len({tuple(f['initial_pose']['position']) for f in report['fruits']})==8,
    initial_rotations_unique=len({tuple(f['initial_pose']['rotation_wxyz']) for f in report['fruits']})==8,
    dump_snapshot=transport['dump_snapshot'],cargo_front_hull_min_x_at_unload_end=bounds,
    completed_cycles=len(completed),completed_in_correct_bins=True,
    phase=report['phase'],error=report['error'],validation_limit_reached=report['validation_limit_reached'],
    batch_complete=report['batch_complete'])
(directory/'audit.json').write_text(json.dumps(audit,indent=2)+'\n')
print(json.dumps(audit,ensure_ascii=False))
