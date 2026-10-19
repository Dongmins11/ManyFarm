"""Actual deposited target is the task outcome; grasp history is diagnostic.

This changes adjudication and its declared60s task budget only. All original
plant calls, attachment dynamics, forces, contact masks and legacy qualification
flags remain active and unmodified. Controllers never receive these diagnostics.
"""
import torch
from .student60_outcome_eval_env import OutcomeCameraStudentEnv
from .student60_box_outcome import box_settlement_step


class BoxOutcomeCameraStudentEnv(OutcomeCameraStudentEnv):
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.box_outcome_hold=torch.zeros_like(self.deposit_hold_time)

    def _update_task(self):
        super()._update_task()
        d=self.last_diagnostics
        legacy_failure=self.failure.clone();qualified_success=self.success.clone()
        self.box_outcome_hold,eligible,safety=box_settlement_step(
            self.box_outcome_hold,d,self._t(self.attached),self.step_dt)
        self.failure=safety
        self.success=eligible & (self.box_outcome_hold>=self.settings.place_hold_s)
        d.update(success=self.success.clone(),failure=self.failure.clone(),
            legacy_failure=legacy_failure,qualified_harvest_success=qualified_success,
            box_outcome_eligible=eligible,box_outcome_dwell_s=self.box_outcome_hold.clone(),
            box_outcome_success=self.success.clone(),safety_failure=safety)

    def _get_dones(self):
        self._update_task()
        # Declared fixed budget, without task-phase or qualification resets.
        timed_out=self.episode_length_buf>=round(60./self.step_dt)-1
        return self.success | self.failure,timed_out

    def _reset_impl(self,ids):
        super()._reset_impl(ids)
        if hasattr(self,'box_outcome_hold'):
            selected=self.robot._ALL_INDICES if ids is None else ids
            self.box_outcome_hold[selected]=0.
