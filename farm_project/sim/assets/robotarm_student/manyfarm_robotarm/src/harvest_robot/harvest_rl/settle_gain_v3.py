"""Contact-reserve guarded jaw relaxation; never increase closing stiffness."""
import torch


def guarded_gain(previous, active, first, scope, zone, raw, grip, slip, center,
                 pose_speed, tcp_speed, sdk_speed, min_force, goal_error, dt=.05):
    allowed = (active & ~first & scope & zone & raw & grip & (slip < .008)
        & (center < .008) & (pose_speed <= .02) & (tcp_speed <= .02)
        & (sdk_speed > .18) & (min_force > 1.) & (goal_error < .01))
    gain = torch.where(allowed, (previous - 7.*dt).clamp_min(1.), previous)
    return gain, allowed
