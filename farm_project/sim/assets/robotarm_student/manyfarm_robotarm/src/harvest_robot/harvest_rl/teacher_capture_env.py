"""V2 reward-only subclass. The V1 domain and frozen Teacher remain reproducible."""
import torch
from isaaclab.utils.math import quat_apply
from .teacher_domain_env import TeacherDomainEnv
from .capture_reward import readiness_potential, closing_progress


class TeacherCaptureEnv(TeacherDomainEnv):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.capture_parameters = self.domain['capture_reward']
        if self.capture_parameters['version'] != 2:
            raise ValueError('Use capture reward version 2')
        self.capture_best = torch.zeros(self.num_envs, device=self.device)
        self.capture_previous_potential = torch.zeros_like(self.capture_best)

    def _reset_impl(self, env_ids):
        super()._reset_impl(env_ids)
        if hasattr(self, 'capture_best'):
            ids = self.robot._ALL_INDICES if env_ids is None else env_ids
            self.capture_best[ids] = 0
            self.capture_previous_potential[ids] = 0

    def _potential(self, distance, error):
        p = self.capture_parameters
        return readiness_potential(distance, error, p['readiness_weight'],
            p['readiness_distance_scale_m'], p['angle_scale_deg'])

    def _pre_physics_step(self, actions):
        if hasattr(self, 'capture_best'):
            error, _ = self._grasp_orientation()
            tcp, _ = self._tcp()
            distance = (self._grasp_center(self._target_fruit())-tcp).norm(dim=-1)
            self.capture_previous_potential = self._potential(distance, error)*(
                ~self.has_grasped & self._t(self.attached))
        super()._pre_physics_step(actions)

    def _get_rewards(self):
        reward = super()._get_rewards()
        if not hasattr(self, 'capture_best'):
            return reward
        s = self.settings
        error, aligned = self._grasp_orientation()
        required = ~self.has_grasped & self._t(self.attached)
        terminal = self.success | self.failure | (self._target_elapsed_steps() >= self.max_episode_length-1)
        # Replace only the old orientation potential and hard-gated closure.
        # Position progress, genuine contact/hold rewards and pushing penalties
        # remain in the parent's reward. Success/failure code is inherited.
        old = s.grasp_orientation_weight*(1-error.square())*torch.exp(-self.distance/.10)
        old = torch.where(required & ~terminal, old, torch.zeros_like(old))
        new = torch.where(required & ~terminal, self._potential(self.distance, error), torch.zeros_like(old))
        reward += (.99*new-self.capture_previous_potential)-(.99*old-self.previous_orientation_potential)
        q = self.robot.data.joint_pos[:, self.jids[-1]]
        allowed = (~required | aligned) & self.entry_inside
        centered = self.distance <= s.grasp_center_tolerance
        qualified = self.raw_grip & centered & allowed
        old_closure = 2*(self.previous_gripper_q-q).clamp(-.06, .06)*centered*~qualified*allowed
        reward -= old_closure*~self.valid_detach
        fruit = self._target_fruit()
        tip = fruit.data.root_link_pos_w+quat_apply(fruit.data.root_link_quat_w,
            self.fruit_tips[self.target_index])
        displacement = (tip-self._t(self.anchors)).norm(dim=-1)
        closing, self.capture_best, ready, progress = closing_progress(
            self.previous_gripper_q, q, self.capture_best, self.entry_inside,
            self.distance, error, displacement, self._t(self.attached),
            self.has_grasped, self.raw_grip, terminal, s.diameter, self.upper[-1],
            self.capture_parameters)
        reward += closing
        near = self.distance < .025
        denom = near.sum().clamp_min(1)
        metrics = dict(entry_ready=ready.float().mean(), closing_reward=closing.mean(),
            new_closing_progress=progress.mean(),
            near_open_command_fraction=(near & (self.actions[:, -1] > .1)).sum()/denom,
            near_close_command_fraction=(near & (self.actions[:, -1] < -.1)).sum()/denom,
            near_measured_close_fraction=(near & (self.previous_gripper_q-q > .001)).sum()/denom,
            near_centered_fraction=(near & centered).sum()/denom,
            near_horizontal_fraction=(near & aligned).sum()/denom,
            near_orientation_deg=(torch.asin(error)*180/torch.pi*near).sum()/denom,
            mean_best_closure=self.capture_best.mean())
        self.extras['log'].update({'Capture/'+key:value for key,value in metrics.items()})
        if getattr(self, 'capture_probe_active', False):
            # Snapshot before DirectRLEnv auto-reset. Post-step robot data may
            # already belong to HOME of the next episode for successful envs.
            self.capture_probe_snapshot = dict(q=q.cpu().tolist(),
                distance_m=self.distance.cpu().tolist(),
                angle_deg=(torch.asin(error)*180/torch.pi).cpu().tolist(),
                entry=self.entry_inside.cpu().tolist(), bilateral=self.raw_grip.cpu().tolist(),
                attached=self._t(self.attached).cpu().tolist(),
                reward=reward.cpu().tolist(),
                capture_metrics={'Capture/'+key:float(value) for key,value in metrics.items()})
        if not torch.isfinite(reward).all():
            raise FloatingPointError('Nonfinite capture reward')
        return reward
