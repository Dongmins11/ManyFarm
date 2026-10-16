"""60Hz r2 원본 계산에서 추출. 재생성: sim/tools/import_teacher60.py."""

import torch

def unload_release_target(target, measured, action, approved, unloaded, speed, dt, lower, upper):
    begin = approved & (action > 0) & ~unloaded
    # Opening must advance from the actual jaw angle, not spend several policy
    # steps unwinding a closing target below it. Never command extra closing.
    opening = (measured + action.clamp(min=0) * speed * dt).clamp(lower, upper)
    return torch.where(begin, torch.maximum(target, opening), target), unloaded | begin
