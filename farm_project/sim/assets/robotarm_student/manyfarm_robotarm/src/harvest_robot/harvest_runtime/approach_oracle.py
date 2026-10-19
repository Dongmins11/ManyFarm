"""Read-only entry oracle. Privileged observations are labels, never Student inputs.

Only the entry expert is supported: full staged Teacher recovery starts explicitly
after collection. Querying this adapter cannot change environment routing/timers.
"""
import copy
import math
import torch


class ApproachOracle:
    def __init__(self, expert, max_episode_length):
        self.expert=copy.deepcopy(expert).eval()
        self.max_episode_length=max_episode_length
        self.steps=0

    def reset(self):
        self.steps=0
        if getattr(self.expert,'is_recurrent',False):
            raise ValueError('Entry oracle currently requires stateless MLP expert')
        if hasattr(self.expert,'reset'):self.expert.reset()

    @torch.inference_mode()
    def query(self, obs):
        label_obs=dict(obs)
        label_obs['policy']=obs['policy'].clone()
        label_obs['policy'][:,42]=max(0.,1-self.steps/self.max_episode_length)
        action=self.expert.act_inference(label_obs).clone().clamp(-1,1)
        if not torch.isfinite(action).all():raise ValueError('Non-finite oracle action')
        self.steps+=1
        return action


def recovery_reason(*, attached, confirmed, contact_n, extension_m, elapsed_s,
                    limit_s, target_valid):
    """Simulation truth gates collection only; not a real robot safety controller."""
    if not attached:return 'DETACHED_REJECT'
    if confirmed:return 'CAPTURED'
    if not target_valid:return 'OBSERVATION_LOST'
    if contact_n>.10 or extension_m>.005:return 'PRECAPTURE_CONTACT'
    if elapsed_s>=limit_s:return 'APPROACH_LIMIT'
    return None


def current_contact_evidence(diagnostics, stamp_s):
    """Ignore prior-episode/reset diagnostics; accept only the current capture tick.

    These are simulator-only takeover diagnostics, never Student inputs. Reset
    does not refresh last_diagnostics, so a matching zero timestamp is also stale.
    """
    empty=dict(contact_n=0.,extension_m=0.)
    if stamp_s<=0 or 'target_elapsed_s' not in diagnostics:return empty
    if abs(float(diagnostics['target_elapsed_s'][0])-stamp_s)>1e-4:return empty
    def value(key):
        result=float(diagnostics[key][0]) if key in diagnostics else 0.
        if not math.isfinite(result):raise ValueError('Non-finite current DAgger contact evidence')
        return result
    return dict(contact_n=max(value('fixed_force_N'),value('moving_force_N')),
                extension_m=value('stem_extension_m'))
