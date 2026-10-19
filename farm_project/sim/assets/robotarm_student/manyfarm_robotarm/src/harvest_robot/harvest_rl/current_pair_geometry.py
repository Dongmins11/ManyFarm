"""CPU validation of the current asset's legacy policy frame and two-fruit layouts."""
import numpy as np


def current_to_policy_frame(old, current, samples):
    frame=old.fk(np.zeros(6),'arm_2/base_link')@np.linalg.inv(current.fk(np.zeros(6),'arm_2/base_link'))
    if not np.allclose(frame[:3,:3]@[0,0,1],[0,0,1],atol=1e-7):
        raise ValueError('Frame mapping changes gravity; cannot reuse teacher')
    if not np.allclose(old.lower,current.lower) or not np.allclose(old.upper,current.upper):
        raise ValueError('Joint limits changed; teacher observation scaling requires review')
    errors={}
    for link in ('arm_2/shoulder_link','arm_2/upper_arm_link','arm_2/lower_arm_link',
                 'arm_2/wrist_link','arm_2/gripper_link','arm_2/moving_jaw_so101_v1_link',
                 'harvest_box','place_right','place_left'):
        errors[link]=max(float(np.max(abs(old.fk(q,link)-frame@current.fk(q,link)))) for q in samples)
    if max(errors.values())>1e-5:
        raise ValueError(f'Robot/box kinematics differ beyond a rigid frame change: {errors}')
    return frame,errors


def separated_pairs(points,spacing):
    if not np.isfinite(spacing) or spacing<=0:raise ValueError('Spacing must be positive')
    d=np.linalg.norm(points[:,None]-points[None,:],axis=-1)
    pairs=np.argwhere(np.triu(d>=spacing,k=1))
    if not len(pairs):raise ValueError('No separated reachable pair in requested range; do not silently shrink spacing')
    return pairs


def select_layout(points,pairs,seed,episode,target):
    # Same seed/episode creates identical target for single-vs-pair comparison.
    rng=np.random.default_rng(np.random.SeedSequence([seed,episode]))
    ids=pairs[rng.integers(len(pairs))].copy()
    if rng.random()<.5:ids=ids[::-1]
    slot=int(rng.integers(2)) if target=='random' else {'red':0,'yellow':1}[target]
    return points[ids].copy(),slot


def add_matched_distractor(positions,slot,candidates,spacing,seed,episode):
    eligible=candidates[np.linalg.norm(candidates-positions[slot],axis=-1)>=spacing]
    if not len(eligible):raise ValueError('No distractor meets spacing; target remains unchanged')
    rng=np.random.default_rng(np.random.SeedSequence([seed,episode,271]))
    result=positions.copy()
    result[1-slot]=eligible[rng.integers(len(eligible))]
    return result


def selected_teacher_observation(obs):
    """Keep the v6 one-target contract; distractor slots were constant in training.

    This deliberately provides NO obstacle awareness. Physics still includes the
    other fruit; record this limitation rather than amplifying unseen slots.
    """
    value=obs.clone()
    value[:,44:68]=0
    value[:,44:47]=value[:,25:28]
    value[:,68:76]=0
    value[:,68]=1
    return value
