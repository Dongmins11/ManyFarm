"""Prepare Isaac Lab USD assets for the OMX sorting station.

Import this module only after AppLauncher has started Isaac Sim. Generated files
live under outputs/sorting_station and never touch harvest_robot caches.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET

import numpy as np

from .settings import ASSET_CACHE, PEPPER_ASSET_ROOT, SIM_VISUAL_CONFIG, SORTING_URDF, WORKSPACE_ROOT


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def prepare_sorting_usd() -> Path:
    """Convert the current combined sorting_station URDF into a fixed-base USD."""
    from isaaclab.sim.converters import UrdfConverter, UrdfConverterCfg

    tree = ET.parse(SORTING_URDF)
    root = tree.getroot()

    # Match the physical OMX-F appearance used for source-demo collection.
    # Only visual material colors are overridden; collision geometry/materials
    # and all kinematics remain untouched.
    visual_cfg = json.loads(SIM_VISUAL_CONFIG.read_text(encoding="utf-8"))
    robot_rgba = " ".join(str(float(v)) for v in visual_cfg["robot"]["visual_rgba"])
    omx_visual_links = {f"omx_link{i}" for i in range(8)}
    for link in root.findall("link"):
        if link.get("name") not in omx_visual_links:
            continue
        for color in link.findall("./visual/material/color"):
            color.set("rgba", robot_rgba)

    joint_names = {joint.get("name") for joint in root.findall("joint")}
    link_names = {link.get("name") for link in root.findall("link")}
    if "omx_joint5" not in joint_names or "omx_link0" not in link_names:
        raise RuntimeError(
            "sorting_station.urdf still contains the legacy 4-DOF OpenMANIPULATOR-X. "
            "Save all workspace edits, then run: "
            "/home/bhc/isaac/env_isaaclab/bin/python "
            "src/sorting_station/migrate_to_omxf.py"
        )
    # OMX wrist roll is mechanically multi-turn on the Leader side. The source
    # URDF uses a finite +/-2*pi limit, which makes PhysX stop after about one
    # revolution even when the Leader keeps rotating. Keep the source URDF intact
    # and widen only the derived Isaac asset to +/-100 turns.
    wrist_joint = root.find("joint[@name='omx_joint5']")
    if wrist_joint is None:
        raise RuntimeError("Missing omx_joint5 in sorting station URDF")
    wrist_limit = wrist_joint.find("limit")
    if wrist_limit is None:
        raise RuntimeError("omx_joint5 is missing its URDF limit element")
    wrist_limit_rad = 100.0 * 2.0 * np.pi
    wrist_limit.set("lower", str(-wrist_limit_rad))
    wrist_limit.set("upper", str(wrist_limit_rad))

    # Expose both jaw DOFs and command symmetric targets. Native mimic remains
    # disabled until contact/teleoperation regression tests pass with it.
    secondary_gripper = root.find("joint[@name='omx_gripper_joint_2']")
    if secondary_gripper is not None:
        mimic = secondary_gripper.find("mimic")
        if mimic is not None:
            secondary_gripper.remove(mimic)

    # The station is merged into one fixed-base USD. Once fixed joints are
    # merged, left_ramp/right_ramp can no longer be targeted reliably by name,
    # so their high-friction URDF collisions cannot receive a separate material.
    # Strip only those two collision geometries here; scene.py respawns the same
    # ramp geometry as dedicated static low-friction colliders.
    for ramp_name in ("left_ramp", "right_ramp"):
        ramp_link = root.find(f"link[@name='{ramp_name}']")
        if ramp_link is None:
            raise RuntimeError(f"Missing sorting ramp link: {ramp_name}")
        collisions = list(ramp_link.findall("collision"))
        if not collisions:
            raise RuntimeError(f"Sorting ramp has no collision geometry: {ramp_name}")
        for collision in collisions:
            ramp_link.remove(collision)

    sources: dict[str, str] = {
        str(SORTING_URDF.relative_to(WORKSPACE_ROOT)): _sha256(SORTING_URDF),
        str(SIM_VISUAL_CONFIG.relative_to(WORKSPACE_ROOT)): _sha256(SIM_VISUAL_CONFIG),
        "__sorting_converter_recipe__": "explicit_dual_gripper_v6_black_visuals_multiturn_j5_external_ramps",
    }

    for mesh in root.findall(".//mesh"):
        filename = mesh.get("filename")
        if filename.startswith("package://smartfarm_description/"):
            relative = filename.split("package://smartfarm_description/", 1)[1]
            path = WORKSPACE_ROOT / "src" / "smartfarm_description" / relative
        else:
            path = (SORTING_URDF.parent / filename).resolve()
        if not path.is_file():
            raise FileNotFoundError(path)
        mesh.set("filename", str(path))
        sources[str(path.relative_to(WORKSPACE_ROOT))] = _sha256(path)

    digest = hashlib.sha256(json.dumps(sources, sort_keys=True).encode("utf-8")).hexdigest()[:16]
    destination = ASSET_CACHE / f"sorting_{digest}"
    destination.mkdir(parents=True, exist_ok=True)
    derived_urdf = destination / "sorting_station_absolute.urdf"
    tree.write(derived_urdf, encoding="utf-8", xml_declaration=True)

    manifest = destination / "manifest.json"
    converter = UrdfConverter(
        UrdfConverterCfg(
            asset_path=str(derived_urdf),
            usd_dir=str(destination),
            usd_file_name="sorting_station.usd",
            force_usd_conversion=not manifest.exists(),
            fix_base=True,
            merge_fixed_joints=True,
            self_collision=True,
            make_instanceable=False,
            collider_type="convex_decomposition",
            joint_drive=UrdfConverterCfg.JointDriveCfg(
                gains=UrdfConverterCfg.JointDriveCfg.PDGainsCfg(stiffness=45.0, damping=2.5)
            ),
        )
    )
    metadata = {
        "source_urdf": str(SORTING_URDF),
        "source_files": sources,
        "asset_input_sha256": digest,
        "usd": str(converter.usd_path),
        "scope": "sorting_station_only",
        "note": "Independent OMX sorting asset; does not use harvest_robot cache or settings.",
    }
    manifest.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    return Path(converter.usd_path)


def prepare_pepper_usd(
    color: str,
    *,
    diameter: float = 0.070,
    length: float = 0.090,
    mass: float = 0.060,
    source_root: Path | None = None,
    cache_root: Path | None = None,
) -> Path:
    """Build a rigid pepper with visual geometry separated from collision geometry.

    The visual mesh remains the detailed pepper model, but collision uses one
    convex hull around the merged body. The previous convex-decomposition
    collider preserved deep lobe grooves and could mechanically hook onto the
    OMX fingertips even after the gripper opened. A single convex hull keeps a
    pepper-like volume without the capsule proxy's excessive rolling and gives
    a much cleaner release contact surface.
    """
    from pxr import Gf, PhysxSchema, Usd, UsdGeom, UsdPhysics

    color_key = color.capitalize()
    if color_key not in {"Red", "Yellow", "Green"}:
        raise ValueError(f"Unsupported pepper color: {color}")

    source_root = PEPPER_ASSET_ROOT if source_root is None else Path(source_root)
    cache_root = ASSET_CACHE if cache_root is None else Path(cache_root)
    source = source_root / f"Pepper_{color_key}.usdc"
    manifest_path = source_root / "manifest.json"
    if not source.is_file() or not manifest_path.is_file():
        raise FileNotFoundError(f"Missing converted pepper assets under {source_root}")

    meta = json.loads(manifest_path.read_text(encoding="utf-8"))[f"Pepper_{color_key}"]
    bounds = np.asarray(meta["bounds"], dtype=float)
    size = bounds[1] - bounds[0]
    scale = np.array([diameter / max(size[:2]), diameter / max(size[:2]), length / size[2]])

    digest = hashlib.sha256(
        json.dumps(
            {
                "source": _sha256(source),
                "diameter": diameter,
                "length": length,
                "mass": mass,
                "collider": "visual_mesh_single_convex_hull_v2_release_safe",
            },
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()[:16]
    destination = cache_root / f"pepper_{color_key.lower()}_{digest}.usda"
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        return destination

    stage = Usd.Stage.CreateNew(str(destination))
    UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.z)
    UsdGeom.SetStageMetersPerUnit(stage, 1.0)

    root = UsdGeom.Xform.Define(stage, "/Pepper").GetPrim()
    stage.SetDefaultPrim(root)
    UsdPhysics.RigidBodyAPI.Apply(root)
    UsdPhysics.MassAPI.Apply(root).CreateMassAttr(float(mass))
    PhysxSchema.PhysxRigidBodyAPI.Apply(root).CreateEnableCCDAttr(True)

    visual = UsdGeom.Xform.Define(stage, "/Pepper/Visual")
    visual.GetPrim().GetReferences().AddReference(str(source))
    UsdGeom.Xformable(visual).AddScaleOp().Set(Gf.Vec3f(*map(float, scale)))

    source_stage = Usd.Stage.Open(str(source))
    xform_cache = UsdGeom.XformCache()
    points: list[tuple[float, float, float]] = []
    indices: list[int] = []
    counts: list[int] = []
    for prim in source_stage.Traverse():
        if not prim.IsA(UsdGeom.Mesh):
            continue
        mesh = UsdGeom.Mesh(prim)
        transform = xform_cache.GetLocalToWorldTransform(prim)
        offset = len(points)
        for p in mesh.GetPointsAttr().Get():
            transformed = np.asarray(
                transform.Transform(Gf.Vec3d(*map(float, p))),
                dtype=float,
            ) * scale
            points.append(tuple(map(float, transformed)))
        indices.extend(offset + int(i) for i in mesh.GetFaceVertexIndicesAttr().Get())
        counts.extend(int(v) for v in mesh.GetFaceVertexCountsAttr().Get())

    if not points:
        raise RuntimeError(f"Pepper visual asset has no mesh geometry: {source}")

    collision = UsdGeom.Mesh.Define(stage, "/Pepper/Collision")
    collision.CreatePointsAttr(points)
    collision.CreateFaceVertexIndicesAttr(indices)
    collision.CreateFaceVertexCountsAttr(counts)
    collision.CreateVisibilityAttr("invisible")
    UsdPhysics.CollisionAPI.Apply(collision.GetPrim())
    UsdPhysics.MeshCollisionAPI.Apply(collision.GetPrim()).CreateApproximationAttr(
        "convexHull"
    )

    stage.GetRootLayer().Save()
    return destination
