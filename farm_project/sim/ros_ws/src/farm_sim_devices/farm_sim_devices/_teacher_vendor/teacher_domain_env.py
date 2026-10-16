"""60Hz r2 원본 계산에서 추출. 재생성: sim/tools/import_teacher60.py."""

from .env import HarvestEnv

from .teacher_domain import canonical_quaternion


class TeacherDomainEnv(HarvestEnv):

    def __init__(self, *args, domain, **kwargs):
        self.domain = domain
        self.domain_ready = True
        super().__init__(*args, **kwargs)

    def _get_observations(self):
        observation = super()._get_observations()
        if self.domain_ready:
            obs = observation['policy']
            obs[:, 21:25] = canonical_quaternion(obs[:, 21:25])
            obs[:, 31:35] = canonical_quaternion(obs[:, 31:35])
            # One target in the working area. The spare color is not an obstacle
            # or a policy input; its position cannot leak a color/target shortcut.
            obs[:, 44:76] = 0
            obs[:, 44:47] = obs[:, 25:28]
            obs[:, 68] = 1
        return observation
