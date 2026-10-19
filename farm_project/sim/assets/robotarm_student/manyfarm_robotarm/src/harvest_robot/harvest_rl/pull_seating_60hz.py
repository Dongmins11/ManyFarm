"""Bounded command-only alignment candidates, never modified fruit states."""
from dataclasses import asdict, dataclass
import hashlib
import math
from pathlib import Path

import numpy as np
from scipy.spatial.transform import Rotation

ROOT = Path(__file__).resolve().parents[3]
FILES = ['src/harvest_robot/harvest_rl/pull_seating_60hz.py',
         'src/harvest_robot/harvest_rl/pull_seating_probe.py',
         'scripts/teacher60_seating_case.py']


@dataclass(frozen=True)
class Alignment:
    orientation_weight_m: float = .08
    center_gain: float = 0.
    center_limit_m: float = .003
    center_axes: str = 'yz'
    center_ramp_s: float = 1.
    follow_gain: float = 0.
    follow_limit_deg: float = 15.
    seat_depth_m: float = 0.

    def __post_init__(self):
        if not all(math.isfinite(v) and v >= 0 for v in
                   (self.orientation_weight_m, self.center_gain, self.center_limit_m, self.center_ramp_s, self.follow_gain, self.follow_limit_deg, self.seat_depth_m)):
            raise ValueError('Alignment values must be finite and nonnegative')
        if self.center_axes not in ('yz', 'xyz') or self.center_limit_m > .005 or self.center_gain > 1 or self.follow_gain > 1 or self.follow_limit_deg > 20 or self.seat_depth_m > .005:
            raise ValueError('Only bounded <=5mm, <=1 gain centering is supported')
        if self.center_ramp_s <= 0:
            raise ValueError('Center ramp must be positive')


def center_correction(error, cfg, elapsed):
    result = np.array(error, dtype=float) * cfg.center_gain
    if cfg.center_axes == 'yz': result[0] = 0.
    magnitude = np.linalg.norm(result)
    if magnitude > cfg.center_limit_m: result *= cfg.center_limit_m / magnitude
    return result * min(1., max(0., elapsed / cfg.center_ramp_s))


def cartesian_action(kin, q, target, origin_pose, targets, cfg, alignment):
    pose = kin.grasp_fk(q, cfg.diameter); jac = np.zeros((6,5))
    weight = alignment.orientation_weight_m
    for j in range(5):
        dq = q.copy(); dq[j] += 1e-4
        moved = kin.grasp_fk(dq, cfg.diameter)
        jac[:3,j] = (moved[:3,3]-pose[:3,3])/1e-4
        jac[3:,j] = weight*Rotation.from_matrix(moved[:3,:3]@pose[:3,:3].T).as_rotvec()/1e-4
    error = np.r_[target-pose[:3,3], weight*Rotation.from_matrix(origin_pose[:3,:3]@pose[:3,:3].T).as_rotvec()]
    delta = np.linalg.solve(jac.T@jac+.002**2*np.eye(5), jac.T@error)
    desired = targets[:5]+np.clip(delta, -.25*cfg.step_dt, .25*cfg.step_dt)
    desired = np.clip(desired, q[:5]-.08, q[:5]+.08)
    actions = np.zeros(6)
    actions[:5] = np.clip((desired-targets[:5])/(cfg.action_speed*cfg.step_dt), -1., 1.)
    return actions


def contract(base, experiment, alignment):
    from .pull_speed_comparison import experiment_contract
    return dict(experiment_contract(base, experiment), pull_alignment=dict(
        schema='teacher60_loaded_seating_diagnostic_v1', settings=asdict(alignment),
        comparison_only=True, training_gate_eligible=False,
        files={f:hashlib.sha256((ROOT/f).read_bytes()).hexdigest() for f in FILES}))


def follow_orientation(origin, initial_fruit, current_fruit, alignment):
    initial = Rotation.from_quat(np.asarray(initial_fruit)[[1,2,3,0]])
    current = Rotation.from_quat(np.asarray(current_fruit)[[1,2,3,0]])
    vector = (current*initial.inv()).as_rotvec()*alignment.follow_gain
    angle = np.linalg.norm(vector)
    limit = math.radians(alignment.follow_limit_deg)
    if angle > limit: vector *= limit/angle
    result = np.array(origin,copy=True)
    result[:3,:3] = Rotation.from_rotvec(vector).as_matrix()@origin[:3,:3]
    return result
