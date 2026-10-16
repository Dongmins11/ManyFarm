"""Live Isaac ground truth for count evaluation only. Never feeds scout inference."""
import json
import os
from pathlib import Path
import time
import numpy as np


class SceneTruth:
    def __init__(self, stage, output, robot_id, map_id, session, workspace):
        from pxr import Usd, UsdGeom, Gf, Tf
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
        self.fruit_paths = {str(prim.GetPath()) for prim, _ in self.fruits}
        self.fruit_prefix = os.path.commonpath([str(prim.GetPath().GetParentPath())
                                              for prim, _ in self.fruits]).rstrip('/')+'/'
        self.geometry_dirty = True
        self.local_bounds = {}
        self.geometry_valid = {}
        self.transforms = UsdGeom.XformCache()
        self.notice = Tf.Notice.Register(Usd.Notice.ObjectsChanged, self._geometry_changed, stage)
        # A wire box has no collision and does not hide fruit or alter the source scene.
        self.lines = UsdGeom.BasisCurves.Define(stage, '/World/HarvestCountPreview/workspace')
        self.lines.CreateTypeAttr('linear')
        self.lines.CreateWrapAttr('nonperiodic')
        self.lines.CreateCurveVertexCountsAttr([2]*12)
        self.lines.CreateWidthsAttr([.005])
        self.lines.CreateDisplayColorAttr([Gf.Vec3f(.72, .12, 1.)])
        self.output.parent.mkdir(parents=True, exist_ok=True)

    def _geometry_changed(self, notice: object, sender: object) -> None:
        """위치만 바뀌는 과실은 로컬 경계를 재사용하고 실제 기하 편집은 무효화한다."""
        for path in notice.GetResyncedPaths():
            text = str(path)
            if text.startswith(self.fruit_prefix) or self.fruit_prefix.startswith(text.rstrip('/')+'/'):
                self.geometry_dirty = True
                return
        for path in notice.GetChangedInfoOnlyPaths():
            if not str(path).startswith(self.fruit_prefix):
                continue
            name = path.name
            if name.startswith('xformOp') and str(path.GetPrimPath()) in self.fruit_paths:
                continue
            if name.startswith('xformOp') or name in ('points', 'extent', 'visibility',
                                                     'radius', 'height', 'size', 'axis', 'widths'):
                self.geometry_dirty = True
                return

    def close(self) -> None:
        """stage 변경 구독을 해제한다."""
        self.notice.Revoke()

    def capture(self, stamp_ns, T_world_base):
        from pxr import Usd, UsdGeom, Gf
        if self.geometry_dirty:
            self.cache.Clear()
            for prim, _ in self.fruits:
                key = str(prim.GetPath())
                meshes = [p for p in Usd.PrimRange(prim, Usd.TraverseInstanceProxies())
                          if p.IsA(UsdGeom.Mesh)]
                valid = bool(meshes) and all(UsdGeom.Mesh(p).GetPointsAttr().Get() for p in meshes)
                self.geometry_valid[key] = valid
                if valid:
                    self.local_bounds[key] = self.cache.ComputeUntransformedBound(prim)
            self.geometry_dirty = False
        self.transforms.Clear()
        values, errors = [], []
        for prim, color in self.fruits:
            if not prim.IsActive():
                continue
            if UsdGeom.Imageable(prim).ComputeVisibility() == UsdGeom.Tokens.invisible:
                continue
            key = str(prim.GetPath())
            if not self.geometry_valid[key]:
                errors.append('Missing fruit geometry: '+str(prim.GetPath()))
                continue
            bound = Gf.BBox3d(self.local_bounds[key])
            bound.Transform(self.transforms.GetLocalToWorldTransform(prim))
            bounds = bound.ComputeAlignedRange()
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
