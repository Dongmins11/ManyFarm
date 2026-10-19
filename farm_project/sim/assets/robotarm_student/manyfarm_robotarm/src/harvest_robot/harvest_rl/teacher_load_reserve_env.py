"""Reward-only contact refinement; keeps all V4 physics/control/outcome checks."""
from .teacher_contact_margin_env import TeacherContactMarginEnv
from .grasp_load_reserve_60hz import replace_contact_margin_reward


class TeacherLoadReserveEnv(TeacherContactMarginEnv):
    def _get_rewards(self):
        reward=super()._get_rewards()
        d=self.last_diagnostics
        if 'loaded_points_complete' not in d:return reward
        result,diag=replace_contact_margin_reward(reward,d,self.distance,
            self.grip & self.raw_grip,self._t(self.attached),self.success,self.step_dt)
        self.last_diagnostics.update({k:v.clone() for k,v in diag.items()})
        self.extras['log'].update({'LoadReserve/'+k:v.float().mean() for k,v in diag.items()})
        # Replace the previous geometry bonus, rather than paying both versions.
        if getattr(self,'capture_probe_active',False):
            import torch
            if not torch.isfinite(result).all() or not all(torch.isfinite(v).all() for v in diag.values()):
                raise RuntimeError('Nonfinite load-reserve fixture reward/diagnostics')
            audit=getattr(self,'load_reserve_fixture_audit',dict(reward_steps=0,
                active_env_steps=0,positive_bonus_env_steps=0,max_bonus=0.,finite=True))
            audit['reward_steps']+=1
            audit['active_env_steps']+=int(diag['load_reserve_active'].sum())
            audit['positive_bonus_env_steps']+=int((diag['load_reserve_bonus']>0).sum())
            audit['max_bonus']=max(audit['max_bonus'],float(diag['load_reserve_bonus'].max()))
            self.load_reserve_fixture_audit=audit
        return result
