"""PhysX motor/mimic articulations and free peppers, imported after AppLauncher."""
import hashlib
import json
import math
from pathlib import Path
import xml.etree.ElementTree as ET

import numpy as np
from scipy.spatial.transform import Rotation

from .model import PEPPERS, SOURCES, _geometry, lid_spec


def derive_robot(name, destination):
    """Freeze parked joints, retain geometry, expose one rotary lid motor.

    The harvest source uses a slide as master. Reverse only the derivative's
    mimic relation so a physical rotary motor can drive both passive racks.
    """
    source = SOURCES[name]
    tree = ET.parse(source)
    spec = lid_spec(name)
    active = {spec["motor"], *spec["slides"]}
    home = dict(zip(("shoulder_pan", "shoulder_lift", "elbow_flex", "wrist_flex",
                     "wrist_roll", "gripper"), (0, -1.39, .77, .62, .0487963268, 1.1)))
    for joint in tree.findall("joint"):
        if joint.get("name") in active:
            for mimic in joint.findall("mimic"):
                joint.remove(mimic)
            if joint.get("name") in spec["slides"]:
                ET.SubElement(joint, "mimic", joint=spec["motor"],
                              multiplier=str(spec["radius"]), offset="0")
        elif joint.get("type") != "fixed":
            # Preserve the actual HOME transform before making arm joints fixed.
            angle = home.get(joint.get("name").split("/")[-1], 0.0)
            if angle:
                axis = np.array(list(map(float, joint.find("axis").get("xyz").split())))
                t = _geometry.origin(joint.find("origin"))
                t[:3, :3] = t[:3, :3] @ Rotation.from_rotvec(axis * angle).as_matrix()
                origin = joint.find("origin")
                if origin is None:
                    origin = ET.SubElement(joint, "origin")
                origin.set("xyz", " ".join(map(str, t[:3, 3])))
                origin.set("rpy", " ".join(map(str, Rotation.from_matrix(t[:3, :3]).as_euler("xyz"))))
            joint.set("type", "fixed")
            for tag in ("axis", "limit", "dynamics", "mimic"):
                for element in joint.findall(tag):
                    joint.remove(element)
    for mesh in tree.getroot().iter("mesh"):
        path = _geometry.mesh_path(mesh.get("filename"), source).resolve()
        if not path.is_file():
            raise FileNotFoundError(path)
        mesh.set("filename", str(path))
    destination.parent.mkdir(parents=True, exist_ok=True)
    tree.write(destination, encoding="utf-8", xml_declaration=True)
    return destination


def prepare_robot(name, cfg, cache):
    from isaaclab.sim.converters import UrdfConverter, UrdfConverterCfg

    cache = cache.resolve()
    derived = derive_robot(name, cache / f"{name}_motor.urdf")
    digest = hashlib.sha256(derived.read_bytes()).hexdigest()[:16]
    spec = lid_spec(name)
    gains = {spec["motor"]: cfg.motor_stiffness, **{j: 0.0 for j in spec["slides"]}}
    damping = {spec["motor"]: cfg.motor_damping, **{j: 0.0 for j in spec["slides"]}}
    converter = UrdfConverter(UrdfConverterCfg(
        asset_path=str(derived), usd_dir=str(cache / name / digest),
        usd_file_name=f"{name}.usd", fix_base=True, merge_fixed_joints=True,
        make_instanceable=False, collider_type="convex_decomposition",
        # Installed Isaac Lab forwards this directly to importer.parse_mimic.
        # Disable importer mimic conversion: it drops forward references and
        # mishandles mixed angular/linear units. Author checked constraints below.
        self_collision=False, convert_mimic_joints_to_normal_joints=False,
        joint_drive=UrdfConverterCfg.JointDriveCfg(
            drive_type="force", target_type={spec["motor"]: "position",
                **{j: "none" for j in spec["slides"]}},
            gains=UrdfConverterCfg.JointDriveCfg.PDGainsCfg(stiffness=gains, damping=damping)),
    ))
    return Path(converter.usd_path)


