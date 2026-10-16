"""60Hz r2 원본 계산에서 추출. 재생성: sim/tools/import_teacher60.py."""

import torch

from .teacher_bridge_motion_compare_env import TeacherBridgeMotionCompareEnv

from .pressure_compare import PressureSpec


class TeacherPressureCompareEnv(TeacherBridgeMotionCompareEnv):

    def __init__(self,*args,pressure_spec=None,**kwargs):
        self.pressure_spec=(pressure_spec or PressureSpec()).validate()
        super().__init__(*args,**kwargs)
        self.pressure_spent=torch.zeros(self.num_envs,device=self.device)
        self.pressure_diagnostics={}

    def _pre_physics_step(self, proposed):
        if self.pressure_spec.goal_N != 0:
            raise ValueError('배포에서 제외한 추가 압력 제어입니다.')
        super()._pre_physics_step(proposed)
