"""Build three-part USD station and approximate articulated HCR robot."""

from pathlib import Path
import math
import json
import hashlib
import numpy as np
from .model import ROOT, OUT, lane_centers, ramp_surface_z


def create_station(cfg):
    import importlib.util

    path = ROOT / "src/smartfarm_description/scripts/hcr3a_environment.py"
    spec = importlib.util.spec_from_file_location("hcr3a_environment", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.create_station(cfg)


def prepare_robot(cfg):
    from isaaclab.sim.converters import UrdfConverter, UrdfConverterCfg
    import importlib.util

    script = ROOT / "src/smartfarm_description/scripts/generate_hcr3a.py"
    spec = importlib.util.spec_from_file_location("generate_hcr3a", script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    source = module.generate(cfg, OUT / "assets/hcr3a_functional.urdf")
    digest = hashlib.sha256(source.read_bytes()).hexdigest()[:12]
    dest = OUT / "assets" / digest
    dest.mkdir(parents=True, exist_ok=True)
    c = UrdfConverterCfg(
        asset_path=str(source),
        usd_dir=str(dest),
        usd_file_name="hcr3a.usd",
        fix_base=True,
        merge_fixed_joints=False,
        make_instanceable=False,
        joint_drive=UrdfConverterCfg.JointDriveCfg(
            drive_type="force",
            target_type="position",
            gains=UrdfConverterCfg.JointDriveCfg.PDGainsCfg(
                stiffness=1200.0, damping=80.0
            ),
        ),
    )
    return Path(UrdfConverter(c).usd_path)


def spawn_robot(usd, cfg, contacts=False):
    import isaaclab.sim as sim
    from isaaclab.assets import Articulation, ArticulationCfg
    from isaaclab.actuators import ImplicitActuatorCfg
    from pxr import UsdShade, UsdGeom, Sdf, Gf

    robot = Articulation(
        ArticulationCfg(
            prim_path="/World/HCRRobot",
            spawn=sim.UsdFileCfg(
                usd_path=str(usd),
                activate_contact_sensors=contacts,
                rigid_props=sim.RigidBodyPropertiesCfg(disable_gravity=True),
                collision_props=sim.CollisionPropertiesCfg(
                    contact_offset=0.001, rest_offset=0
                ),
                articulation_props=sim.ArticulationRootPropertiesCfg(
                    enabled_self_collisions=False
                ),
            ),
            init_state=ArticulationCfg.InitialStateCfg(pos=(0, 0, cfg["base_z"])),
            actuators={
                "arm": ImplicitActuatorCfg(
                    joint_names_expr=["joint[1-6]"],
                    stiffness=1200,
                    damping=80,
                    effort_limit_sim=150,
                    velocity_limit_sim=2,
                ),
                "jaw": ImplicitActuatorCfg(
                    joint_names_expr=[".*_jaw"],
                    stiffness=400,
                    damping=20,
                    effort_limit_sim=20,
                    velocity_limit_sim=0.06,
                ),
            },
        )
    )
    stage = sim.get_current_stage()
    # URDF importer instances each link's geometry even with make_instanceable=False.
    # Expose the small primitive meshes so contact offsets and colors reach them.
    for prim in list(stage.Traverse()):
        if str(prim.GetPath()).startswith("/World/HCRRobot") and prim.IsInstance():
            prim.SetInstanceable(False)
    sim.modify_collision_properties(
        "/World/HCRRobot",
        sim.CollisionPropertiesCfg(contact_offset=0.001, rest_offset=0),
    )
    pad = UsdShade.Material.Get(stage, "/World/HCRMaterials/GripPad")
    palettes = {}
    for name, rgb in [
        ("Orange", (0.94, 0.32, 0.025)),
        ("Black", (0.055, 0.06, 0.065)),
        ("Pink", (0.95, 0.15, 0.45)),
    ]:
        mat = UsdShade.Material.Define(stage, "/World/HCRMaterials/Robot" + name)
        shader = UsdShade.Shader.Define(stage, str(mat.GetPath()) + "/Surface")
        shader.CreateIdAttr("UsdPreviewSurface")
        shader.CreateInput("diffuseColor", Sdf.ValueTypeNames.Color3f).Set(
            Gf.Vec3f(*rgb)
        )
        shader.CreateInput("roughness", Sdf.ValueTypeNames.Float).Set(0.45)
        mat.CreateSurfaceOutput().ConnectToSource(shader.ConnectableAPI(), "surface")
        palettes[name] = mat
    for prim in stage.Traverse():
        path = str(prim.GetPath())
        if not path.startswith("/World/HCRRobot"):
            continue
        if prim.IsA(UsdGeom.Mesh) or prim.IsA(UsdGeom.Cube):
            color = (
                "Pink"
                if "pad" in path
                else (
                    "Black"
                    if any(
                        "/" + n + "/" in path
                        for n in [
                            "base",
                            "link1",
                            "tool",
                            "left_finger",
                            "right_finger",
                        ]
                    )
                    else "Orange"
                )
            )
            UsdShade.MaterialBindingAPI.Apply(prim).Bind(
                palettes[color], UsdShade.Tokens.strongerThanDescendants
            )
        if "pad" in path:
            UsdShade.MaterialBindingAPI.Apply(prim).Bind(
                pad, UsdShade.Tokens.strongerThanDescendants, "physics"
            )
    return robot


def spawn_peppers(cfg, count_per_lane=2, in_transport=False):
    import isaaclab.sim as sim
    from isaaclab.assets import RigidObject, RigidObjectCfg

    # Shared standalone pepper geometry only, no harvest modules/caches.
    from sorting_sim.assets import prepare_pepper_usd
    from pxr import Usd, UsdGeom, Gf

    assets = {
        c: prepare_pepper_usd(
            c,
            diameter=cfg["physics"]["pepper_diameter"],
            length=cfg["physics"]["pepper_length"],
            mass=cfg["physics"]["pepper_mass"],
            source_root=ROOT / "src/smartfarm_description/meshes/pepper",
            cache_root=OUT / "assets/peppers",
        )
        for c in ["red", "yellow"]
    }
    fruits = []
    if in_transport:
        from .transport_asset import payload_poses
        from scipy.spatial import ConvexHull
        poses = payload_poses(cfg, count_per_lane * 4)
        collision_points = {}
        for color, asset in assets.items():
            stage = Usd.Stage.Open(str(asset))
            points = np.asarray(UsdGeom.Mesh(stage.GetPrimAtPath('/Pepper/Collision')).GetPointsAttr().Get())
            collision_points[color] = points[ConvexHull(points).vertices]
    for li, (lane, y) in enumerate(lane_centers(cfg).items()):
        for i in range(count_per_lane):
            color = "red" if (li + i) % 2 == 0 else "yellow"
            x = cfg["intake"]["low_x"] + 0.07 + i * 0.11
            z = ramp_surface_z(cfg, x) + cfg["physics"]["pepper_length"] / 2 + 0.005
            if in_transport:
                pose = poses[len(fruits)]
                x, cargo_y, z = pose['position']
            else:
                pose = dict(position=[x, y, z], rotation_wxyz=[1., 0., 0., 0.])
            path = f"/World/Peppers/{lane}_{i}_{color}"
            fruit = RigidObject(
                RigidObjectCfg(
                    prim_path=path,
                    spawn=sim.UsdFileCfg(
                        usd_path=str(assets[color]),
                        rigid_props=sim.RigidBodyPropertiesCfg(
                            linear_damping=0.2,
                            angular_damping=0.2,
                            max_linear_velocity=2,
                            max_angular_velocity=10,
                        ),
                        collision_props=sim.CollisionPropertiesCfg(
                            contact_offset=0.001, rest_offset=0
                        ),
                    ),
                    init_state=RigidObjectCfg.InitialStateCfg(pos=tuple(pose['position']), rot=tuple(pose['rotation_wxyz'])),
                )
            )
            fruits.append(
                dict(
                    object=fruit,
                    lane=lane,
                    color=color.upper(),
                    path=path,
                    sorted=False,
                    initial_pose=pose,
                    loading_points=collision_points[color] if in_transport else None,
                )
            )
    return fruits
