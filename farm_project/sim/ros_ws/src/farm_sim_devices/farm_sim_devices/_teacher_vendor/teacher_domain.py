"""60Hz r2 원본 계산에서 추출. 재생성: sim/tools/import_teacher60.py."""

import torch

def canonical_quaternion(q):
    norm = torch.linalg.vector_norm(q, dim=-1, keepdim=True)
    if bool((norm < 1e-8).any()):
        raise ValueError('Zero quaternion')
    q = q / norm
    # q and -q represent the same rotation, including exact 180-degree cases.
    largest = q.gather(-1, q.abs().argmax(-1, keepdim=True))
    pivot = torch.where(q[..., :1] != 0, q[..., :1], largest)
    return q * torch.where(pivot < 0, -1., 1.)
