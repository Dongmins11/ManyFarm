"""Reward-only entry/capture guidance; no actuator, contact or termination edits."""
import math
import torch


def jaw_gap(q):
    return .0281*(1-torch.cos(q))+.0616*torch.sin(q)


def readiness_potential(distance, orientation_error, weight=8., distance_scale=.035,
                        angle_scale_deg=35.):
    # horizontal_grasp_alignment returns a sine projection, not radians.
    angle = torch.asin(orientation_error.clamp(0., 1.))
    return weight*torch.exp(-(distance/distance_scale).square()
                           -(angle/math.radians(angle_scale_deg)).square())


def closing_progress(previous_q, q, best, entered, distance, orientation_error,
                     displacement, attached, confirmed, bilateral, terminal,
                     diameter, upper_q, parameters):
    """Pay measured NEW closure once, only after entry with little stem motion.

    Opening/reclosing cannot farm progress. A blocked negative command earns
    nothing. Initial entry with an already partly closed jaw earns nothing.
    The nominal gap goal caps reward; it is not a servo target or grasp test.
    """
    largest_gap = jaw_gap(torch.as_tensor(upper_q, device=q.device, dtype=q.dtype))
    span = (largest_gap-(diameter-.004)).clamp_min(.005)
    score = ((largest_gap-jaw_gap(q))/span).clamp(0., 1.)
    measured = ((jaw_gap(previous_q)-jaw_gap(q))/span).clamp_min(0.)
    eligible = (entered & attached & ~confirmed & ~bilateral & ~terminal
                & (displacement <= parameters['maximum_stem_motion_m']))
    updated = torch.where(eligible, torch.maximum(best, score), best)
    new_progress = torch.minimum((updated-best).clamp_min(0.), measured)
    quality = readiness_potential(distance, orientation_error, weight=1.,
        distance_scale=parameters['closing_center_scale_m'],
        angle_scale_deg=parameters['angle_scale_deg'])
    reward = parameters['closing_budget']*new_progress*quality
    return reward, updated, eligible, new_progress
