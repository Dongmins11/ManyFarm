"""Live Isaac ground truth for count evaluation only. Never feeds scout inference."""
import json
from pathlib import Path
import time
import numpy as np


class SceneTruth:
    def __init__(self, stage, output, robot_id, map_id, session, workspace):
        from pxr import Usd, UsdGeom, Gf
        self.stage, self.output = stage, Path(output)
        self.robot_id, self.map_id, self.session = robot_id, map_id, session
        self.workspace = workspace
        self.fruits = []
        for prim in stage.Traverse():
            color = prim.GetAttribute('crop:color')
            if color and color.Get():
                if any(str(prim.GetPath()).startswith(str(parent.GetPath())+'/') for parent, _ in self.fruits):
                    continue
                self.fruits.append((prim, str(color.Get()).lower()))
        if not self.fruits:
            raise RuntimeError('No crop:color fruit prims were found in the active scene')
        self.cache = UsdGeom.BBoxCache(Usd.TimeCode.Default(), ['default', 'render'], useExtentsHint=False)
        # A wire box has no collision and does not hide fruit or alter the source scene.
        self.lines = UsdGeom.BasisCurves.Define(stage, '/World/HarvestCountPreview/workspace')
        self.lines.CreateTypeAttr('linear')
        self.lines.CreateWrapAttr('nonperiodic')
        self.lines.CreateCurveVertexCountsAttr([2]*12)
        self.lines.CreateWidthsAttr([.005])
        self.lines.CreateDisplayColorAttr([Gf.Vec3f(.72, .12, 1.)])
        self.output.parent.mkdir(parents=True, exist_ok=True)

    def capture(self, stamp_ns, T_world_base):
        from pxr import Usd, UsdGeom, Gf
        self.cache.Clear()
        values, errors = [], []
        for prim, color in self.fruits:
            if not prim.IsActive():
                continue
            if UsdGeom.Imageable(prim).ComputeVisibility() == UsdGeom.Tokens.invisible:
                continue
            meshes = [p for p in Usd.PrimRange(prim, Usd.TraverseInstanceProxies()) if p.IsA(UsdGeom.Mesh)]
            if not meshes or any(not UsdGeom.Mesh(p).GetPointsAttr().Get() for p in meshes):
                errors.append('Missing fruit geometry: '+str(prim.GetPath()))
                continue
            bounds = self.cache.ComputeWorldBound(prim).ComputeAlignedRange()
            lo, hi = np.asarray(bounds.GetMin()), np.asarray(bounds.GetMax())
            if not np.isfinite([lo, hi]).all() or (hi <= lo).any():
                errors.append('Invalid fruit bounds: '+str(prim.GetPath()))
                continue
            values.append(dict(gt_id=str(prim.GetPath()), class_name=color,
                               center_world_m=((lo+hi)/2).tolist(), aabb_world_m=[lo.tolist(), hi.tolist()]))
        center = np.asarray(self.workspace['center_m'])
        size = np.asarray(self.workspace['size_m'])
        corners = [center+size*.5*np.array([x, y, z]) for z in (-1, 1) for y in (-1, 1) for x in (-1, 1)]
        corners = [T_world_base[:3, :3]@p+T_world_base[:3, 3] for p in corners]
        edges = [(0,1),(0,2),(1,3),(2,3),(4,5),(4,6),(5,7),(6,7),(0,4),(1,5),(2,6),(3,7)]
        self.lines.GetPointsAttr().Set([Gf.Vec3f(*map(float, corners[i])) for edge in edges for i in edge])
        snapshot = dict(schema_version=1, robot_id=self.robot_id, map_id=self.map_id,
                        scene_session=self.session, stamp_ns=int(stamp_ns), written_monotonic_s=time.monotonic(),
                        T_world_base=np.asarray(T_world_base).tolist(), fruits=values,
                        complete=not errors, error='; '.join(errors[:5]),
                        scene=self.stage.GetRootLayer().realPath, workspace=self.workspace)
        temp = self.output.with_suffix('.tmp')
        temp.write_text(json.dumps(snapshot, ensure_ascii=False, separators=(',', ':'), allow_nan=False))
        temp.replace(self.output)
        return len(values)
