"""60Hz r2 원본 계산에서 추출. 재생성: sim/tools/import_teacher60.py."""

import torch

def opening_target(previous, measured, started, *, rate, dt, lower, upper, max_error):
    if not 0 < rate <= 1.2 or dt <= 0 or max_error <= 0:
        raise ValueError('Invalid opening rate/dt/error')
    # Remove the old closing preload exactly once, after a verified stop.
    # Subsequent steps continue the saved target, never chase measured noise.
    base = torch.where(started, torch.maximum(previous, measured), previous)
    desired = torch.minimum(base + rate * dt, measured + max_error)
    return torch.maximum(previous, desired).clamp(lower, upper)

def deposit_dwell(previous, inside, clear, attached, retained, valid_detach, failure, dt):
    eligible = inside & clear & ~attached & retained & valid_detach & ~failure
    return torch.where(eligible, previous + dt, 0.), eligible
