"""60Hz r2 원본 계산에서 추출. 재생성: sim/tools/import_teacher60.py."""

import torch

SPEC = dict(version=1, post_confirmation_hold_s=2., preload_deg=4.,
    preload_rate_deg_s=6., proposal_cost_per_s=2.,
    scope='HOME approach/grasp followed by the same stored arm target and finite jaw preload as response pull; no pulling',
    success='Original attached 250ms qualification, then uninterrupted actual qualified contact/slip for two additional seconds',
    failure='Original physical failure, or actual qualification/contact/slip/attachment loss after confirmation',
    velocity='Measured velocities recorded; no arbitrary velocity cutoff or velocity reset',
    physics='Unchanged9g/v1/response6,60Hz physics,20Hz policy; no auxiliary forces, weld or pose correction')

def bridge_step(started, hold_time, original_success, qualified, attached, failed, dt):
    """Confirmation's first sample earns no post-confirmation hold time."""
    if not 0 < dt <= .05+1e-9:
        raise ValueError('Positive bridge sample period at most50ms required')
    first = ~started & original_success & attached & qualified & ~failed
    lost = started & ~(qualified & attached)
    updated = torch.where(started & qualified & attached & ~failed,
        hold_time+dt, torch.zeros_like(hold_time))
    started = started | first
    success = started & ~failed & ~lost & (updated >= SPEC['post_confirmation_hold_s']-1e-6)
    return started, updated, success, lost, first
