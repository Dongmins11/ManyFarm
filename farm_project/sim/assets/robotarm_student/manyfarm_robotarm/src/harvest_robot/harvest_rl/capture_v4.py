"""Raw proposals, confirmation control and bounded physical commands are distinct."""
import torch
from .capture_confirmation import confirmation_actions, confirmation_action_cost

CONTRACT = 'raw_proposal_confirmation_v2'


def prepare_actions(proposed, qualified, attached, confirmed):
    if proposed.ndim != 2 or proposed.shape[1] != 6 or not torch.isfinite(proposed).all():
        raise ValueError('Expected finite N x 6 raw policy proposals')
    physical, held = confirmation_actions(proposed.clamp(-1, 1), qualified, attached, confirmed)
    return physical, held


def proposal_cost(proposed, held, dt, control):
    cost = confirmation_action_cost(proposed, held, dt,
                                    control['proposed_action_cost_per_s'])
    # Opening is specifically undesirable during an already qualified capture.
    # Smooth, unbounded proposal sensitivity; applied commands remain bounded.
    opening = torch.log1p(proposed[:, -1].clamp_min(0).square())
    return cost + dt * held * control['proposed_open_cost_per_s'] * opening
