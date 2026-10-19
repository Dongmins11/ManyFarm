"""Executed-target labels for the selected 60Hz Teacher; no privileged inputs."""
import numpy as np

ACTION_CONTRACT = 'teacher60_normalized_executed_joint_target_v1'


def encode_targets(target, lower, upper):
    target, lower, upper = (np.asarray(x, dtype=np.float64) for x in (target, lower, upper))
    if any(x.shape != (6,) for x in (target, lower, upper)) or not np.isfinite([target, lower, upper]).all():
        raise ValueError('Expected finite six joint targets/limits')
    if np.any(upper <= lower) or np.any(target < lower-1e-6) or np.any(target > upper+1e-6):
        raise ValueError('Executed target outside joint limits; do not clip the demonstration')
    return (2*(target-lower)/(upper-lower)-1).astype(np.float32)


def decode_targets(action, lower, upper):
    action = np.asarray(action)
    if action.shape != (6,) or not np.isfinite(action).all() or np.any(np.abs(action) > 1.000001):
        raise ValueError('Invalid normalized target')
    return np.asarray(lower)+(action+1)*.5*(np.asarray(upper)-np.asarray(lower))


def summarize_observations(rows):
    """Truth exists only in diagnostic JSON, never policy NPZ inputs."""
    result = {}
    for phase in sorted({r['phase'] for r in rows}):
        selected = [r for r in rows if r['phase'] == phase]
        errors = [r['target_error_m'] for r in selected if r['target_error_m'] is not None]
        lost = longest = 0
        for r in selected:
            lost = 0 if r['target']['valid'] else lost+1
            longest = max(longest, lost)
        result[phase] = dict(samples=len(selected), valid=sum(r['target']['valid'] for r in selected),
            fresh=sum(r['target']['valid'] and r['target']['age_s'] <= .05 for r in selected),
            max_invalid_s=longest*.05,
            error_median_m=float(np.median(errors)) if errors else None,
            error_p95_m=float(np.percentile(errors,95)) if errors else None)
    return result
