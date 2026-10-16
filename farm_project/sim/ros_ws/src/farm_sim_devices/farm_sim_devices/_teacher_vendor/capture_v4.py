"""60Hz r2 원본 계산에서 추출. 재생성: sim/tools/import_teacher60.py."""

import torch

from .capture_confirmation import confirmation_actions

CONTRACT = 'raw_proposal_confirmation_v2'

def prepare_actions(proposed, qualified, attached, confirmed):
    if proposed.ndim != 2 or proposed.shape[1] != 6 or not torch.isfinite(proposed).all():
        raise ValueError('Expected finite N x 6 raw policy proposals')
    physical, held = confirmation_actions(proposed.clamp(-1, 1), qualified, attached, confirmed)
    return physical, held
