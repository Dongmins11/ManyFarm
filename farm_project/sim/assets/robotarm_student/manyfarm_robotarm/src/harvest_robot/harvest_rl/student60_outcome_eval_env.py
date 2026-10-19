"""Outcome harvest and stopped-release quality, adjudication only.

No controller receives these flags. Physical plant, valid break/retention,
collision failures, true mesh containment and 0.6s dwell remain unchanged.
"""
import torch
from .student60_response6_eval_env import Response6CameraStudentEnv
from .deposit_60hz import deposit_dwell


class OutcomeCameraStudentEnv(Response6CameraStudentEnv):
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.outcome_hold=torch.zeros_like(self.deposit_hold_time)

    def _update_task(self):
        super()._update_task()
        previous_success=self.success.clone()
        d=self.last_diagnostics
        self.outcome_hold,eligible=deposit_dwell(self.outcome_hold,
            d['deposit_mesh_inside'],d['deposit_both_jaws_clear'],self._t(self.attached),
            self.has_retained,self.valid_detach,self.failure,self.step_dt)
        self.success=eligible & (self.outcome_hold>=self.settings.place_hold_s)
        quality=self.valid_release & ~self.bad_release
        d.update(success=self.success.clone(),outcome_harvest_success=self.success.clone(),
            outcome_mesh_dwell_s=self.outcome_hold.clone(),outcome_eligible=eligible,
            previous_evaluator_success=previous_success,placement_quality_pass=quality,
            strict_harvest_success=self.success & quality)

    def _reset_impl(self,ids):
        super()._reset_impl(ids)
        if hasattr(self,'outcome_hold'):
            selected=self.robot._ALL_INDICES if ids is None else ids
            self.outcome_hold[selected]=0.
