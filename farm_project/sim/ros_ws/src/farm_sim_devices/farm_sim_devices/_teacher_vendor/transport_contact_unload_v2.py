"""60Hz r2 원본 계산에서 추출. 재생성: sim/tools/import_teacher60.py."""

import math

import torch

def unload_step(previous,spent,eligible,force_min,dt):
    budget=math.radians(2.);rate=math.radians(.5)
    active=eligible & (force_min>.5) & (spent<budget-1e-8)
    increment=torch.where(active,(budget-spent).clamp(min=0.,max=rate*dt),0.)
    return previous+increment,spent+increment,increment
