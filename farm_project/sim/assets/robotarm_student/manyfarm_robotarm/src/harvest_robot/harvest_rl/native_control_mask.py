"""Separate real native trajectories from actions replaced by a controller."""
import torch

SPEC = dict(version=1, actor='Native arm5 proposals actually applied only',
    excluded=['qualification_pause', 'axial_adapter', 'detached_target_hold'],
    critic='All real native transitions, including controller-only retention',
    returns='Original physical rewards/GAE; no truncation at controller transitions',
    success='Original valid detachment and actual0.5s retention')


def actor_mask(native, pause, path_active, path_hold, retention_hold):
    flags = (native, pause, path_active, path_hold, retention_hold)
    if any(x.shape != native.shape or x.dtype != torch.bool for x in flags):
        raise ValueError('Native control masks must be matching boolean vectors')
    return native & ~(pause | path_active | path_hold | retention_hold)


def actor_advantages(returns, values, mask):
    """Normalize only eligible actor samples; keep critic targets intact."""
    if returns.shape != values.shape or mask.shape != returns.shape[:2]:
        raise ValueError('Expected [T,N,1] returns and [T,N] actor mask')
    raw = returns-values
    selected = raw[mask]
    if not selected.numel():
        return torch.zeros_like(raw)
    result = (raw-selected.mean())/(selected.std(unbiased=False)+1e-8)
    return torch.where(mask[:, :, None], result, torch.zeros_like(result))


def initial_completed(seen, ids, elapsed, terminal):
    """Initial zero-time resets cannot certify a finished assigned episode."""
    result = seen.clone()
    finished = ids[(elapsed[ids] > 0) & terminal[ids]]
    result[finished] = True
    return result
