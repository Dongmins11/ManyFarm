"""60Hz r2 원본 계산에서 추출. 재생성: sim/tools/import_teacher60.py."""

import torch

from .teacher_capture_env import TeacherCaptureEnv

from .capture_v4 import CONTRACT, prepare_actions


class TeacherCaptureV4Env(TeacherCaptureEnv):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.settings.task != 'grasp' or not self.settings.stage_transfer:
            raise ValueError('V4 requires the grasp Teacher82 stage-transfer contract')
        if self.domain['confirmation_control'].get('contract') != CONTRACT:
            raise ValueError('Explicit V4 raw-proposal contract required')
        self.handoff_collector = None

    def _pre_physics_step(self, proposed):
        self.confirmation_proposed = proposed.clone()
        qualified = getattr(self, 'grip', torch.zeros(self.num_envs, device=self.device, dtype=torch.bool))
        physical, self.confirmation_held = prepare_actions(proposed, qualified,
            self._t(self.attached), self.has_grasped)
        super()._pre_physics_step(physical)
