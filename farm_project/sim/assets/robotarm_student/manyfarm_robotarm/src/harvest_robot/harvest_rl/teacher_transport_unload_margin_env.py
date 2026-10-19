"""Do not unload a held pepper already near the original center boundary."""
import torch
from .teacher_transport_posture_env import TeacherTransportPostureEnv


class TeacherTransportUnloadMarginEnv(TeacherTransportPostureEnv):
    def _pre_physics_step(self,proposed):
        jaw=self.targets[:,-1].clone();spent=self.unload_spent.clone()
        distance=getattr(self,'distance',torch.zeros(self.num_envs,device=self.device)).clone()
        super()._pre_physics_step(proposed)
        increment=self.unload_diagnostics.get('transport_unload_increment_rad',torch.zeros_like(jaw))
        blocked=(self.transport_before & ~self.deposit_before & ~self.release_intent &
                 (distance>.008) & (increment>0))
        self.targets[blocked,-1]=jaw[blocked];self.actions[blocked,-1]=0.
        self.unload_spent[blocked]=spent[blocked]
        if 'transport_unload_increment_rad' in self.unload_diagnostics:
            self.unload_diagnostics['transport_unload_increment_rad'][blocked]=0.
            self.unload_diagnostics['transport_unload_rad']=self.unload_spent.clone()
        self.margin_diag=dict(unload_margin_blocked=blocked,unload_margin_distance_before_m=distance,
            unload_margin_previous_jaw_rad=jaw,unload_margin_previous_spent_rad=spent,
            unload_margin_actual_jaw_rad=self.targets[:,-1].clone())

    def _get_rewards(self):
        reward=super()._get_rewards()
        if hasattr(self,'margin_diag'):self.chain_snapshot.update({k:v.clone() for k,v in self.margin_diag.items()})
        return reward
