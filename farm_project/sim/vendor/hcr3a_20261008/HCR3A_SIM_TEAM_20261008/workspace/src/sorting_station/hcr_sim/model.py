"""SI layout and approximate six-axis kinematics. No simulator imports."""

import json
import math
from pathlib import Path
import numpy as np
from scipy.spatial.transform import Rotation
from scipy.optimize import least_squares

ROOT = Path(__file__).resolve().parents[3]
CONFIG = ROOT / "src/smartfarm_description/config/hcr3a_station.json"
OUT = ROOT / "outputs/sorting_station/hcr_sim"
NAMES = "ABCD"


def load_config(path=CONFIG):
    cfg = json.loads(Path(path).read_text())
    r = cfg["intake"]
    if not 0 < r["rise"] < r["slope_length"]:
        raise ValueError("Intake rise must be below slope length")
    if not np.isclose(4 * r["lane_clear_width"] + 5 * r["board"], r["width"]):
        raise ValueError("Four clear lanes + five boards must equal intake width")
    for group, keys in [
        (
            "physics",
            [
                "foam_static_friction",
                "foam_dynamic_friction",
                "pad_static_friction",
                "pad_dynamic_friction",
                "pepper_mass",
            ],
        )
    ]:
        if any(cfg[group][key] <= 0 for key in keys):
            raise ValueError("Non-positive physics value")
    return cfg


def lane_centers(cfg):
    r = cfg["intake"]
    pitch = r["lane_clear_width"] + r["board"]
    return {n: (1.5 - i) * pitch for i, n in enumerate(NAMES)}


def ramp_surface_z(cfg, x):
    r = cfg["intake"]
    run = math.sqrt(r["slope_length"] ** 2 - r["rise"] ** 2)
    return cfg["base_z"] + (x - r["low_x"]) * r["rise"] / run


def pickup_points(cfg):
    x = cfg["intake"]["low_x"] + 0.048
    return {
        n: np.array(
            [x, y, ramp_surface_z(cfg, x) + cfg["physics"]["pepper_length"] / 2]
        )
        for n, y in lane_centers(cfg).items()
    }


def storage_points(cfg):
    s = cfg["storage"]
    return {
        "RED": np.array(
            [s["drop_x"] - 0.05, s["width"] / 4, s["drop_z"] + s["release_clearance"]]
        ),
        "YELLOW": np.array(
            [s["drop_x"] - 0.05, -s["width"] / 4, s["drop_z"] + s["release_clearance"]]
        ),
    }


class Arm:
    """Approximate industrial 6R chain, separate from actual Rodi joint zeros."""

    def __init__(self, cfg):
        self.cfg = cfg
        r = cfg["robot"]
        self.origins = [
            (0, 0, r["shoulder_z"]),
            (0, 0, 0),
            (r["upper_length"], 0, 0),
            (r["fore_length"], 0, 0),
            (0, 0, 0),
            (r["wrist_length"], 0, 0),
        ]
        self.axes = [(0, 0, 1), (0, 1, 0), (0, 1, 0), (1, 0, 0), (0, 1, 0), (1, 0, 0)]
        self.tcp = np.array([r["tcp_length"], 0, 0])
        self.seed = np.array([0, -1.0, 1.9, 0, math.pi / 2 - 0.9, 0])
        self.lower = np.array(
            [-2 * math.pi, -math.pi, -2.79, -2 * math.pi, -2 * math.pi, -2 * math.pi]
        )
        self.upper = -self.lower

    def frames(self, q):
        t = np.eye(4)
        t[2, 3] = self.cfg["base_z"]
        out = []
        for origin, axis, a in zip(self.origins, self.axes, q):
            tr = np.eye(4)
            tr[:3, 3] = origin
            rot = np.eye(4)
            rot[:3, :3] = Rotation.from_rotvec(np.asarray(axis) * a).as_matrix()
            t = t @ tr @ rot
            out.append(t.copy())
        return out

    def fk(self, q):
        t = self.frames(q)[-1].copy()
        t[:3, 3] += t[:3, :3] @ self.tcp
        return t

    def ik(self, point, seed=None, orientation=None):
        # Tool +X downward, jaw closing axis +Y; world orientation is fixed.
        target = (
            Rotation.from_euler("y", math.pi / 2).as_matrix()
            if orientation is None
            else orientation
        )
        seed = self.seed.copy() if seed is None else np.asarray(seed).copy()

        def residual(q):
            t = self.fk(q)
            return np.r_[
                t[:3, 3] - point,
                0.15 * Rotation.from_matrix(target @ t[:3, :3].T).as_rotvec(),
            ]

        candidates = [
            seed,
            self.seed.copy(),
            np.array([math.pi, -1, 1.5, 0, 0, math.pi]),
        ]
        best = None
        for q in candidates:
            fit = least_squares(
                residual,
                np.clip(q, self.lower + 0.001, self.upper - 0.001),
                bounds=(self.lower, self.upper),
                max_nfev=180,
                ftol=1e-9,
                xtol=1e-9,
                gtol=1e-9,
            )
            err = np.linalg.norm(residual(fit.x))
            if best is None or err < best[0]:
                best = (err, fit.x)
            if err < 1e-5:
                break
        if best[0] > 0.003:
            raise ValueError(
                f"Unreachable approximate-arm pose {point}: residual={best[0]}"
            )
        q = best[1].copy()
        # Multi-turn axes share the same pose every 2*pi. Pick the equivalent
        # nearest the caller's seed to avoid a gratuitous full wrist turn.
        for i in (0, 3, 4, 5):
            choices = [
                q[i] + k * 2 * math.pi
                for k in range(-2, 3)
                if self.lower[i] <= q[i] + k * 2 * math.pi <= self.upper[i]
            ]
            q[i] = min(choices, key=lambda value: abs(value - seed[i]))
        return q


def teach(cfg):
    arm = Arm(cfg)
    points = {
        "HOME": np.array([0.25, 0, 0.32]),
        "TRANSFER": np.array([0.02, 0.05, 0.48]),
    }
    for n, p in pickup_points(cfg).items():
        points[n + "_PICK"] = p
        points[n + "_UP"] = p + [0, 0, 0.12]
    points.update(storage_points(cfg))
    for color, p in storage_points(cfg).items():
        points[color + "_CLEAR"] = np.array([-0.10, p[1], p[2]])
    poses = {}
    seed = arm.seed
    for n, p in points.items():
        rot = (
            (Rotation.from_euler("z", math.pi).as_matrix())
            if n.startswith(("RED", "YELLOW"))
            else None
        )
        seed = arm.ik(p, seed, rot)
        poses[n] = {"xyz": p.tolist(), "q": seed.tolist()}
    return poses
