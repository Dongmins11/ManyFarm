"""Training-only reset mixture/reward over frozen native controls and9g floor."""
import torch
from .teacher_native_alignment_env import TeacherNativeAlignmentEnv
from .native_contact_refine import ContactMotionReward, training_pool
from .floor_unified import configure_floor


class TeacherNativeContactEnv(TeacherNativeAlignmentEnv):
    def __init__(self, *args, bias_training=False, **kwargs):
        if bias_training and kwargs.get('domain_split') != 'train':
            raise ValueError('No held-out priority sampling')
        super().__init__(*args, **kwargs)
        self.contact_motion = ContactMotionReward(self.num_envs, self.device)
        self.priority_bank_ids = []
        self.train_bank_end_exclusive = int(len(self.bank_np['points'])*.8)
        if bias_training:
            mixed, hard = training_pool(self.domain_pools[3], self.domain_bank_ids, self.points,
                train_end=self.train_bank_end_exclusive)
            self.domain_pools[3] = mixed
            self.priority_bank_ids = self.domain_bank_ids[hard].cpu().tolist()

    def _setup_scene(self):
        super()._setup_scene()
        self.floor_override = configure_floor(self.sim.stage, 'unified')

    def _update_task(self):
        super()._update_task()
        if hasattr(self, 'contact_motion'):
            tcp, quat = self._tcp(); d = self.last_diagnostics
            self.contact_motion.handoff(d['chain_handoff'], tcp, quat,
                d['fixed_force_N'], d['moving_force_N'])

    def _get_rewards(self):
        original = super()._get_rewards()
        if not hasattr(self, 'contact_motion'):
            return original
        tcp, quat = self._tcp(); d = self.last_diagnostics
        cost, metrics = self.contact_motion.step(active=self.policy_active_before,
            tcp=tcp, quat=quat, axis=self.settings.tension_axis,
            fixed=d['fixed_force_N'], moving=d['moving_force_N'],
            arm_force=d['arm_max_force_N'], dt=self.step_dt)
        # Replace the old capped collision term; preserve axial potential,
        # handoff-relative alignment, physical terminal and loss-event costs.
        result = original+d['bridge_pull_collision_cost']*self.policy_active_before-cost
        d['effective_reward'] = result.clone()
        for key, value in metrics.items():
            d['native_contact_'+key] = value.clone()
            selected = value[self.policy_active_before]
            self.extras['log']['NativeContact/'+key] = selected.mean() if selected.numel() else value.new_tensor(0.)
        self.chain_snapshot.update({k:v.clone() for k,v in d.items()
            if k.startswith('native_contact_') or k == 'effective_reward'})
        if not torch.isfinite(result).all():
            raise FloatingPointError('Nonfinite native contact reward')
        return result

    def _reset_impl(self, ids):
        super()._reset_impl(ids)
        if hasattr(self, 'contact_motion'):
            self.contact_motion.reset(self.robot._ALL_INDICES if ids is None else ids)
