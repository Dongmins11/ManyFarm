"""60Hz r2 원본 계산에서 추출. 재생성: sim/tools/import_teacher60.py."""

import torch

from .teacher_transport_posture_env import TeacherTransportPostureEnv

from .teacher_bridge_transport_gain_env import hold_stiffness

from .settle_gate_v2 import eligibility, advance


class TeacherNativeSettleV2Env(TeacherTransportPostureEnv):

    def __init__(self, *args, settle_goal_limit_m=.01, **kwargs):
        if settle_goal_limit_m not in (.005, .01):
            raise ValueError('Only5/10mm stationary plateau comparison')
        self.settle_goal_limit_m = settle_goal_limit_m
        super().__init__(*args, **kwargs)

    def _pre_physics_step(self, proposed):
        # The frozen hierarchy executes all original targets and phase scopes.
        # Its plateau state/gain is replaced BEFORE physics, from saved inputs;
        # there is one physical gain write in effect and no duplicate dwell.
        previous = self.gain_plateau_ticks.clone()
        active = self.transport_gain_active.clone()
        start = self.gain_start_step.clone()
        super()._pre_physics_step(proposed)
        if not self.transport_before.any():
            return
        d = self.last_diagnostics
        minimum = torch.minimum(d['fixed_force_N'], d['moving_force_N'])
        goal = self.transport_path_diagnostics['transport_goal_error_m']
        eligible = eligibility(transport=self.transport_before, qualified=self.grip,
            raw=self.raw_grip, slip=self.slip, max_slip=self.settings.max_slip,
            release=self.release_intent, zone=d['stop_zone_ok'],
            tcp_speed=d['stop_tcp_speed_m_s'], pose_speed=d['stop_fruit_pose_speed_m_s'],
            goal_error=goal, sdk_speed=d['fruit_speed_m_s'], min_force=minimum,
            goal_limit=self.settle_goal_limit_m)
        ticks, active, start, first = advance(previous, active, start, eligible, self.episode_length_buf)
        self.gain_plateau_ticks = ticks
        self.transport_gain_active = active
        self.gain_start_step = start
        ids = self.transport_before.nonzero().flatten()
        elapsed = (self.episode_length_buf[ids] - start[ids]) * self.step_dt
        gain = hold_stiffness(self.original_jaw_stiffness[ids], elapsed,
                             self.hold_stiffness_Nm_rad, self.gain_ramp_s)
        gain = torch.where(active[ids], gain, self.original_jaw_stiffness[ids])
        self._write_gain(ids, gain)
        self.settle_diagnostics = dict(transport_gain_eligible=eligible,
            transport_gain_plateau_ticks=ticks.clone(), transport_gain_started=first,
            transport_gain_elapsed_s=torch.where(active,
                (self.episode_length_buf-start)*self.step_dt, 0.),
            settle_pre_zone=d['stop_zone_ok'].clone(), settle_pre_raw=self.raw_grip.clone(),
            settle_pre_grip=self.grip.clone(), settle_pre_slip_m=self.slip.clone(),
            settle_pre_release=self.release_intent.clone(),
            settle_pre_tcp_speed_m_s=d['stop_tcp_speed_m_s'].clone(),
            settle_pre_pose_speed_m_s=d['stop_fruit_pose_speed_m_s'].clone(),
            settle_pre_sdk_speed_m_s=d['fruit_speed_m_s'].clone(),
            settle_pre_force_N=minimum.clone(), settle_pre_goal_error_m=goal.clone())
