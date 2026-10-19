"""Pressure-only comparison on frozen height-v2 full harvest, no training."""
import torch
from .teacher_bridge_motion_compare_env import TeacherBridgeMotionCompareEnv
from .pressure_compare import PressureSpec, pressure_step


class TeacherPressureCompareEnv(TeacherBridgeMotionCompareEnv):
    def __init__(self,*args,pressure_spec=None,**kwargs):
        self.pressure_spec=(pressure_spec or PressureSpec()).validate()
        super().__init__(*args,**kwargs)
        self.pressure_spent=torch.zeros(self.num_envs,device=self.device)
        self.pressure_diagnostics={}

    def _pre_physics_step(self,proposed):
        super()._pre_physics_step(proposed)
        base=self.targets[:,-1].clone();measured=self.robot.data.joint_pos[:,self.jids[-1]]
        scope=(self.bridge_started & self.bridge_preload.latched & ~self.bridge_preload.released
               & ~self.transport_before & ~self.deposit_before & ~self.release_intent
               & (self.actions[:,-1]<=0) & ~self.failure)
        d=self.last_diagnostics
        qualified=(self.grip & self.raw_grip & (self.slip<self.settings.max_slip)
                   if hasattr(self,'raw_grip') and hasattr(self,'slip') else torch.zeros_like(scope))
        feedback=(self._t(self.attached) & qualified &
                  d.get('loaded_points_complete',torch.zeros_like(scope)).bool())
        normal=(torch.minimum(d['loaded_fixed_normal_N'],d['loaded_moving_normal_N'])
                if scope.any() else torch.zeros(self.num_envs,device=self.device))
        target,spent,increment,loading=pressure_step(base,measured,self.bridge_preload.origin,
            self.pressure_spent,scope,feedback,normal,spec=self.pressure_spec,dt=self.step_dt,
            max_error=self.settings.gripper_max_error,lower=self.lower[-1],upper=self.upper[-1])
        self.targets[:,-1]=target;self.pressure_spent=spent
        changed=scope & ((target-base).abs()>1e-8)
        self.actions[changed,-1]=-increment[changed]/(self.settings.gripper_speed*self.step_dt)
        self.pressure_diagnostics=dict(pressure_scope=scope,pressure_feedback_qualified=feedback,
            pressure_loading=loading,pressure_normal_before_N=normal,
            pressure_base_target_rad=base,pressure_measured_before_rad=measured.clone(),
            pressure_origin_before_rad=self.bridge_preload.origin.clone(),
            pressure_target_rad=target.clone(),pressure_spent_rad=spent.clone(),
            pressure_increment_rad=increment,
            pressure_goal_N=torch.full_like(normal,self.pressure_spec.goal_N))

    def _get_rewards(self):
        reward=super()._get_rewards()
        if hasattr(self,'pressure_diagnostics'):
            self.chain_snapshot.update({k:v.clone() for k,v in self.pressure_diagnostics.items()})
            self.chain_snapshot.update(
                applied_stem_force_norm_N=self._t(self.applied_stem_force).norm(dim=-1).clone(),
                applied_stem_torque_norm_Nm=self._t(self.applied_stem_torque).norm(dim=-1).clone())
        return reward

    def _reset_impl(self,ids):
        super()._reset_impl(ids)
        if hasattr(self,'pressure_spent'):
            selected=self.robot._ALL_INDICES if ids is None else ids
            self.pressure_spent[selected]=0.
