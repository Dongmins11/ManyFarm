"""Distinct train neighbors, explicit unique-candidate uniform coverage."""
import torch
from .native_contact_refine import SPEC, TRAIN_ANCHOR_IDS, ContactMotionReward


def training_pool(pool, bank_ids, points, *, train_end, spec=SPEC):
    if spec.hard_fraction != .25:
        raise ValueError('This version fixes the mixture at25%')
    if train_end < 1 or (bank_ids < 0).any() or (bank_ids >= train_end).any():
        raise ValueError('Original bank-derived train split required')
    # The old contact-margin environment repeats far points. Remove that
    # weight for this TRAIN reset mixture before finding distinct neighbors.
    pool = pool.unique(sorted=True)
    chosen = []
    for anchor in TRAIN_ANCHOR_IDS:
        found = (bank_ids == anchor).nonzero().flatten()
        if len(found) != 1 or not (pool == found[0]).any():
            raise ValueError('Training anchor absent from reachable domain')
        distance = (points[pool]-points[found[0]]).norm(dim=-1)
        chosen.append(pool[distance.argsort()[:spec.neighbors_per_anchor]])
    hard = torch.cat(chosen).unique(sorted=True)
    mixed = torch.cat((pool.repeat(3*len(hard)), hard.repeat(len(pool))))
    return mixed, hard
