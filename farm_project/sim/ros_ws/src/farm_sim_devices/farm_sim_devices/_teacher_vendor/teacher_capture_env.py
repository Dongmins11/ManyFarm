"""60Hz r2 원본 계산에서 추출. 재생성: sim/tools/import_teacher60.py."""

import torch

from .teacher_domain_env import TeacherDomainEnv

from .capture_reward import readiness_potential


class TeacherCaptureEnv(TeacherDomainEnv):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.capture_parameters = self.domain['capture_reward']
        if self.capture_parameters['version'] != 2:
            raise ValueError('Use capture reward version 2')
        self.capture_best = torch.zeros(self.num_envs, device=self.device)
        self.capture_previous_potential = torch.zeros_like(self.capture_best)

    def _potential(self, distance, error):
        p = self.capture_parameters
        return readiness_potential(distance, error, p['readiness_weight'],
            p['readiness_distance_scale_m'], p['angle_scale_deg'])

    def _pre_physics_step(self, actions):
        if hasattr(self, 'capture_best'):
            error, _ = self._grasp_orientation()
            tcp, _ = self._tcp()
            distance = (self._grasp_center(self._target_fruit())-tcp).norm(dim=-1)
            self.capture_previous_potential = self._potential(distance, error)*(
                ~self.has_grasped & self._t(self.attached))
        super()._pre_physics_step(actions)
