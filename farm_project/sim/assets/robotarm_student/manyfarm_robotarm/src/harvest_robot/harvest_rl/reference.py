"""Slow, orientation-aware diagnostic pull. Not the RL policy or a hardware driver."""
import numpy as np
from scipy.optimize import least_squares
from scipy.spatial.transform import Rotation


def pull_waypoint(initial_pose, progress, distance=.06):
    u = np.clip(progress, 0., 1.)
    # Zero velocity/acceleration at both endpoints.
    blend = 10*u**3 - 15*u**4 + 6*u**5
    return initial_pose[:3,3] + np.array([-distance*blend, 0., 0.])


def solve_pull_ik(kin, q, initial_pose, desired, diameter=.070):
    def residual(arm_q):
        pose=kin.grasp_fk(np.r_[arm_q,q[-1]],diameter)
        rotation=Rotation.from_matrix(initial_pose[:3,:3] @ pose[:3,:3].T).as_rotvec()
        return np.r_[pose[:3,3]-desired, .08*rotation]
    result=least_squares(residual,np.clip(q[:5],kin.lower[:5]+.001,kin.upper[:5]-.001),
        bounds=(kin.lower[:5]+.001,kin.upper[:5]-.001),max_nfev=40)
    pose=kin.grasp_fk(np.r_[result.x,q[-1]],diameter)
    error=float(np.linalg.norm(pose[:3,3]-desired))
    if not np.isfinite(result.x).all() or error > .01:
        raise RuntimeError(f"Pull IK outside 10mm position tolerance: {error}")
    return result.x, error
