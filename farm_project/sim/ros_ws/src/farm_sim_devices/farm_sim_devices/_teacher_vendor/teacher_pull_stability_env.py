"""60Hz r2 원본 계산에서 추출. 재생성: sim/tools/import_teacher60.py."""

import torch

from .teacher_pressure_compare_env import TeacherPressureCompareEnv


class TeacherPullStabilityEnv(TeacherPressureCompareEnv):

    def __init__(self, *args, stability_mode='pause', **kwargs):
        if stability_mode not in ('baseline', 'pause', 'early', 'axial'):
            raise ValueError('Unknown stability mode')
        self.stability_mode = stability_mode
        super().__init__(*args, **kwargs)
        self.stability_seen = torch.zeros_like(self.pull_active)
        self.stability_origin = torch.zeros((self.num_envs, 3), device=self.device)
        self.stability_rotation = torch.eye(3, device=self.device).repeat(self.num_envs, 1, 1)
        self.stability_diag = {}

    def _pre_physics_step(self, proposed):
        previous = self.targets[:, :5].clone()
        scope = self.pull_active & ~self.transport_active & ~self.deposit_active & ~self.release_intent
        qualified = (self.grip & self.raw_grip & (self.slip < self.settings.max_slip)
                     if hasattr(self, 'raw_grip') and hasattr(self, 'slip') else torch.zeros_like(scope))
        p, r, _ = self.path_kin.pose_and_jacobian(self.robot.data.joint_pos[:, self.jids])
        first = scope & ~self.stability_seen
        self.stability_origin[first] = p[first]
        self.stability_rotation[first] = r[first]
        self.stability_seen |= scope
        axis = p.new_tensor(self.settings.tension_axis); axis = axis/axis.norm()
        offset = p-self.stability_origin
        lateral = (offset-(offset*axis).sum(-1)[:, None]*axis).norm(dim=-1)
        relative = self.stability_rotation @ r.transpose(1, 2)
        angle = (((relative.diagonal(dim1=-2, dim2=-1).sum(-1)-1)/2).clamp(-1, 1)).acos()
        eligible = scope & self._t(self.attached) & qualified & ~self.failure
        trigger = torch.zeros_like(scope)
        if self.stability_mode == 'early':
            trigger = eligible & ((lateral >= .002) | (angle >= .10))
        elif self.stability_mode == 'axial':
            trigger = eligible
        fresh = trigger & ~self.risk_latched
        # The existing Cartesian controller starts from measured pose on first
        # intervention. Keep its original speed/joint caps and jaw bookkeeping.
        if not hasattr(self, 'risk_start_s'):
            self.risk_start_s = torch.zeros_like(self._target_elapsed_steps()*self.step_dt)
        self.risk_start_s[fresh] = (self._target_elapsed_steps()*self.step_dt)[fresh]
        self.risk_latched |= trigger
        super()._pre_physics_step(proposed)
        pause = scope & ~qualified if self.stability_mode != 'baseline' else torch.zeros_like(scope)
        self.targets[pause, :5] = previous[pause]
        self.actions[pause, :5] = 0.
        self.stability_diag = dict(stability_scope=scope, stability_qualified_before=qualified,
            stability_pause=pause, stability_early_trigger=fresh,
            stability_lateral_m=lateral, stability_rotation_rad=angle,
            stability_pause_target_error_rad=torch.where(pause,
                (self.targets[:, :5]-previous).abs().amax(-1), 0.))
