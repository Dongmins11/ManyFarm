"""Frozen guarded pull followed by legacy transport, without a scene reset.

This is an explicit 480Hz/35g -> 60Hz/9g transfer evaluation, not a trained60Hz
transport certification. Parent physics/failure checks run once per policy tick.
"""
import torch
from .teacher_bridge_pull_guarded_env import TeacherBridgePullGuardedEnv
from .env import HarvestEnv
from .logic import above_box, orientation_speed, transport_stop_speed
from .bridge_transport_60hz import next_transport, transport_targets, transport_observation


class TeacherBridgeTransportEnv(TeacherBridgePullGuardedEnv):
    def __init__(self, *args, transport_policy, **kwargs):
        super().__init__(*args, **kwargs)
        self.transport_policy = transport_policy
        self.transport_active = torch.zeros_like(self.pull_active)
        self.transport_start_step = torch.zeros_like(self.episode_length_buf)
        self.transport_before = self.transport_active.clone()
        self.transport_events = []

    def _target_elapsed_steps(self):
        result = super()._target_elapsed_steps()
        if hasattr(self, 'transport_active'):
            result = torch.where(self.transport_active,
                self.episode_length_buf-self.transport_start_step, result)
        return result

    def _transport_observations(self):
        raw = HarvestEnv._get_observations(self)['policy']
        tcp, _ = self._tcp()
        return {'policy': transport_observation(raw,
            self._target_fruit().data.root_link_pos_w-tcp,
            self.episode_length_buf-self.transport_start_step, self.max_episode_length)}

    def _pre_physics_step(self, proposed):
        previous = self.targets.clone()
        self.transport_before = self.transport_active.clone()
        preload = {k: getattr(self.bridge_preload, k).clone()
                   for k in ('origin', 'latched', 'released')}
        super()._pre_physics_step(proposed)
        scope = self.transport_before
        if not scope.any():
            return
        # Parent only proposes targets here; no physics has run yet. Replace
        # transport rows before _apply_action. Prefix rows are bit-for-bit intact.
        with torch.no_grad():
            action = self.transport_policy(self._transport_observations())
        if not torch.isfinite(action).all():
            raise FloatingPointError('Nonfinite transport command')
        elapsed = (self.episode_length_buf-self.transport_start_step)*self.step_dt
        targets, commands, scale = transport_targets(previous, action, scope,
            self.lower, self.upper, speed=self.settings.action_speed, dt=self.step_dt,
            elapsed=elapsed)
        self.targets[scope] = targets[scope]
        self.actions[scope] = commands[scope]
        for k, value in preload.items():
            getattr(self.bridge_preload, k)[scope] = value[scope]
        for k in ('path_hold', 'path_active', 'retention_target_hold'):
            self.path_diagnostics[k][scope] = False
        self.transport_scale = scale
        self.transport_raw_action = action.clone()

    def _update_task(self):
        # Exactly one physical/contact/grasp/retention update. Pull remains the
        # original task, so pre-transport stop/release logic cannot change prefix.
        super()._update_task()
        if not hasattr(self, 'transport_active'):
            return
        pull_success = self.success.clone()
        self.transport_active, first = next_transport(self.transport_active,
            pull_success, self.failure, self.valid_detach, self.has_retained,
            self.grip & self.raw_grip & (self.slip < self.settings.max_slip))
        self.transport_start_step[first] = self.episode_length_buf[first]
        fruit = self._target_fruit().data
        tcp, _ = self._tcp()
        zone = above_box(fruit.root_link_pos_w-self.scene.env_origins,
                         fruit.root_link_quat_w, self.settings)
        tcp_speed = (tcp-self.previous_tcp).norm(dim=-1)/self.step_dt
        pose_speed = (fruit.root_com_pos_w-self.previous_fruit_com).norm(dim=-1)/self.step_dt
        fruit_speed = fruit.root_com_lin_vel_w.norm(dim=-1)
        speed_ok = transport_stop_speed(pose_speed, fruit_speed, self.settings.release_speed)
        angular_ok = orientation_speed(self.previous_fruit_quat,
                                      fruit.root_link_quat_w, self.step_dt) < 1.
        stable = self.grip & self.has_grasped & (self.slip < self.settings.max_slip)
        paused = (zone & speed_ok & (tcp_speed <= self.settings.release_speed)
                  & angular_ok & stable & self.has_retained & self.valid_detach)
        scope = self.transport_before
        self.stop_time[scope] = torch.where(paused[scope],
            self.stop_time[scope]+self.step_dt, 0.)
        stopped = (self.stop_time >= self.settings.release_stop_s) & paused
        self.success = scope & stopped & ~self.failure
        self.last_diagnostics.update(success=self.success.clone(),
            transport_active=self.transport_active.clone(), transport_handoff=first,
            transport_action_active=scope.clone(), pull_retention_success=first,
            stop_zone_ok=zone, stop_fruit_speed_ok=speed_ok, stop_tcp_speed_ok=tcp_speed<=self.settings.release_speed,
            stop_angular_ok=angular_ok, stop_stable_grip_ok=stable, stop_all_ok=paused,
            stop_tcp_speed_m_s=tcp_speed, stop_fruit_pose_speed_m_s=pose_speed,
            release_stop_s=self.stop_time.clone())
        for i in first.nonzero().flatten().cpu().tolist():
            self.transport_events.append(dict(env_id=i,episode_step=int(self.episode_length_buf[i]),
                detached_hold_s=float(self.detached_time[i]),
                q=self.robot.data.joint_pos[i].cpu().tolist(),
                qd=self.robot.data.joint_vel[i].cpu().tolist(),
                fruit=self._target_fruit().data.root_link_pos_w[i].cpu().tolist(),
                targets=self.targets[i].cpu().tolist(),jaw_origin=float(self.bridge_preload.origin[i]),
                valid_detach=bool(self.valid_detach[i]),has_retained=bool(self.has_retained[i]),
                qualified=bool(self.grip[i]&self.raw_grip[i]), scene_reset=False))

    def _get_rewards(self):
        reward = super()._get_rewards()
        if hasattr(self, 'transport_active'):
            self.chain_snapshot['transport_elapsed_s'] = torch.where(self.transport_active,
                (self.episode_length_buf-self.transport_start_step)*self.step_dt, 0.)
            for j in range(6):
                self.chain_snapshot[f'transport_raw_action_{j}'] = (
                    self.transport_raw_action[:, j].clone() if hasattr(self, 'transport_raw_action')
                    else torch.zeros(self.num_envs, device=self.device))
            self.chain_snapshot['transport_arm_scale'] = (
                self.transport_scale.clone() if hasattr(self, 'transport_scale')
                else torch.zeros(self.num_envs, device=self.device))
        return reward

    def _reset_impl(self, ids):
        super()._reset_impl(ids)
        if hasattr(self, 'transport_active'):
            selected = self.robot._ALL_INDICES if ids is None else ids
            self.transport_active[selected] = False
            self.transport_start_step[selected] = 0
