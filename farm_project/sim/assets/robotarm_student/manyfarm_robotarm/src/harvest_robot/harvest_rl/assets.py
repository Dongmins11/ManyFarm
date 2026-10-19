"""USD helper functions. Import only AFTER AppLauncher."""
import json
import math
import numpy as np
from pxr import Gf, Usd, UsdGeom, UsdPhysics, PhysxSchema, UsdShade
from .settings import ASSETS, CACHE


def bind_verified_material(stage, body_path, material_path):
    """Resolve imported collision instances locally; bind every collider, verify USD resolution."""
    root = stage.GetPrimAtPath(body_path)
    for prim in list(Usd.PrimRange(root)):
        if prim.IsInstance():
            prim.SetInstanceable(False)
    material = UsdShade.Material(stage.GetPrimAtPath(material_path))
    paths = []
    for prim in Usd.PrimRange(root):
        if not prim.HasAPI(UsdPhysics.CollisionAPI):
            continue
        binding = UsdShade.MaterialBindingAPI.Apply(prim)
        binding.Bind(material, bindingStrength=UsdShade.Tokens.strongerThanDescendants, materialPurpose="physics")
        resolved, _ = binding.ComputeBoundMaterial("physics")
        if resolved.GetPath() != material.GetPath():
            raise RuntimeError(f"Physics material did not resolve on {prim.GetPath()}")
        paths.append(str(prim.GetPath()))
    if not paths:
        raise RuntimeError(f"No editable collider under {body_path}")
    return paths


def fruit_asset(cfg, color="Red", cache=None):
    palette = cfg.sequence and cfg.random_colors
    name = "Palette" if palette else color
    mesh_contact = cfg.attachment_version == 4 and cfg.stem_response_version >= 2
    suffix = "_mesh_contact_v2" if mesh_contact else ""
    body_hull = cfg.fruit_collision_mode == 'body_hull_v1'
    if body_hull:
        suffix = '_body_hull_v1'
    directory = CACHE if cache is None else cache
    directory.mkdir(parents=True,exist_ok=True)
    path = directory / f"pepper_{name}_{cfg.diameter:.4f}_{cfg.length:.4f}_{cfg.mass:.4f}{suffix}.usda"
    stage = Usd.Stage.CreateNew(str(path))
    UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.z)
    UsdGeom.SetStageMetersPerUnit(stage, 1.0)
    root = UsdGeom.Xform.Define(stage, "/Pepper").GetPrim()
    stage.SetDefaultPrim(root)
    UsdPhysics.RigidBodyAPI.Apply(root)
    UsdPhysics.MassAPI.Apply(root).CreateMassAttr(cfg.mass)
    PhysxSchema.PhysxRigidBodyAPI.Apply(root).CreateEnableCCDAttr(True)
    meta = json.loads((ASSETS / "manifest.json").read_text())["Pepper_" + color]
    size = np.diff(meta["bounds"], axis=0)[0]
    scale = np.array([cfg.diameter / max(size[:2])] * 2 + [cfg.length / size[2]])
    for shade in (("Red","Yellow","Green") if palette else (color,)):
        visual = UsdGeom.Xform.Define(stage, f"/Pepper/Visual_{shade}" if palette else "/Pepper/Visual")
        visual.GetPrim().GetReferences().AddReference(str(ASSETS / f"Pepper_{shade}.usdc"))
        UsdGeom.Xformable(visual).AddScaleOp().Set(Gf.Vec3f(*scale))
        if palette:
            visual.CreateVisibilityAttr().Set("inherited" if shade == color else "invisible")
    # Legacy ellipsoid, full-mesh contact, or explicit body-only contact experiment.
    points, faces = [], []
    nlat, nlon = 10, 16
    for i in range(nlat + 1):
        theta = math.pi * i / nlat
        for j in range(nlon):
            phi = 2 * math.pi * j / nlon
            points.append((cfg.diameter / 2 * math.sin(theta) * math.cos(phi),
                           cfg.diameter / 2 * math.sin(theta) * math.sin(phi),
                           cfg.length * .40 * math.cos(theta) - cfg.length * .08))
    for i in range(nlat):
        for j in range(nlon):
            a, b = i * nlon + j, i * nlon + (j + 1) % nlon
            faces.extend([(a, b, a+nlon), (b, b+nlon, a+nlon)])
    mesh = UsdGeom.Mesh.Define(stage, "/Pepper/Collision")
    if mesh_contact:
        # Match the visible asset (including its visible stem), rather than an
        # unrelated ellipsoid. Convex decomposition preserves the jaw-accessible shape.
        source = Usd.Stage.Open(str(ASSETS / f"Pepper_{color}.usdc"))
        points, indices, counts = [], [], []
        transforms = UsdGeom.XformCache()
        for prim in source.Traverse():
            if not prim.IsA(UsdGeom.Mesh):
                continue
            source_mesh = UsdGeom.Mesh(prim)
            transform = transforms.GetLocalToWorldTransform(prim)
            offset = len(points)
            points.extend([tuple(np.asarray(transform.Transform(Gf.Vec3d(*map(float,p)))) * scale)
                           for p in source_mesh.GetPointsAttr().Get()])
            indices.extend([offset+int(i) for i in source_mesh.GetFaceVertexIndicesAttr().Get()])
            counts.extend(list(source_mesh.GetFaceVertexCountsAttr().Get()))
        if not points:
            raise ValueError("Fruit visual mesh contains no geometry")
        if body_hull:
            from .contact_geometry import pepper_body_hull
            points, triangles = pepper_body_hull(points, cfg.length)
            points = points.tolist()
            indices = triangles.ravel().tolist()
            counts = [3] * len(triangles)
        mesh.CreatePointsAttr(points)
        mesh.CreateFaceVertexCountsAttr(counts)
        mesh.CreateFaceVertexIndicesAttr(indices)
    else:
        mesh.CreatePointsAttr(points)
    if not mesh_contact:
        mesh.CreateFaceVertexCountsAttr([3] * len(faces))
        mesh.CreateFaceVertexIndicesAttr(np.asarray(faces).ravel().tolist())
    mesh.CreateVisibilityAttr("invisible")
    UsdPhysics.CollisionAPI.Apply(mesh.GetPrim())
    UsdPhysics.MeshCollisionAPI.Apply(mesh.GetPrim()).CreateApproximationAttr("convexDecomposition" if mesh_contact and not body_hull else "convexHull")
    stage.GetRootLayer().Save()
    return str(path), np.asarray(meta["attachment"]) * scale


def find_body_path(stage, suffix):
    matches = [str(p.GetPath()) for p in stage.Traverse()
               if str(p.GetPath()).startswith("/World/envs/env_0/Robot/")
               and p.GetName() == suffix and p.HasAPI(UsdPhysics.RigidBodyAPI)]
    if len(matches) != 1:
        raise RuntimeError(f"Expected one body {suffix}, found {matches}")
    return matches[0].replace("env_0", "env_.*")


def collision_hull_points(path):
    """Extreme points of authored collider; same extrema as its convex hull."""
    from scipy.spatial import ConvexHull
    stage=Usd.Stage.Open(str(path))
    points=np.asarray(UsdGeom.Mesh(stage.GetPrimAtPath('/Pepper/Collision')).GetPointsAttr().Get(),dtype=np.float32)
    return points[ConvexHull(points).vertices].copy()
