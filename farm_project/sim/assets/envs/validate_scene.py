"""Validate composed assets, exact fruit geometry clearance, spacing, and counts."""
import json
import math
from collections import Counter
from pathlib import Path
import numpy as np
from pxr import Usd,UsdGeom,UsdShade,Sdf
from placement import ROOT,find_beds,transform_points

def validate_scene(config=ROOT/'config.json'):
    cfg=json.loads(Path(config).read_text());out=(ROOT/cfg['output']).resolve()
    s=Usd.Stage.Open(str(out));report=json.loads(out.with_suffix('.report.json').read_text())
    beds={b['id']:b for b in find_beds(s,cfg)};xf=UsdGeom.XformCache()
    errors=[];min_clearance=float('inf');mesh_count=0
    for p in Usd.PrimRange.Stage(s,Usd.TraverseInstanceProxies()):
        for attr in p.GetAttributes():
            if attr.GetTypeName()==Sdf.ValueTypeNames.Asset:
                v=attr.Get()
                if v and v.path and not v.resolvedPath:errors.append(f'Missing asset {attr.GetPath()}: {v.path}')
        if p.IsA(UsdGeom.Mesh):
            mesh_count+=1
            mat,_=UsdShade.MaterialBindingAPI(p).ComputeBoundMaterial()
            if '/Vegetation/' in str(p.GetPath()) and not mat:errors.append(f'Missing material: {p.GetPath()}')
    for bed_id,bed in beds.items():
        local=dict(cfg);local.update(cfg.get('bed_overrides',{}).get(str(bed_id),{}))
        f=[f for f in report['fruits'] if f['bed']==bed_id]
        actual=Counter(p['color'] for p in f)
        expected=Counter({c:n for c,n in local['fruit_counts_per_bed'].items() if n})
        if actual!=expected:errors.append(f'Bed {bed_id}: count mismatch')
        if sum(t['bed']==bed_id for t in report['trees'])!=local['plants_per_bed']:errors.append('Tree count mismatch')
        for i,fruit in enumerate(f):
            root=s.GetPrimAtPath(fruit['path'])
            if not root:errors.append('Missing fruit '+fruit['path']);continue
            for p in Usd.PrimRange(root,Usd.TraverseInstanceProxies()):
                if p.IsA(UsdGeom.Mesh):
                    points=np.array(UsdGeom.Mesh(p).GetPointsAttr().Get())
                    pts=transform_points(points,xf.GetLocalToWorldTransform(p)*bed['matrix'].GetInverse())
                    clear=fruit['side']*(pts[:,0]-bed['x'])-bed['outer_half_width']
                    min_clearance=min(min_clearance,float(clear.min()))
                    if clear.min()<local['wire_clearance_m']-1e-5:errors.append('Fruit intersects wire envelope: '+fruit['path'])
            for other in f[:i]:
                d=np.linalg.norm(np.array(fruit['center_world'])-other['center_world'])
                if d<fruit['radius_m']+other['radius_m']+local['fruit_gap_m']-1e-6:errors.append('Fruit overlap')
    result={'passed':not errors,'bed_count':len(beds),'tree_count':report['tree_count'],'fruit_count':report['fruit_count'],
        'composed_mesh_count':mesh_count,'minimum_vertex_clearance_m':min_clearance if math.isfinite(min_clearance) else None,
        'errors':errors,'rendering_note':'USD/geometry validation only; Isaac Sim RTX rendering not executed in this environment.'}
    out.with_suffix('.validation.json').write_text(json.dumps(result,indent=2))
    print(json.dumps(result,indent=2))
    if errors:raise RuntimeError('Validation failed')
    return result
if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--config',type=Path,default=ROOT/'config.json');a=p.parse_args();validate_scene(a.config)
