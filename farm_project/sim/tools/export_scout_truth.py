#!/usr/bin/env python3
"""TEMP evaluation-only USD fruit bounds. Never imported by survey/vision nodes."""
import argparse
import json
from pathlib import Path


def export(stage,output):
    from pxr import Usd,UsdGeom
    import numpy as np
    if UsdGeom.GetStageUpAxis(stage)!='Z' or abs(UsdGeom.GetStageMetersPerUnit(stage)-1)>1e-8:
        raise ValueError('Evaluation requires metre/Z-up scene')
    cache=UsdGeom.BBoxCache(Usd.TimeCode.Default(),['default','render'],useExtentsHint=False)
    fruits=[]
    for prim in stage.Traverse():
        if not prim.HasAttribute('crop:color'):continue
        color=prim.GetAttribute('crop:color').Get()
        if not color:continue
        meshes=[p for p in Usd.PrimRange(prim,Usd.TraverseInstanceProxies()) if p.IsA(UsdGeom.Mesh)]
        if not meshes:raise RuntimeError(f'Missing fruit mesh/reference: {prim.GetPath()}')
        if any(not UsdGeom.Mesh(p).GetPointsAttr().Get() for p in meshes):
            raise RuntimeError(f'Fruit mesh points unavailable: {prim.GetPath()}')
        box=cache.ComputeWorldBound(prim).ComputeAlignedRange()
        lo=np.array(box.GetMin());hi=np.array(box.GetMax())
        if not np.isfinite([lo,hi]).all() or (hi<=lo).any():raise RuntimeError('Invalid fruit bounds')
        fruits.append({'gt_id':str(prim.GetPath()),'bed_prim':str(prim.GetPath()).split('/Fruits/')[0],
            'class_name':str(color).capitalize(),'aabb_world_m':[lo.tolist(),hi.tolist()],
            'center_world_m':((lo+hi)/2).tolist()})
    if not fruits:raise RuntimeError('No crop:color fruit prims found')
    out={'scope':'evaluation only; USD mesh AABB center is not sensor surface point',
         'scene':stage.GetRootLayer().realPath,'frame':'isaac_world','fruits':fruits}
    path=Path(output);path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(out,ensure_ascii=False,indent=2,allow_nan=False))
    print(f'Exported {len(fruits)} fruit bounds: {path}')


def main():
    p=argparse.ArgumentParser();p.add_argument('--scene',required=True);p.add_argument('--output',required=True);a=p.parse_args()
    app=None
    try:
        try:from pxr import Usd
        except ImportError:
            from isaacsim import SimulationApp
            app=SimulationApp({'headless':True})
            from pxr import Usd
        s=Usd.Stage.Open(str(Path(a.scene).expanduser().resolve()))
        if not s:raise RuntimeError('Cannot open scene')
        export(s,a.output)
    finally:
        if app:app.close()
if __name__=='__main__':main()
