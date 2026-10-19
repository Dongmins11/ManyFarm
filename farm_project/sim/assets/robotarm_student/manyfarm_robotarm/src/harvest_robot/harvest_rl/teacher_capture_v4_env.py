"""Separate V4; never edits the successful V3 controller or checkpoint contract."""
import torch
from .teacher_capture_env import TeacherCaptureEnv
from .capture_v4 import CONTRACT, prepare_actions, proposal_cost


class TeacherCaptureV4Env(TeacherCaptureEnv):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.settings.task != 'grasp' or not self.settings.stage_transfer:
            raise ValueError('V4 requires the grasp Teacher82 stage-transfer contract')
        if self.domain['confirmation_control'].get('contract') != CONTRACT:
            raise ValueError('Explicit V4 raw-proposal contract required')
        self.handoff_collector = None

    def _pre_physics_step(self, proposed):
        self.confirmation_proposed = proposed.clone()
        qualified = getattr(self, 'grip', torch.zeros(self.num_envs, device=self.device, dtype=torch.bool))
        physical, self.confirmation_held = prepare_actions(proposed, qualified,
            self._t(self.attached), self.has_grasped)
        super()._pre_physics_step(physical)

    def _get_rewards(self):
        reward = super()._get_rewards()
        if getattr(self, 'handoff_collector', None) is not None:
            self.handoff_collector.capture(self)
        if not hasattr(self, 'confirmation_proposed'):
            return reward
        proposed, held = self.confirmation_proposed, self.confirmation_held
        denom = held.sum().clamp_min(1)
        cost = proposal_cost(proposed, held, self.step_dt, self.domain['confirmation_control'])
        self.extras['log'].update({
            'Confirm/control_active': held.float().mean(),
            'Confirm/proposed_open_fraction': (held & (proposed[:, -1] > .1)).sum()/denom,
            'Confirm/proposed_jaw_abs': (proposed[:, -1].abs()*held).sum()/denom,
            'Confirm/raw_saturated_fraction': (held & (proposed[:, -1].abs() > 1)).sum()/denom,
            'Confirm/proposed_action_cost': cost.mean(),
            'Confirm/qualified': self.grip.float().mean(),
            'Confirm/hold_s': self.grip_time.mean(),
            'Confirm/max_hold_s': self.grip_time.max()})
        return reward-cost
