"""Unchanged v2 environment with read-only applied-action provenance."""
import torch
from .teacher_native_contact_v2_env import TeacherNativeContactV2Env
from .native_control_mask import actor_mask, initial_completed


class TeacherNativeContactControlEnv(TeacherNativeContactV2Env):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.native_initial_episode_done = torch.zeros(self.num_envs, dtype=torch.bool, device=self.device)

    def _pre_physics_step(self, proposed):
        super()._pre_physics_step(proposed)
        active = self.policy_active_before
        off = torch.zeros_like(active)
        d = self.path_diagnostics
        self.native_actor_controlled = actor_mask(active, self.native_pause,
            d.get('path_active', off), d.get('path_hold', off),
            d.get('retention_target_hold', off)).clone()
        self.native_controller_only = active & ~self.native_actor_controlled
        # Do not clear these at auto-reset: the just-ended transition still
        # needs its applied-action mask in process_env_step. Next pre-step
        # overwrites all environments before any new physical transition.

    def _get_rewards(self):
        reward = super()._get_rewards()
        if hasattr(self, 'native_actor_controlled'):
            fields = dict(native_actor_controlled=self.native_actor_controlled.clone(),
                native_controller_only=self.native_controller_only.clone())
            self.last_diagnostics.update(fields)
            self.chain_snapshot.update(fields)
        return reward

    def _reset_impl(self, ids):
        if hasattr(self, 'native_initial_episode_done'):
            selected = self.robot._ALL_INDICES if ids is None else ids
            terminal = self.success | self.failure | self.reset_time_outs
            self.native_initial_episode_done = initial_completed(
                self.native_initial_episode_done, selected, self.episode_length_buf, terminal)
        super()._reset_impl(ids)
