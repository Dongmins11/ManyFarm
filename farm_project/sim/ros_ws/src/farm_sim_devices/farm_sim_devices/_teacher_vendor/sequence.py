"""60Hz r2 원본 계산에서 추출. 재생성: sim/tools/import_teacher60.py."""

import torch

def forbidden_detach(attached, collected, target):
    indices = torch.arange(attached.shape[1],device=attached.device)[None,:]
    return ((~attached) & ~collected & (indices != target[:,None])).any(-1)

def target_elapsed(episode_steps, target_start, per_fruit):
    return episode_steps-target_start if per_fruit else episode_steps
