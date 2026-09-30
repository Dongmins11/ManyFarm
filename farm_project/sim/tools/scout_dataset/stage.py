"""USD scene inspection and persistent fruit labels (Isaac Sim 5.1)."""
from __future__ import annotations

from collections import Counter
from datetime import datetime
from itertools import product
from pathlib import Path
import re
import shutil
import hashlib
import json
import math
import numpy as np

from .core import Fruit, bed_geometry_from_points, classify_fruit_side

FRUIT_PATH = re.compile(r"^(.*?/Bed_(\d+))/Fruits/Pepper_\d+_(red|yellow|green)$")
EDGE_NAME = re.compile(r"^Bed_Edge_(\d+)(?:_.*)?$")


def _validate_rotation_limit(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
        raise ValueError("fruit_rotation.max_degrees must be a finite number >= 0")
    return float(value)


def load_fruit_rotation_settings(project_root):
    """Read settings on every action so JSON edits apply without restarting."""
    config = json.loads((Path(project_root)/"sim/config/scout_dataset.json").read_text(encoding="utf-8"))
    settings = config["fruit_rotation"]
    seed = settings["seed"]
    if isinstance(seed, bool) or not isinstance(seed, int):
        raise ValueError("fruit_rotation.seed must be an integer")
    return {"max_degrees": _validate_rotation_limit(settings["max_degrees"]), "seed": seed}


def randomize_fruit_rotations(stage, seed=930, max_degrees=10.0):
    """Local XYZ rotation offsets relative to original transforms; never cumulative."""
    from pxr import Usd, UsdGeom, Gf
    max_degrees = _validate_rotation_limit(max_degrees)
    op_name = "xformOp:rotateXYZ:pepperDatasetJitter"
    planned = []
    for prim in stage.Traverse():
        path = str(prim.GetPath())
        if not FRUIT_PATH.fullmatch(path):
            continue
        xf = UsdGeom.Xformable(prim)
        if not xf or prim.IsInstanceProxy():
            raise ValueError(f"Fruit root cannot be edited: {path}")
        existing = prim.GetAttribute(op_name)
        if existing and UsdGeom.XformOp(existing).GetOpType() != UsdGeom.XformOp.TypeRotateXYZ:
            raise ValueError(f"Conflicting jitter operation: {path}")
        # Stable per-prim random values: adding another fruit does not reshuffle others.
        digest = hashlib.sha256(f"{int(seed)}|{path}".encode()).digest()
        rng = np.random.default_rng(int.from_bytes(digest[:8], "little"))
        angles = rng.uniform(-1.0, 1.0, 3) * max_degrees
        planned.append((prim, xf, angles))
    if not planned:
        raise ValueError("No Pepper fruit roots found")
    results = {}
    with Usd.EditContext(stage, stage.GetRootLayer()):
        for prim, xf, angles in planned:
            reset = xf.GetResetXformStack()
            ops = [op for op in xf.GetOrderedXformOps() if op.GetOpName() != op_name]
            attr = prim.GetAttribute(op_name)
            jitter = UsdGeom.XformOp(attr) if attr else xf.AddRotateXYZOp(
                UsdGeom.XformOp.PrecisionDouble, "pepperDatasetJitter")
            jitter.Set(Gf.Vec3d(*map(float, angles)))
            # Compose T * R_original * R_jitter * S for the existing fruit stack.
            # All original operations/values are retained. A repeated call replaces
            # this single extra operation instead of adding another rotation.
            index = len(ops)
            while index and ops[index-1].GetOpType() == UsdGeom.XformOp.TypeScale:
                index -= 1
            ops.insert(index, jitter)
            xf.SetXformOpOrder(ops, resetXformStack=reset)
            results[str(prim.GetPath())] = list(map(float, angles))
    return results


def randomize_current_stage_and_save(seed=930, max_degrees=10.0):
    max_degrees = _validate_rotation_limit(max_degrees)
    import omni.usd
    stage = omni.usd.get_context().get_stage()
    if stage is None:
        raise RuntimeError("Open the farm scene first")
    layer = stage.GetRootLayer()
    if layer.anonymous or not layer.realPath:
        raise RuntimeError("Save the current scene once with File > Save As")
    path = Path(layer.realPath)
    backup = path.with_name(path.name+".before_rotation_"+datetime.now().strftime("%Y%m%d_%H%M%S_%f"))
    shutil.copy2(path, backup)
    rotations = randomize_fruit_rotations(stage, seed, max_degrees)
    if not layer.Save():
        raise RuntimeError(f"Map save failed: {path}")
    print(f"[scout_dataset] {len(rotations)} peppers: local XYZ +/-{max_degrees} deg, seed={seed}", flush=True)
    print(f"[scout_dataset] Saved: {path}; previous map: {backup}", flush=True)
    return rotations


def inspect_fruits(stage):
    fruits = {}
    for prim in stage.Traverse():
        path = str(prim.GetPath())
        match = FRUIT_PATH.fullmatch(path)
        if not match:
            continue
        bed, number, suffix = match.groups()
        attr = prim.GetAttribute("crop:color")
        color = str(attr.Get()).lower() if attr and attr.Get() else suffix
        if color != suffix:
            raise ValueError(f"Fruit name/crop:color conflict: {path}")
        attr = prim.GetAttribute("crop:bedId")
        if attr and attr.Get() is not None and int(attr.Get()) != int(number):
            raise ValueError(f"Fruit path/crop:bedId conflict: {path}")
        if color in ("red", "yellow"):
            fruits[path] = Fruit(path, bed, int(number), color)
    if not fruits:
        raise RuntimeError("No red/yellow /Bed_NN/Fruits/Pepper_NNNN_color prims found")
    return fruits


def label_stage(stage):
    """Author labels only on fruit roots, in the current map's root layer."""
    from pxr import Sdf, Usd, UsdSemantics
    fruits = inspect_fruits(stage)
    # Legacy SemanticsAPI labels, if any, are migrated by the official utility.
    try:
        from isaacsim.core.utils.semantics import upgrade_prim_semantics_to_labels
    except ImportError:
        upgrade_prim_semantics_to_labels = None
    with Usd.EditContext(stage, stage.GetRootLayer()):
        for fruit in fruits.values():
            prim = stage.GetPrimAtPath(fruit.path)
            if prim.IsInstanceProxy():
                raise RuntimeError(f"Fruit root is an instance proxy; cannot author label: {fruit.path}")
            if upgrade_prim_semantics_to_labels:
                upgrade_prim_semantics_to_labels(prim, include_descendants=False)
            for name, labels in (("class", ["pepper_"+fruit.color]),
                                 ("physical_bed", [fruit.bed_path])):
                api = UsdSemantics.LabelsAPI.Apply(prim, name)
                api.CreateLabelsAttr().Set(labels)
                if list(api.GetLabelsAttr().Get()) != labels:
                    raise RuntimeError(f"Label verification failed: {fruit.path}")
            prim.CreateAttribute("dataset:gtId", Sdf.ValueTypeNames.String).Set(fruit.path)
            prim.CreateAttribute("dataset:classId", Sdf.ValueTypeNames.Int).Set(fruit.class_id)
    return fruits


def save_labeled_copy(stage, output=None):
    """Export a labelled root layer next to its source, preserving relative refs.

    The returned map is a normal root USD layer, not a flattened asset package.
    Assets and payloads continue to resolve in the user's existing project.
    """
    source = stage.GetRootLayer()
    if source.anonymous or not source.realPath:
        raise RuntimeError("Use File > Save As for this scene before labeling")
    source_path = Path(source.realPath).resolve()
    target = Path(output).expanduser().resolve() if output else source_path.with_name(
        source_path.stem.removesuffix("_vision_labeled")+"_vision_labeled.usd")
    if target.parent != source_path.parent:
        raise ValueError("Save labelled map beside source to preserve relative asset references")
    if target == source_path:
        raise ValueError("Use label_current_stage_and_save() for explicit in-place saving")
    if target.exists():
        backup = target.with_name(target.name+".bak_"+datetime.now().strftime("%Y%m%d_%H%M%S_%f"))
        shutil.copy2(target, backup)
    if not source.Export(str(target)):
        raise RuntimeError(f"Could not export map: {target}")
    return target


def label_current_stage_and_save(graph):
    """Script Editor: label the currently open scene and save its root map."""
    import omni.usd
    stage = omni.usd.get_context().get_stage()
    if stage is None:
        raise RuntimeError("Open the farm scene first")
    layer = stage.GetRootLayer()
    if layer.anonymous or not layer.realPath:
        raise RuntimeError("Save this new scene once with File > Save As")
    path = Path(layer.realPath)
    backup = path.with_name(path.name+".before_labels_"+datetime.now().strftime("%Y%m%d_%H%M%S_%f"))
    shutil.copy2(path, backup)
    fruits = label_stage(stage)
    assign_section_membership(stage, fruits, inspect_beds(stage, fruits), graph)
    if not layer.Save():
        raise RuntimeError(f"Map save failed: {path}")
    print(f"[scout_dataset] Labels saved: {path}", flush=True)
    print(f"[scout_dataset] Previous file: {backup}", flush=True)
    print(f"[scout_dataset] {dict(Counter(f.color for f in fruits.values()))}", flush=True)
    return fruits


def inspect_beds(stage, fruits):
    from pxr import Usd, UsdGeom
    if UsdGeom.GetStageUpAxis(stage) != "Z" or abs(UsdGeom.GetStageMetersPerUnit(stage)-1) > 1e-8:
        raise ValueError("Current project requires metres and Z-up")
    cache = UsdGeom.BBoxCache(Usd.TimeCode.Default(), ["default", "render"], useExtentsHint=False)
    groups = {}
    for prim in stage.Traverse():
        match = EDGE_NAME.fullmatch(prim.GetName())
        if not match or EDGE_NAME.fullmatch(prim.GetParent().GetName()):
            continue
        number = int(match.group(1))
        bbox = cache.ComputeWorldBound(prim)
        bounds, matrix = bbox.GetRange(), bbox.GetMatrix()
        if bounds.IsEmpty():
            raise RuntimeError(f"Missing Bed_Edge geometry: {prim.GetPath()}")
        from pxr import Gf
        corners = [matrix.Transform(Gf.Vec3d(*xyz)) for xyz in product(*zip(bounds.GetMin(), bounds.GetMax()))]
        group = groups.setdefault(number, {"points": [], "paths": []})
        group["points"].extend([[float(p[0]), float(p[1])] for p in corners])
        group["paths"].append(str(prim.GetPath()))
    paths = {}
    for fruit in fruits.values():
        if fruit.physical_bed in paths and paths[fruit.physical_bed] != fruit.bed_path:
            raise ValueError("Duplicate physical bed number under different vegetation roots")
        paths[fruit.physical_bed] = fruit.bed_path
    result = {}
    for number, path in paths.items():
        if number not in groups:
            raise RuntimeError(f"Cannot find Bed_Edge_{number} frame geometry. Check background reference.")
        item = groups[number]
        result[number] = bed_geometry_from_points(number, path, item["points"], item["paths"])
    return result


def assign_section_membership(stage, fruits, beds, graph):
    """Persist a unique survey section for each fruit, independent of camera pose.

    Use fruit root placement (the scene's crop anchor), not image left/right or
    whichever part of its silhouette happens to be visible through the foliage.
    """
    from pxr import Usd, UsdGeom, UsdSemantics, Sdf
    section_ids = {}
    for sid, section in graph.get("survey_sections", {}).items():
        key = (section["evaluation_bed_prim"].rstrip("/"), section["survey_side"])
        if key in section_ids:
            raise ValueError(f"Multiple section IDs for the same bed side: {key}")
        section_ids[key] = sid
    cache = UsdGeom.XformCache()
    membership = {}
    for path, fruit in fruits.items():
        position = cache.GetLocalToWorldTransform(stage.GetPrimAtPath(path)).ExtractTranslation()
        side = classify_fruit_side(position, beds[fruit.physical_bed])
        key = (fruit.bed_path, side)
        if key not in section_ids:
            raise ValueError(f"Missing graph section for {key}")
        membership[path] = {"side": side, "section_id": section_ids[key],
                            "placement_world_m": list(position)}
    with Usd.EditContext(stage, stage.GetRootLayer()):
        for path, member in membership.items():
            prim = stage.GetPrimAtPath(path)
            prim.CreateAttribute("dataset:surveySide", Sdf.ValueTypeNames.String).Set(member["side"])
            prim.CreateAttribute("dataset:surveySection", Sdf.ValueTypeNames.String).Set(member["section_id"])
            UsdSemantics.LabelsAPI.Apply(prim, "survey_section").CreateLabelsAttr().Set([member["section_id"]])
    return membership


def validate_render_geometry(stage, fruits):
    from pxr import Usd, UsdGeom
    missing = []
    roots = [stage.GetPrimAtPath(p) for p in fruits]
    roots += [p for p in stage.Traverse() if re.fullmatch(r"Tree_\d+", p.GetName())
              and p.GetParent().GetName() == "Trees"]
    for root in roots:
        meshes = [p for p in Usd.PrimRange(root, Usd.TraverseInstanceProxies()) if p.IsA(UsdGeom.Mesh)]
        if not meshes or not any(UsdGeom.Mesh(p).GetPointsAttr().Get() for p in meshes):
            missing.append(str(root.GetPath()))
    if missing:
        raise RuntimeError(f"Missing render meshes/references ({len(missing)}): {missing[:4]}")


def source_camera(stage, config):
    from pxr import UsdGeom
    path = config.get("source_prim", "auto")
    if path == "auto":
        matches = [p for p in stage.Traverse() if p.IsA(UsdGeom.Camera) and p.GetName() == "scout_camera"]
        if len(matches) != 1:
            raise RuntimeError(f"Expected one scout_camera, found {len(matches)}. Set camera.source_prim.")
        prim = matches[0]
    else:
        prim = stage.GetPrimAtPath(path)
        if not prim or not prim.IsA(UsdGeom.Camera):
            raise ValueError(f"Not a USD Camera: {path}")
    cam = UsdGeom.Camera(prim)
    matrix = np.asarray(UsdGeom.XformCache().GetLocalToWorldTransform(prim), float).T
    if not np.allclose(matrix[:3, :3].T@matrix[:3, :3], np.eye(3), atol=1e-4):
        raise ValueError("Scout camera has scaled parent transforms")
    forward = -matrix[:3, 2]
    pitch = float(np.degrees(np.arcsin(np.clip(forward[2], -1, 1))))
    return {"prim_path": str(prim.GetPath()), "world_height_m": float(matrix[2, 3]),
            "pitch_deg": pitch, "focalLength": float(cam.GetFocalLengthAttr().Get()),
            "horizontalAperture": float(cam.GetHorizontalApertureAttr().Get()),
            "verticalAperture": float(cam.GetVerticalApertureAttr().Get()),
            "horizontalApertureOffset": float(cam.GetHorizontalApertureOffsetAttr().Get()),
            "verticalApertureOffset": float(cam.GetVerticalApertureOffsetAttr().Get()),
            "clippingRange": list(cam.GetClippingRangeAttr().Get())}


def configure_camera(cam, source, config):
    from pxr import Gf
    w, h = config["resolution"]
    focal = source["focalLength"]
    mode = config["intrinsics_mode"]
    if mode == "calibrated_K":
        K = np.asarray(config["K"], float)
        if K.shape != (3, 3) or K[0, 0] <= 0 or K[1, 1] <= 0:
            raise ValueError("calibrated_K requires a valid 3x3 matrix for this resolution")
        if not np.allclose(K[2], [0, 0, 1]) or abs(K[0, 1])+abs(K[1, 0]) > 1e-10:
            raise ValueError("Only zero-skew pinhole K is supported")
        ha, va = focal*w/K[0, 0], focal*h/K[1, 1]
        ho, vo = (w/2-K[0, 2])*ha/w, (K[1, 2]-h/2)*va/h
    elif mode == "source_horizontal_fov":
        ha, ho = source["horizontalAperture"], source["horizontalApertureOffset"]
        va = ha*h/w
        vo = source["verticalApertureOffset"]*va/source["verticalAperture"]
    else:
        raise ValueError(f"Unknown intrinsics_mode: {mode}")
    cam.CreateProjectionAttr().Set("perspective")
    cam.CreateFocalLengthAttr().Set(focal)
    cam.CreateHorizontalApertureAttr().Set(ha)
    cam.CreateVerticalApertureAttr().Set(va)
    cam.CreateHorizontalApertureOffsetAttr().Set(ho)
    cam.CreateVerticalApertureOffsetAttr().Set(vo)
    cam.CreateClippingRangeAttr().Set(Gf.Vec2f(*source["clippingRange"]))
    cam.CreateFStopAttr().Set(0.)  # Defocus is controlled by the RGB postprocessor.
    K = [[w*focal/ha, 0., w/2-ho*w/ha], [0., h*focal/va, h/2+vo*h/va], [0., 0., 1.]]
    return {"resolution": [w, h], "K": K, "mode": mode,
            "horizontal_fov_deg": float(np.degrees(2*np.arctan(ha/(2*focal)))),
            "vertical_fov_deg": float(np.degrees(2*np.arctan(va/(2*focal)))),
            "source_camera": source,
            "note": "Source camera FOV is preserved horizontally; real D435 calibration is not inferred from a photo."}
