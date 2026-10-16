"""60Hz r2 원본 계산에서 추출. 재생성: sim/tools/import_teacher60.py."""

import torch

from .teacher_friction_followup_env import TeacherFrictionFollowupEnv

from .transport_progress_budget import extension_eligible


class TeacherFrictionProgressEnv(TeacherFrictionFollowupEnv):

    def __init__(self,*args,progress_budget=False,**kwargs):
        self.progress_budget_enabled=progress_budget
        super().__init__(*args,**kwargs)
        self.progress_history=torch.full((61,self.num_envs),float('nan'),device=self.device)
        self.progress_history_step=0
        self.progress_extension=torch.zeros_like(self.grip_time)
        self.progress_3s=torch.zeros_like(self.grip_time)
        self.progress_first=torch.zeros_like(self.has_grasped)

    def _pre_physics_step(self,proposed):
        super()._pre_physics_step(proposed)
        if not hasattr(self,'progress_history'):return
        error=self.transport_path_diagnostics.get('transport_goal_error_m',torch.full_like(self.grip_time,float('nan')))
        index=self.progress_history_step%61;past=self.progress_history[(self.progress_history_step-60)%61]
        self.progress_3s=past-error
        self.progress_history[index]=torch.where(self.transport_before,error,float('nan'))
        self.progress_history_step+=1

    def _get_dones(self):
        terminated,timeout=super()._get_dones()
        if not hasattr(self,'progress_extension') or not self.progress_budget_enabled:return terminated,timeout
        qualified=self.grip & self.raw_grip & (self.slip<self.settings.max_slip)
        scope=self.transport_before & ~self.deposit_active & ~self.release_intent
        d=self.last_diagnostics;force_min=torch.minimum(d['fixed_force_N'],d['moving_force_N'])
        error=self.transport_path_diagnostics.get('transport_goal_error_m',torch.full_like(self.grip_time,float('inf')))
        first=extension_eligible(timeout,scope,self.failure,qualified,self.has_retained,self.valid_detach,
            self._t(self.attached),error,self.progress_3s,force_min,self.progress_extension>0)
        self.progress_extension[first]=6.;self.progress_first=first
        elapsed=(self.episode_length_buf-self.transport_start_step)*self.step_dt
        permitted=scope & qualified & (self.progress_extension>0) & ~self.failure
        timeout=torch.where(permitted,elapsed>=self.settings.episode_s+self.progress_extension-self.step_dt,timeout)
        return terminated,timeout
