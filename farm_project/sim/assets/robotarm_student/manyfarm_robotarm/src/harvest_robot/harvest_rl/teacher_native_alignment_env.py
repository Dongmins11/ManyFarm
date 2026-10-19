"""Same guarded/pause pull as the26/32 chain; only the learning reward changes."""
import torch
from .teacher_bridge_pull_guarded_env import TeacherBridgePullGuardedEnv
from .native_pull_alignment import NativePullAlignment


class TeacherNativeAlignmentEnv(TeacherBridgePullGuardedEnv):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.alignment = NativePullAlignment(self.num_envs, self.device)
        self.native_pause = torch.zeros_like(self.pull_active)

    def _update_task(self):
        super()._update_task()
        if hasattr(self, 'alignment'):
            tcp, quat = self._tcp()
            self.alignment.handoff(self.last_diagnostics['chain_handoff'], tcp, quat)

    def _pre_physics_step(self, proposed):
        previous = self.targets[:, :5].clone()
        scope = self.pull_active & ~self.release_intent
        qualified = (self.grip & self.raw_grip & (self.slip < self.settings.max_slip)
            if hasattr(self, 'raw_grip') and hasattr(self, 'slip') else torch.zeros_like(scope))
        super()._pre_physics_step(proposed)
        self.native_pause = scope & ~qualified
        self.targets[self.native_pause, :5] = previous[self.native_pause]
        self.actions[self.native_pause, :5] = 0.

    def _get_rewards(self):
        original = super()._get_rewards()
        if not hasattr(self, 'alignment'):
            return original
        tcp, quat = self._tcp(); d = self.last_diagnostics
        cost, metrics = self.alignment.step(active=self.policy_active_before,
            attached=self._t(self.attached),
            qualified=self.grip & self.raw_grip & (self.slip < self.settings.max_slip),
            tcp=tcp, quat=quat, axis=self.settings.tension_axis, center=self.distance,
            slip=self.slip, dt=self.step_dt)
        # Replace the two old calyx/fruit costs, rather than charging both old
        # and new lateral/rotation costs. Axial potential and terminal remain.
        replaced = d['bridge_pull_lateral_cost']+d['bridge_pull_rotation_cost']
        result = original+replaced*self.policy_active_before-cost
        d['native_pause'] = self.native_pause.clone()
        d['effective_reward'] = result.clone()
        for key, value in metrics.items():
            d['native_alignment_'+key] = value.clone()
            selected = value[self.policy_active_before]
            self.extras['log']['NativeAlignment/'+key] = selected.mean() if selected.numel() else value.new_tensor(0.)
        self.chain_snapshot.update({k:v.clone() for k,v in d.items()
            if k.startswith('native_') or k == 'effective_reward'})
        if not torch.isfinite(result).all():
            raise FloatingPointError('Nonfinite native pull reward')
        return result

    def _reset_impl(self, ids):
        super()._reset_impl(ids)
        if hasattr(self, 'alignment'):
            selected = self.robot._ALL_INDICES if ids is None else ids
            self.alignment.reset(selected); self.native_pause[selected] = False
