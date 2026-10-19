"""Frozen stop candidate -> arm target hold -> bounded opening -> real box dwell.

Only command targets and controller phase are changed. No teleport, weld, force,
velocity override, contact latch or replay bank is used at either handoff.
"""
import torch
from isaaclab.utils.math import quat_apply
from .teacher_bridge_transport_settle_env import TeacherBridgeTransportSettleEnv
from .logic import mesh_settled_in_box, release_intent_step
from .deposit_60hz import opening_target, deposit_dwell


class TeacherBridgeDepositEnv(TeacherBridgeTransportSettleEnv):
    def __init__(self, *args, opening_rate_rad_s=.3, deposit_timeout_s=6., **kwargs):
        if not 0 < opening_rate_rad_s <= 1.2 or deposit_timeout_s < 2.:
            raise ValueError('Requires bounded opening and at least2s physical deposit budget')
        self.opening_rate_rad_s = opening_rate_rad_s
        self.deposit_timeout_s = deposit_timeout_s
        super().__init__(*args, **kwargs)
        self.deposit_active = torch.zeros_like(self.transport_active)
        self.deposit_before = self.deposit_active.clone()
        self.deposit_first_command = self.deposit_active.clone()
        self.deposit_start_step = torch.zeros_like(self.episode_length_buf)
        self.deposit_hold_time = torch.zeros(self.num_envs, device=self.device)
        self.deposit_arm_targets = torch.zeros(self.num_envs, 5, device=self.device)
        self.deposit_start_arm_q = torch.zeros_like(self.deposit_arm_targets)
        self.deposit_start_tcp = torch.zeros(self.num_envs, 3, device=self.device)
        self.deposit_gain = self.original_jaw_stiffness.clone()
        self.deposit_events = []

    def _target_elapsed_steps(self):
        result = super()._target_elapsed_steps()
        if hasattr(self, 'deposit_active'):
            result = torch.where(self.deposit_active,
                self.episode_length_buf - self.deposit_start_step, result)
        return result

    def _pre_physics_step(self, proposed):
        self.deposit_before = self.deposit_active.clone()
        previous = self.targets.clone()
        scope = self.deposit_before
        preload = {k: getattr(self.bridge_preload, k).clone()
                   for k in ('origin', 'latched', 'released')}
        # Keep the frozen upstream controller for all non-release rows. Disable
        # its transport scope on release rows so unloading/gain/path cannot run
        # a second time. Restore the stage history, then replace only commands.
        self.transport_active[scope] = False
        try:
            super()._pre_physics_step(proposed)
        finally:
            self.transport_active[scope] = True
        if not scope.any():
            return
        target = opening_target(previous[:, -1],
            self.robot.data.joint_pos[:, self.jids[-1]], self.deposit_first_command,
            rate=self.opening_rate_rad_s, dt=self.step_dt,
            lower=self.lower[-1], upper=self.upper[-1], max_error=self.settings.gripper_max_error)
        self.targets[scope, :5] = self.deposit_arm_targets[scope]
        self.targets[scope, -1] = target[scope]
        for key, value in preload.items():
            getattr(self.bridge_preload, key)[scope] = value[scope]
        self.actions[scope, :5] = 0.
        self.actions[scope, -1] = self.opening_rate_rad_s / self.settings.gripper_speed
        for key in ('path_hold', 'path_active', 'retention_target_hold'):
            self.path_diagnostics[key][scope] = False
        self.deposit_first_command[scope] = False

    def _update_task(self):
        super()._update_task()
        if not hasattr(self, 'deposit_active'):
            return
        first = self.success & ~self.deposit_active & ~self.failure
        self.deposit_start_step[first] = self.episode_length_buf[first]
        self.deposit_arm_targets[first] = self.targets[first, :5]
        self.deposit_start_arm_q[first] = self.robot.data.joint_pos[first][:, self.jids[:5]]
        tcp, _ = self._tcp()
        self.deposit_start_tcp[first] = tcp[first]
        self.deposit_gain[first] = self.robot.data.joint_stiffness[first, self.jids[-1]]
        self.deposit_active |= first
        self.deposit_first_command |= first
        # Authorization comes from the actual original0.3s stop gate, not a
        # historical "has retained" flag. Release quality remains diagnostic.
        self.release_armed[first] = True
        self.release_intent[first] = True
        self.release_intent_age[first] = 0.
        fruit = self._target_fruit().data
        local = fruit.root_link_pos_w - self.scene.env_origins
        inside = torch.zeros_like(self.deposit_active)
        bottom = torch.zeros(self.num_envs, 3, device=self.device)
        top = torch.zeros_like(bottom)
        for i, vertices in enumerate(self.fruit_collision_hulls):
            ids = self.target_index == i
            inside |= ids & mesh_settled_in_box(local, fruit.root_link_quat_w,
                fruit.root_com_lin_vel_w, vertices, self.settings)
            points = local[:, None] + quat_apply(
                fruit.root_link_quat_w[:, None].expand(-1, len(vertices), -1),
                vertices[None].expand(self.num_envs, -1, -1))
            bottom[ids] = points.amin(1)[ids]
            top[ids] = points.amax(1)[ids]
        d = self.last_diagnostics
        clear = (~self.raw_grip &
            (d['fixed_force_N'] < self.settings.contact_threshold) &
            (d['moving_force_N'] < self.settings.contact_threshold))
        scope = self.deposit_before
        hold, eligible = deposit_dwell(self.deposit_hold_time, inside, clear,
            self._t(self.attached), self.has_retained, self.valid_detach, self.failure, self.step_dt)
        self.deposit_hold_time[scope] = hold[scope]
        hand_still = ((tcp - self.deposit_start_tcp).norm(dim=-1) <= .01) & (
            (self.robot.data.joint_pos[:, self.jids[:5]] - self.deposit_start_arm_q).abs().amax(-1) <= .03)
        hand_still &= (tcp - self.previous_tcp).norm(dim=-1) / self.step_dt <= self.settings.release_speed
        lost = self.previous_raw_grip & ~self.raw_grip & ~self.valid_release
        intent, age, approved = release_intent_step(self.release_intent,
            self.release_intent_age, lost, self.actions[:, -1], hand_still, self.step_dt)
        self.release_intent[scope] = intent[scope]
        self.release_intent_age[scope] = age[scope]
        self.valid_release |= approved & scope
        self.bad_release |= lost & ~approved & scope
        self.success = scope & eligible & (self.deposit_hold_time >= self.settings.place_hold_s) & ~self.failure
        d.update(success=self.success.clone(), deposit_handoff=first,
            deposit_active=self.deposit_active.clone(), deposit_action_active=scope.clone(),
            deposit_elapsed_s=torch.where(self.deposit_active,
                (self.episode_length_buf-self.deposit_start_step)*self.step_dt, 0.),
            deposit_hold_s=self.deposit_hold_time.clone(), deposit_mesh_inside=inside,
            deposit_both_jaws_clear=clear, deposit_eligible=eligible,
            deposit_release_approved=self.valid_release.clone(), deposit_hand_still=hand_still,
            deposit_start_gain_Nm_rad=self.deposit_gain.clone(),
            deposit_arm_target_error_rad=(self.targets[:, :5]-self.deposit_arm_targets).abs().amax(-1),
            deposit_fruit_angular_speed_rad_s=fruit.root_com_ang_vel_w.norm(dim=-1))
        for j, axis in enumerate('xyz'):
            d['deposit_hull_lower_'+axis+'_m'] = bottom[:, j].clone()
            d['deposit_hull_upper_'+axis+'_m'] = top[:, j].clone()
        for i in first.nonzero().flatten().cpu().tolist():
            self.deposit_events.append(dict(env_id=i, episode_step=int(self.episode_length_buf[i]),
                stop_dwell_s=float(self.stop_time[i]), valid_detach=bool(self.valid_detach[i]),
                retained=bool(self.has_retained[i]), qualified=bool(self.grip[i] & self.raw_grip[i]),
                arm_targets=self.deposit_arm_targets[i].cpu().tolist(),
                jaw_target_rad=float(self.targets[i, -1]), jaw_q_rad=float(self.robot.data.joint_pos[i, self.jids[-1]]),
                jaw_stiffness_Nm_rad=float(self.deposit_gain[i]), scene_reset=False))

    def _get_dones(self):
        terminated, timed_out = super()._get_dones()
        # An independent bounded opening/deposit clock; not another20s retry.
        timed_out = torch.where(self.deposit_active,
            (self.episode_length_buf-self.deposit_start_step)*self.step_dt >= self.deposit_timeout_s-self.step_dt,
            timed_out)
        return terminated, timed_out

    def _reset_impl(self, ids):
        super()._reset_impl(ids)
        if hasattr(self, 'deposit_active'):
            selected = self.robot._ALL_INDICES if ids is None else ids
            self.deposit_active[selected] = False
            self.deposit_first_command[selected] = False
            self.deposit_start_step[selected] = 0
            self.deposit_hold_time[selected] = 0.
