"""Stop reducing preload once jitter is low or contact reserve is shrinking."""
from .teacher_native_settle_v2_env import TeacherNativeSettleV2Env
from .settle_gain_v4 import guarded_gain


class TeacherNativeSettleV4Env(TeacherNativeSettleV2Env):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, settle_goal_limit_m=.01, **kwargs)

    def _pre_physics_step(self, proposed):
        previous = self.robot.data.joint_stiffness[:,self.jids[-1]].clone()
        super()._pre_physics_step(proposed)
        if not self.transport_before.any():
            return
        d = self.settle_diagnostics
        gain, allowed, reserve = guarded_gain(previous, self.transport_gain_active,
            d['transport_gain_started'], self.transport_before, d['settle_pre_zone'],
            d['settle_pre_raw'], d['settle_pre_grip'], d['settle_pre_slip_m'],
            self.last_diagnostics['center_error_m'], d['settle_pre_pose_speed_m_s'],
            d['settle_pre_tcp_speed_m_s'], d['settle_pre_sdk_speed_m_s'],
            d['settle_pre_force_N'], d['settle_pre_goal_error_m'], self.step_dt)
        ids = self.transport_before.nonzero().flatten()
        self._write_gain(ids, gain[ids])
        self.settle_diagnostics.update(settle_ramp_allowed=allowed,
            settle_force_requirement_N=reserve, settle_pre_gain_Nm_rad=previous, settle_pre_center_m=self.last_diagnostics['center_error_m'].clone())
