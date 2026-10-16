"""60Hz r2 원본 계산에서 추출. 재생성: sim/tools/import_teacher60.py."""

import torch

def eligibility(*, transport, qualified, raw, slip, max_slip, release,
                zone, tcp_speed, pose_speed, goal_error, sdk_speed, min_force,
                goal_limit=.01):
    if goal_limit not in (.005, .01):
        raise ValueError('Compare original5mm or bounded10mm eligibility only')
    return (transport & qualified & raw & (slip < max_slip) & ~release
            & zone & (tcp_speed <= .02) & (pose_speed <= .02)
            & (goal_error < goal_limit) & (sdk_speed > .2) & (min_force > .5))

def advance(previous, active, start, eligible, step):
    ticks = torch.where(eligible, previous + 1, 0)
    first = (ticks >= 6) & ~active
    return ticks, active | first, torch.where(first, step, start), first
