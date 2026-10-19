"""Keep the Teacher82 grasp dwell fraction in its defined [0, 1] units.

Rare first contacts must not turn 0.2 dwell progress into a large outlier.
All other channels and empirical-normalizer state keys are preserved.
"""
import torch
from rsl_rl.networks import EmpiricalNormalization

PROGRESS_SLOT = 39
CONTRACT = 'teacher82_grasp_progress_identity_v1'


class GraspProgressNormalization(EmpiricalNormalization):
    def forward(self, x):
        if x.shape[-1] != 82:
            raise ValueError('Requires the Teacher82 stage-transfer observation')
        normalized = super().forward(x)
        normalized[..., PROGRESS_SLOT] = x[..., PROGRESS_SLOT]
        return normalized

    def inverse(self, y):
        result = super().inverse(y)
        result[..., PROGRESS_SLOT] = y[..., PROGRESS_SLOT]
        return result


def install_grasp_progress_normalization(policy):
    """Replace actor AND critic normalizers, retaining every buffer and count."""
    for attr in ('actor_obs_normalizer', 'critic_obs_normalizer'):
        original = getattr(policy, attr)
        if not isinstance(original, EmpiricalNormalization) or original._mean.shape != (1, 82):
            raise ValueError('Expected empirical Teacher82 actor/critic normalization')
        replacement = GraspProgressNormalization(82, eps=original.eps, until=original.until)
        replacement.to(original._mean.device)
        replacement.load_state_dict(original.state_dict())
        replacement.train(original.training)
        setattr(policy, attr, replacement)


def normalization_audit(policy):
    n = policy.actor_obs_normalizer
    first = n._mean.new_tensor(.2)
    old_first = (first-n._mean[0, PROGRESS_SLOT])/(n._std[0, PROGRESS_SLOT]+n.eps)
    return dict(contract=CONTRACT, progress_slot=PROGRESS_SLOT, raw_first_contact=.2,
        empirical_mean=float(n._mean[0, PROGRESS_SLOT]),
        empirical_std=float(n._std[0, PROGRESS_SLOT]), eps=n.eps,
        old_first_contact_normalized=float(old_first), new_first_contact_normalized=.2)
