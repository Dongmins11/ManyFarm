"""60Hz r2 원본 계산에서 추출. 재생성: sim/tools/import_teacher60.py."""

import math

def render_interval(physics_dt, policy_decimation, render_hz=0):
    if render_hz == 0:
        return policy_decimation  # historical behavior, including RGB-D collection
    if physics_dt <= 0 or render_hz <= 0:
        raise ValueError('Clock rates must be positive')
    steps = 1. / (physics_dt * render_hz)
    rounded = round(steps)
    if rounded < 1 or not math.isclose(steps, rounded, rel_tol=1e-8):
        raise ValueError('Rendering frequency must divide actual physics frequency')
    return rounded
