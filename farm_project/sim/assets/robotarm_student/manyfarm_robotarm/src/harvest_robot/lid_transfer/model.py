"""Offline geometry, random loading and measured-state transfer checks (SI)."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from functools import lru_cache
import importlib.util
import json
from pathlib import Path
import xml.etree.ElementTree as ET

import numpy as np
from scipy.spatial.transform import Rotation

ROOT = Path(__file__).resolve().parents[3]
DESCRIPTION = ROOT / "src/smartfarm_description"
SOURCES = {
    "harvest": DESCRIPTION / "urdf/harvest_robot.urdf",
    "transport": DESCRIPTION / "urdf/transport_robot.portable.urdf",
}
PEPPERS = DESCRIPTION / "meshes/pepper"
OUT = ROOT / "outputs/harvest_transfer"

_spec = importlib.util.spec_from_file_location(
    "transfer_urdf_geometry", DESCRIPTION / "scripts/model_geometry.py"
)
_geometry = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_geometry)


@dataclass
class Settings:
    count: int = 8
    diameter: float = .070
    length: float = .075
    mass: float = .009
    physics_dt: float = 1 / 240
    motor_speed: float = .4  # rad/s; below both URDF pinion limits
    motor_stiffness: float = 20.0
    motor_damping: float = 2.0
    load_min_s: float = 3.0
    load_timeout_s: float = 15.0
    motor_timeout_s: float = 12.0
    transfer_timeout_s: float = 15.0
    dwell_s: float = .6
    linear_speed: float = .08
    angular_speed: float = 1.0
    boundary_tolerance: float = .002
    slide_tolerance: float = .002
    motor_tolerance: float = .03
    transport_yaw: float = 0.0  # lid motion along world Y avoids harvest frame's X posts
    transport_offset_x: float = 0.0
    transport_offset_y: float = 0.0

    def validate(self):
        if self.count != 8:
            raise ValueError("This experiment requires exactly eight peppers")
        for key, value in asdict(self).items():
            if not np.isfinite(value):
                raise ValueError(f"Non-finite setting: {key}")
            if key not in ("transport_offset_x", "transport_offset_y", "transport_yaw") and value <= 0:
                raise ValueError(f"Setting must be positive: {key}")
        if self.load_timeout_s <= self.load_min_s + self.dwell_s:
            raise ValueError("Loading timeout must exceed minimum settling time + dwell")
        if self.motor_speed > .5:
            raise ValueError("Motor speed must stay within the source URDF .5 rad/s limit")


def load_settings(path: Path | None = None) -> Settings:
    return Settings(**json.loads(path.read_text())) if path else Settings()


def source_paths():
    paths = set(SOURCES.values()) | {
        DESCRIPTION / "config/assembly.yaml", DESCRIPTION / "config/transport.json",
        DESCRIPTION / "scripts/model_geometry.py", PEPPERS / "manifest.json",
    }
    for source in SOURCES.values():
        for mesh in ET.parse(source).getroot().iter("mesh"):
            paths.add(_geometry.mesh_path(mesh.get("filename"), source).resolve())
    paths.update(PEPPERS.glob("Pepper_*.usdc"))
    paths.update(p for p in (PEPPERS / "textures").rglob("*") if p.is_file())
    return sorted(paths)


@lru_cache(maxsize=2)
def lid_spec(name):
    root = ET.parse(SOURCES[name]).getroot()
    motor = "harvest_lid_pinion_joint" if name == "harvest" else "lid_pinion_joint"
    slides = (("box_bottom_left_joint", "box_bottom_right_joint") if name == "harvest"
              else ("top_lid_left_joint", "top_lid_right_joint"))
    motor_joint = root.find(f"joint[@name='{motor}']")
    limit = motor_joint.find("limit")
    travel = float(root.find(f"joint[@name='{slides[0]}']/limit").get("upper"))
    if name == "harvest":
        radius = 1 / float(motor_joint.find("mimic").get("multiplier"))
    else:
        radius = float(root.find(f"joint[@name='{slides[0]}']/mimic").get("multiplier"))
    angle = min(float(limit.get("upper")), travel / radius)
    return dict(motor=motor, slides=slides, radius=radius, travel=travel,
                open_angle=angle, effort=float(limit.get("effort")),
                velocity=float(limit.get("velocity")))


def scene_geometry(cfg):
    """Align the real box centers; preserve both original ground heights."""
    harvest = _geometry.fk(ET.parse(SOURCES["harvest"]).getroot())["harvest_box"]
    transport = _geometry.fk(ET.parse(SOURCES["transport"]).getroot())["cargo_box"]
    tc = json.loads((DESCRIPTION / "config/transport.json").read_text())
    # Internal harvest dimensions come from the source wall collisions.
    root = ET.parse(SOURCES["harvest"]).getroot()
    wall = root.find("link[@name='box_left_wall']/collision/geometry/box")
    length, thickness, height = map(float, wall.get("size").split())
    rear = root.find("link[@name='box_front_wall']/collision/geometry/box")
    width = float(rear.get("size").split()[1])
    floor = root.find("joint[@name='box_left_wall_joint']/origin")
    zc = float(floor.get("xyz").split()[2])
    # The CAD panel top is below the wall's lower edge; use the actual panel
    # collision surface, not the wall bottom, as the loading floor boundary.
    floor_mesh = root.find("link[@name='box_bottom_left']/collision/geometry/mesh")
    floor_points = _geometry.stl(_geometry.mesh_path(floor_mesh.get("filename"), SOURCES["harvest"])).reshape(-1, 3)
    floor_points *= np.array(list(map(float, floor_mesh.get("scale", "1 1 1").split())))
    lid_mount = _geometry.fk(root)["box_bottom_left"]
    panel_top = lid_mount[2, 3] + floor_points[:, 2].max() - harvest[2, 3]
    harvest_lo = np.array([-length / 2 + thickness, -width / 2, panel_top])
    harvest_hi = np.array([length / 2 - thickness, width / 2, zc + height / 2])
    yaw = Rotation.from_euler("z", cfg.transport_yaw).as_matrix()
    # Cargo URDF origin is the front lower edge, rather than the box center.
    cargo_center = (transport @ np.array([-tc["box_length"] / 2, 0, 0, 1]))[:3]
    base = np.eye(4)
    base[:3, :3] = yaw
    base[:2, 3] = harvest[:2, 3] - (yaw @ cargo_center)[:2]
    base[:2, 3] += [cfg.transport_offset_x, cfg.transport_offset_y]
    cargo_pose = base @ transport
    cargo_link = ET.parse(SOURCES["transport"]).getroot().find("link[@name='cargo_box']")
    floor_box = cargo_link.find("collision/geometry/box")
    floor_origin = cargo_link.find("collision/origin")
    floor_z = float(floor_origin.get("xyz").split()[2]) + float(floor_box.get("size").split()[2]) / 2
    w, t = tc["box_width"], tc["wall_thickness"]
    return dict(harvest_pose=harvest, transport_base=base, transport_box_pose=cargo_pose,
                harvest_bounds=(harvest_lo, harvest_hi),
                transport_bounds=(np.array([-tc["box_length"] + t, -w / 2 + t, floor_z]),
                                  np.array([-t, w / 2 - t, tc["box_height"]])),
                vertical_gap_m=float(harvest[2, 3] - (cargo_pose[2, 3] + tc["box_height"])))


def pepper_local_bounds(cfg):
    meta = json.loads((PEPPERS / "manifest.json").read_text())["Pepper_Red"]
    bounds = np.array(meta["bounds"])
    size = bounds[1] - bounds[0]
    scale = np.array([cfg.diameter / max(size[:2])] * 2 + [cfg.length / size[2]])
    return bounds * scale


def random_poses(cfg, seed, geometry):
    """Eight random poses inside disjoint subvolumes; no initial intersections.

    Gravity settles these into a pile before either lid opens. Stratification
    avoids unreliable dense random packing in the original 20 cm box.
    """
    rng = np.random.default_rng(seed)
    bounds = pepper_local_bounds(cfg)
    center, half = bounds.mean(axis=0), (bounds[1] - bounds[0]) / 2
    lower, upper = geometry["harvest_bounds"]
    cell = (upper - lower) / 2
    if np.min(half) * 2 + .004 >= np.min(cell):
        raise ValueError("Peppers are too large for eight non-overlapping loading cells")
    poses = []
    for index in rng.permutation(8):
        xyz = np.array([index % 2, (index // 2) % 2, index // 4])
        lo, hi = lower + xyz * cell + .002, lower + (xyz + 1) * cell - .002
        for _ in range(10000):
            rotation = Rotation.random(random_state=rng).as_matrix()
            extent = np.abs(rotation) @ half
            if np.all(hi - lo > 2 * extent):
                break
        else:
            raise ValueError("Cannot fit randomized pepper orientations inside the harvest box")
        p = rng.uniform(lo + extent, hi - extent) - rotation @ center
        t = geometry["harvest_pose"]
        quat = Rotation.from_matrix(t[:3, :3] @ rotation).as_quat()
        poses.append(dict(position=(t[:3, 3] + t[:3, :3] @ p).tolist(),
                          rotation_wxyz=quat[[3, 0, 1, 2]].tolist(),
                          color="Red" if len(poses) % 2 == 0 else "Yellow"))
    return poses


def world_points(position, quaternion_wxyz, points):
    quat = np.asarray(quaternion_wxyz)[[1, 2, 3, 0]]
    return np.asarray(points) @ Rotation.from_quat(quat).as_matrix().T + position


def inside_box(position, quaternion_wxyz, points, pose, bounds, tolerance=.002):
    """Whole authored collider, including stem; COM-only checks are insufficient."""
    world = world_points(position, quaternion_wxyz, points)
    local = (world - pose[:3, 3]) @ pose[:3, :3]
    lower, upper = bounds
    return bool(np.all(local.min(axis=0) >= lower - tolerance)
                and np.all(local.max(axis=0) <= upper + tolerance))


class TransferMonitor:
    """Experiment states, deliberately separate from ROS/RL task enums."""
    def __init__(self, cfg):
        self.cfg = cfg
        self.phase = "LOADING"
        self.elapsed = 0.0
        self.dwell = 0.0
        self.harvest_angle = 0.0
        self.transport_angle = 0.0
        self.reason = None

    @property
    def finished(self):
        return self.phase in ("SUCCESS", "FAILED")

    def fail(self, reason):
        self.phase, self.reason = "FAILED", reason

    def transition(self, phase):
        self.phase, self.elapsed, self.dwell = phase, 0.0, 0.0

    def advance(self, dt, *, loaded, received, escaped, finite, harvest_open, transport_open):
        if self.finished:
            return
        self.elapsed += dt
        if not finite:
            self.fail("NONFINITE_PHYSICS")
        elif escaped:
            self.fail("PEPPER_ESCAPED")
        elif self.phase == "LOADING":
            self.dwell = self.dwell + dt if loaded == self.cfg.count else 0.0
            if self.elapsed >= self.cfg.load_min_s and self.dwell >= self.cfg.dwell_s:
                self.transition("OPEN_TRANSPORT")
            elif self.elapsed >= self.cfg.load_timeout_s:
                self.fail("HARVEST_LOADING_FAILED")
        elif self.phase == "OPEN_TRANSPORT":
            spec = lid_spec("transport")
            self.transport_angle = min(spec["open_angle"], self.transport_angle + self.cfg.motor_speed * dt)
            if self.transport_angle == spec["open_angle"] and transport_open:
                self.dwell += dt
                if self.dwell >= .2:
                    self.transition("OPEN_HARVEST")
            else:
                self.dwell = 0.0
            if self.elapsed >= self.cfg.motor_timeout_s:
                self.fail("TRANSPORT_LID_OPEN_FAILED")
        elif self.phase == "OPEN_HARVEST":
            if not transport_open:
                self.fail("TRANSPORT_LID_LOST_OPEN")
                return
            spec = lid_spec("harvest")
            self.harvest_angle = min(spec["open_angle"], self.harvest_angle + self.cfg.motor_speed * dt)
            if self.harvest_angle == spec["open_angle"] and harvest_open:
                self.transition("TRANSFER_SETTLE")
            elif self.elapsed >= self.cfg.motor_timeout_s:
                self.fail("HARVEST_LID_OPEN_FAILED")
        elif self.phase == "TRANSFER_SETTLE":
            if not (transport_open and harvest_open):
                self.fail("LID_LOST_OPEN")
                return
            self.dwell = self.dwell + dt if received == self.cfg.count else 0.0
            if self.dwell >= self.cfg.dwell_s:
                self.phase = "SUCCESS"
            elif self.elapsed >= self.cfg.transfer_timeout_s:
                self.fail("TRANSFER_INCOMPLETE")
