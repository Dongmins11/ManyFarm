"""Explicit T_parent_child rigid transforms and local covariance propagation."""
import math
import numpy as np
from .core import wrap_angle


def finite(value, shape):
    a = np.array(value, dtype=float, copy=True)
    if a.shape != shape or not np.isfinite(a).all():
        raise ValueError('invalid_shape_or_nonfinite:' + str(shape))
    return a


def transform(value):
    t = finite(value, (4, 4))
    # Same finite-array, rtol=0 acceptance tests, without generic allclose
    # setup. Keep every rigid-transform validation and its original tolerance.
    if not (np.abs(t[3]-[0,0,0,1]) <= 1e-10).all():
        raise ValueError('invalid_homogeneous_transform')
    r = t[:3, :3]
    if not (np.abs(r.T @ r-np.eye(3)) <= 1e-8).all() or abs(np.linalg.det(r)-1) > 1e-8:
        raise ValueError('proper_rotation_required')
    return t


def inverse(value):
    t = transform(value)
    result = np.eye(4)
    result[:3, :3] = t[:3, :3].T
    result[:3, 3] = -result[:3, :3] @ t[:3, 3]
    return result


def from_pose6(pose):
    x, y, z, roll, pitch, yaw = finite(pose, (6,))
    cr, sr, cp, sp, cy, sy = math.cos(roll), math.sin(roll), math.cos(pitch), math.sin(pitch), math.cos(yaw), math.sin(yaw)
    result = np.eye(4)
    result[:3, :3] = [[cy*cp, cy*sp*sr-sy*cr, cy*sp*cr+sy*sr],
                      [sy*cp, sy*sp*sr+cy*cr, sy*sp*cr-cy*sr], [-sp, cp*sr, cp*cr]]
    result[:3, 3] = [x, y, z]
    return result


def pose6(value):
    t = transform(value)
    r = t[:3, :3]
    pitch = math.asin(float(np.clip(-r[2, 0], -1, 1)))
    if abs(math.cos(pitch)) < 1e-7:
        raise ValueError('euler_singularity_not_a_valid_local_pose')
    return np.array([*t[:3, 3], math.atan2(r[2, 1], r[2, 2]), pitch, math.atan2(r[1, 0], r[0, 0])])


def planar(value):
    return pose6(value)[[0, 1, 5]]


def with_planar(value, q):
    p = pose6(value)
    p[[0, 1, 5]] = finite(q, (3,))
    return from_pose6(p)


def covariance(value, n, *, definite=True):
    c = finite(value, (n, n))
    if not (np.abs(c-c.T) <= 1e-12+1e-10*np.abs(c.T)).all():
        raise ValueError('asymmetric_joint_covariance')
    c = (c+c.T)/2
    if definite:
        try:
            np.linalg.cholesky(c)
        except np.linalg.LinAlgError as exc:
            raise ValueError('joint_covariance_not_positive_definite') from exc
    elif np.linalg.eigvalsh(c).min() < -1e-12*max(1, np.max(np.abs(c))):
        raise ValueError('joint_covariance_not_positive_semidefinite')
    return c


def propagate(evaluate, mean, joint_covariance, steps, *, angle_indices=()):
    """Finite-difference local J C J^T; C includes all declared cross terms.

    No diagonal noise is added to conceal rank deficiency. Steps are numerical
    differentiation settings, not sensor noise or operational thresholds.
    """
    x = np.array(mean, dtype=float)
    if x.ndim != 1 or not np.isfinite(x).all():
        raise ValueError('finite_latent_mean_required')
    c = covariance(joint_covariance, len(x), definite=False)
    step = finite(steps, x.shape)
    if np.any(step <= 0):
        raise ValueError('positive_numeric_steps_required')
    y = np.array(evaluate(x), dtype=float)
    if y.ndim != 1 or not np.isfinite(y).all():
        raise ValueError('invalid_linearization_output')
    j = np.empty((len(y), len(x)))
    for i, h in enumerate(step):
        plus, minus = x.copy(), x.copy()
        plus[i] += h; minus[i] -= h
        d = np.array(evaluate(plus))-np.array(evaluate(minus))
        for index in angle_indices:
            d[index] = wrap_angle(float(d[index]))
        j[:, i] = d/(2*h)
    if not np.isfinite(j).all():
        raise ValueError('invalid_jacobian')
    output = j @ c @ j.T
    return (output+output.T)/2, j