def apply_rack_coupling():
    """Author actual rack/pinion constraints, with USD's degree-based gearing."""
    import isaaclab.sim as sim
    from pxr import PhysxSchema, UsdPhysics

    stage = sim.get_current_stage()
    audit = {}
    for name in ("harvest", "transport"):
        spec = lid_spec(name)
        prefix = f"/World/{name.capitalize()}/joints/"
        motor = stage.GetPrimAtPath(prefix + spec["motor"])
        if not motor.IsA(UsdPhysics.RevoluteJoint):
            raise RuntimeError(f"Missing rotary motor: {motor.GetPath()}")
        audit[name] = []
        for slide in spec["slides"]:
            prim = stage.GetPrimAtPath(prefix + slide)
            if not prim.IsA(UsdPhysics.PrismaticJoint):
                raise RuntimeError(f"Missing rack: {prefix + slide}")
            joint = UsdPhysics.PrismaticJoint(prim)
            joint.CreateLowerLimitAttr(0.0)
            joint.CreateUpperLimitAttr(spec["travel"])
            # Single-DOF joint instance/reference axis tokens are irrelevant in
            # PhysX; rotX follows NVIDIA's rack/pinion schema regression example.
            mimic = PhysxSchema.PhysxMimicJointAPI.Apply(prim, UsdPhysics.Tokens.rotX)
            mimic.CreateReferenceJointRel().SetTargets([motor.GetPath()])
            mimic.CreateReferenceJointAxisAttr(UsdPhysics.Tokens.rotX)
            gearing = -spec["radius"] * math.pi / 180
            mimic.CreateGearingAttr(gearing)
            mimic.CreateOffsetAttr(0.0)
            # Compliance attributes are not exposed by the installed schema
            # Python API. Its default constraint is rigid (as in PhysX's demo).
            audit[name].append(dict(slide=str(prim.GetPath()), reference=str(motor.GetPath()),
                                   usd_gearing_m_per_degree=gearing, travel_m=spec["travel"]))
    return audit


def spawn_robot(name, usd, cfg, geometry):
    import isaaclab.sim as sim
    from isaaclab.assets import Articulation, ArticulationCfg
    from isaaclab.actuators import ImplicitActuatorCfg

    pose = np.eye(4) if name == "harvest" else geometry["transport_base"]
    q = Rotation.from_matrix(pose[:3, :3]).as_quat()[[3, 0, 1, 2]]
    spec = lid_spec(name)
    return Articulation(ArticulationCfg(
        prim_path="/World/" + name.capitalize(),
        spawn=sim.UsdFileCfg(usd_path=str(usd), activate_contact_sensors=True,
            rigid_props=sim.RigidBodyPropertiesCfg(solver_position_iteration_count=16,
                solver_velocity_iteration_count=4),
            collision_props=sim.CollisionPropertiesCfg(contact_offset=.001, rest_offset=0),
            articulation_props=sim.ArticulationRootPropertiesCfg(enabled_self_collisions=False)),
        init_state=ArticulationCfg.InitialStateCfg(pos=tuple(pose[:3, 3]), rot=tuple(q)),
        actuators={
            "motor": ImplicitActuatorCfg(joint_names_expr=[spec["motor"]],
                stiffness=cfg.motor_stiffness, damping=cfg.motor_damping,
                effort_limit_sim=spec["effort"], velocity_limit_sim=spec["velocity"]),
            "passive_racks": ImplicitActuatorCfg(joint_names_expr=list(spec["slides"]),
                stiffness=0, damping=0, effort_limit_sim=0,
                velocity_limit_sim=spec["velocity"] * spec["radius"]),
        },
    ))


