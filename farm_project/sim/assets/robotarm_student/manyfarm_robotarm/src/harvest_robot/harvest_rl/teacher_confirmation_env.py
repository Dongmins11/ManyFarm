"""V3: physical grasp confirmation before allowing another motion command."""
import torch
from .teacher_capture_env import TeacherCaptureEnv
from .capture_confirmation import confirmation_actions, confirmation_action_cost


class TeacherConfirmationEnv(TeacherCaptureEnv):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.settings.task != 'grasp' or not self.settings.stage_transfer:
            raise ValueError('Confirmation V3 requires the grasp-stage Teacher82 contract')
        if self.domain.get('confirmation_control', {}).get('version') != 1:
            raise ValueError('Explicit confirmation control profile required')

    def _pre_physics_step(self, actions):
        self.confirmation_proposed = actions.clone()
        if hasattr(self, 'grip'):
            actions, self.confirmation_held = confirmation_actions(actions,
                self.grip, self._t(self.attached), self.has_grasped)
        else:
            self.confirmation_held = torch.zeros(self.num_envs,device=self.device,dtype=torch.bool)
        super()._pre_physics_step(actions)

    def _get_rewards(self):
        reward = super()._get_rewards()
        if not hasattr(self, 'confirmation_proposed'): return reward
        weight = self.domain['confirmation_control']['proposed_action_cost_per_s']
        cost = confirmation_action_cost(self.confirmation_proposed,
            self.confirmation_held, self.step_dt, weight)
        denominator = self.confirmation_held.sum().clamp_min(1)
        self.extras['log'].update({
            'Confirm/control_active': self.confirmation_held.float().mean(),
            'Confirm/proposed_open': (self.confirmation_held & (self.confirmation_proposed[:,-1]>.1)).float().mean(),
            'Confirm/proposed_open_fraction': (self.confirmation_held & (self.confirmation_proposed[:,-1]>.1)).sum()/denominator,
            'Confirm/proposed_jaw_abs': (self.confirmation_proposed[:,-1].abs()*self.confirmation_held).sum()/denominator,
            'Confirm/proposed_action_cost': cost.mean(),
            'Confirm/qualified': self.grip.float().mean(),
            'Confirm/hold_s': self.grip_time.mean(),
            'Confirm/max_hold_s': self.grip_time.max()})
        return reward-cost
