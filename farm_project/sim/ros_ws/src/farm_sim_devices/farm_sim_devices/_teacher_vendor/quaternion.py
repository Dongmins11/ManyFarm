"""Isaac math와 같은 wxyz quaternion 계산. 시뮬레이터 import가 필요 없습니다."""
import torch


def quat_conjugate(q: torch.Tensor) -> torch.Tensor:
    """단위 quaternion의 역회전을 반환합니다."""
    return torch.cat((q[..., :1], -q[..., 1:]), dim=-1)


def quat_mul(a: torch.Tensor, b: torch.Tensor) -> torch.Tensor:
    """wxyz 순서의 Hamilton 곱입니다."""
    aw, av, bw, bv = a[..., :1], a[..., 1:], b[..., :1], b[..., 1:]
    return torch.cat((aw * bw - (av * bv).sum(-1, keepdim=True),
                      aw * bv + bw * av + torch.linalg.cross(av, bv, dim=-1)), dim=-1)


def quat_apply(q: torch.Tensor, vector: torch.Tensor) -> torch.Tensor:
    """단위 quaternion으로 마지막 축의 3D 벡터를 회전합니다."""
    uv = torch.linalg.cross(q[..., 1:], vector, dim=-1)
    return vector + 2 * (q[..., :1] * uv + torch.linalg.cross(q[..., 1:], uv, dim=-1))