def prepare_pepper(color, cfg, cache):
    """Use shared visual geometry + full-body/stem convex decomposition collider."""
    from pxr import Gf, PhysxSchema, Usd, UsdGeom, UsdPhysics

    source = PEPPERS / f"Pepper_{color}.usdc"
    meta = json.loads((PEPPERS / "manifest.json").read_text())[f"Pepper_{color}"]
    size = np.diff(meta["bounds"], axis=0)[0]
    scale = np.array([cfg.diameter / max(size[:2])] * 2 + [cfg.length / size[2]])
    cache.mkdir(parents=True, exist_ok=True)
    path = cache / f"pepper_{color}.usda"
    stage = Usd.Stage.CreateNew(str(path))
    UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.z)
    UsdGeom.SetStageMetersPerUnit(stage, 1.0)
    root = UsdGeom.Xform.Define(stage, "/Pepper").GetPrim()
    stage.SetDefaultPrim(root)
    UsdPhysics.RigidBodyAPI.Apply(root)
    UsdPhysics.MassAPI.Apply(root).CreateMassAttr(cfg.mass)
    PhysxSchema.PhysxRigidBodyAPI.Apply(root).CreateEnableCCDAttr(True)
    visual = UsdGeom.Xform.Define(stage, "/Pepper/Visual")
    visual.GetPrim().GetReferences().AddReference(str(source))
    UsdGeom.Xformable(visual).AddScaleOp().Set(Gf.Vec3f(*map(float, scale)))
    original = Usd.Stage.Open(str(source))
    transforms = UsdGeom.XformCache()
    points, indices, counts = [], [], []
    for prim in original.Traverse():
        if not prim.IsA(UsdGeom.Mesh):
            continue
        mesh = UsdGeom.Mesh(prim)
        t = transforms.GetLocalToWorldTransform(prim)
        offset = len(points)
        points.extend(tuple(np.asarray(t.Transform(Gf.Vec3d(*map(float, p)))) * scale)
                      for p in mesh.GetPointsAttr().Get())
        indices.extend(offset + int(i) for i in mesh.GetFaceVertexIndicesAttr().Get())
        counts.extend(int(n) for n in mesh.GetFaceVertexCountsAttr().Get())
    if not points:
        raise RuntimeError(f"No geometry in {source}")
    collision = UsdGeom.Mesh.Define(stage, "/Pepper/Collision")
    collision.CreatePointsAttr(points)
    collision.CreateFaceVertexIndicesAttr(indices)
    collision.CreateFaceVertexCountsAttr(counts)
    collision.CreateVisibilityAttr("invisible")
    UsdPhysics.CollisionAPI.Apply(collision.GetPrim())
    UsdPhysics.MeshCollisionAPI.Apply(collision.GetPrim()).CreateApproximationAttr("convexDecomposition")
    stage.GetRootLayer().Save()
    # Extreme points suffice for whole-mesh containment in a convex box.
    from scipy.spatial import ConvexHull
    points = np.asarray(points)
    return path, points[ConvexHull(points).vertices]


def spawn_peppers(cfg, poses, cache):
    import isaaclab.sim as sim
    from isaaclab.assets import RigidObject, RigidObjectCfg

    assets = {c: prepare_pepper(c, cfg, cache) for c in ("Red", "Yellow")}
    fruits, hulls = [], []
    for i, pose in enumerate(poses):
        path, hull = assets[pose["color"]]
        fruits.append(RigidObject(RigidObjectCfg(
            prim_path=f"/World/Peppers/Pepper_{i}",
            spawn=sim.UsdFileCfg(usd_path=str(path),
                rigid_props=sim.RigidBodyPropertiesCfg(
                    solver_position_iteration_count=16, solver_velocity_iteration_count=4,
                    linear_damping=.05, angular_damping=.05),
                collision_props=sim.CollisionPropertiesCfg(contact_offset=.001, rest_offset=0)),
            init_state=RigidObjectCfg.InitialStateCfg(pos=tuple(pose["position"]),
                rot=tuple(pose["rotation_wxyz"])),
        )))
        hulls.append(hull)
    return fruits, hulls


def bind_materials():
    import isaaclab.sim as sim
    from pxr import PhysxSchema, Usd, UsdPhysics, UsdShade

    stage = sim.get_current_stage()
    material_cfg = sim.RigidBodyMaterialCfg(static_friction=.5, dynamic_friction=.4, restitution=.02)
    material_cfg.func("/World/Materials/Cargo", material_cfg)
    material = UsdShade.Material.Get(stage, "/World/Materials/Cargo")
    for root in ("/World/Harvest", "/World/Transport", "/World/Peppers"):
        for prim in list(Usd.PrimRange(stage.GetPrimAtPath(root))):
            if prim.IsInstance():
                prim.SetInstanceable(False)
        # Reapply after uninstancing; importer instances previously hid meshes.
        sim.modify_collision_properties(root, sim.CollisionPropertiesCfg(contact_offset=.001, rest_offset=0))
        for prim in Usd.PrimRange(stage.GetPrimAtPath(root)):
            if prim.HasAPI(UsdPhysics.RigidBodyAPI):
                PhysxSchema.PhysxRigidBodyAPI.Apply(prim).CreateEnableCCDAttr(True)
            if prim.HasAPI(UsdPhysics.CollisionAPI):
                binding = UsdShade.MaterialBindingAPI.Apply(prim)
                binding.Bind(material, bindingStrength=UsdShade.Tokens.strongerThanDescendants,
                             materialPurpose="physics")
                resolved, _ = binding.ComputeBoundMaterial("physics")
                if resolved.GetPath() != material.GetPath():
                    raise RuntimeError(f"Material failed to resolve: {prim.GetPath()}")
