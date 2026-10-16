"""60Hz r2 원본 계산에서 추출. 재생성: sim/tools/import_teacher60.py."""

import torch

def confirmation_actions(actions, qualified, attached, confirmed):
    """Keep existing joint targets while a real capture accumulates its dwell.

    Qualification already includes opposed contacts, centre, entry and angle.
    Losing qualification immediately releases this controller. No joint target,
    torque, success flag, contact flag or timer is injected here.
    """
    held = qualified & attached & ~confirmed
    return torch.where(held[:, None], torch.zeros_like(actions), actions), held
