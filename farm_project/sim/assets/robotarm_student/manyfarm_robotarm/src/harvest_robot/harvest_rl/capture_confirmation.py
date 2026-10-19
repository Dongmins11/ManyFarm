"""Grasp confirmation control using current physical qualification, no latch."""
import torch

CONTRACT = 'qualified_attached_grasp_confirmation_v1'


def confirmation_actions(actions, qualified, attached, confirmed):
    """Keep existing joint targets while a real capture accumulates its dwell.

    Qualification already includes opposed contacts, centre, entry and angle.
    Losing qualification immediately releases this controller. No joint target,
    torque, success flag, contact flag or timer is injected here.
    """
    held = qualified & attached & ~confirmed
    return torch.where(held[:, None], torch.zeros_like(actions), actions), held


def confirmation_action_cost(proposed, held, dt, weight):
    # PPO samples/log-probabilities refer to the proposed action. Penalize that
    # proposal separately so the actor can learn to settle, not just rely on the
    # controller. The physical action is still recorded by HarvestEnv.
    # Use the sampled, UNCLIPPED proposal: a clipped +2 and +10 otherwise have
    # identical cost and provide no incentive to leave the saturated open zone.
    # Smooth log cost remains sensitive outside the actuator's [-1,1] range.
    effort = torch.log1p(proposed[:, :5].square()).mean(-1)+torch.log1p(proposed[:, -1].square())
    return weight*dt*held*effort
