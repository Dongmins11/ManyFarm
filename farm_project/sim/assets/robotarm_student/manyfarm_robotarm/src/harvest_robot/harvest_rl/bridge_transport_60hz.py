"""Evaluation-only transport handoff; helpers need neither Kit nor hardware."""
import torch


def next_transport(active, pull_success, failure, valid_detach, retained, qualified):
    first = ~active & pull_success & ~failure & valid_detach & retained & qualified
    return active | first, first


def transport_targets(previous, action, active, lower, upper, *, speed, dt, elapsed,
                      initial_scale=.25, ramp_s=3.):
    """Continue loaded targets; no new jaw origin, squeeze, or measured-q rebase."""
    scale = initial_scale + (1-initial_scale)*(elapsed/ramp_s).clamp(0., 1.)
    commands = action.clamp(-1., 1.).clone()
    commands[:, :5] *= scale[:, None]
    commands[:, -1] = 0.
    targets = previous.clone()
    proposed = (previous[:, :5]+commands[:, :5]*speed*dt).clamp(lower[:5], upper[:5])
    targets[active, :5] = proposed[active]
    return targets, commands, scale


def transport_observation(raw, target_relative, elapsed_steps, max_steps):
    """Legacy transport82: raw quaternion and one target in slot0, no color leak."""
    result = raw.clone()
    result[:, 42] = (1-elapsed_steps/max_steps).clamp(0., 1.)
    result[:, 44:76] = 0.
    result[:, 44:47] = target_relative
    result[:, 68] = 1.
    return result
