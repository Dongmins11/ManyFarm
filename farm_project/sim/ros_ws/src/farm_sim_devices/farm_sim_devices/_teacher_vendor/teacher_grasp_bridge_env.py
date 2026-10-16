"""60Hz r2 원본 계산에서 추출. 재생성: sim/tools/import_teacher60.py."""

import math

import torch

from .teacher_load_reserve_env import TeacherLoadReserveEnv

from .bounded_grip_60hz import BoundedGripPreload

from .grasp_bridge_60hz import SPEC, bridge_step


class TeacherGraspBridgeEnv(TeacherLoadReserveEnv):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.bridge_started = torch.zeros_like(self.has_grasped)
        self.bridge_hold_time = torch.zeros_like(self.grip_time)
        self.bridge_arm_targets = self.targets[:, :5].clone()
        self.bridge_preload = BoundedGripPreload(self.num_envs, self.device,
            math.radians(SPEC['preload_deg']), math.radians(SPEC['preload_rate_deg_s']))
        self.bridge_episode_records = []
        self.bridge_serial = torch.zeros(self.num_envs,device=self.device,dtype=torch.long)
        self.bridge_totals = dict(confirmed=0, passed=0, contact_loss=0, original_failure=0)

    def _pre_physics_step(self, proposed):
        previous = self.targets.clone()
        super()._pre_physics_step(proposed)
        if not hasattr(self, 'bridge_started'):
            return
        scope = self.bridge_started & ~self.release_intent
        self.actions[scope] = 0.
        self.targets[scope, :5] = self.bridge_arm_targets[scope]
        target, _ = self.bridge_preload.step(previous[:, -1], self.targets[:, -1],
            self.robot.data.joint_pos[:, self.jids[-1]], self.actions[:, -1], scope,
            speed=self.settings.gripper_speed, dt=self.step_dt,
            max_error=self.settings.gripper_max_error, lower=self.lower[-1], upper=self.upper[-1])
        self.targets[:, -1] = target

    def _update_task(self):
        super()._update_task()
        if not hasattr(self, 'bridge_started'):
            return
        original_success, original_failure = self.success.clone(), self.failure.clone()
        qualified = self.grip & self.raw_grip & (self.slip < self.settings.max_slip)
        (self.bridge_started, self.bridge_hold_time, self.success,
            lost, first) = bridge_step(self.bridge_started, self.bridge_hold_time,
                original_success, qualified, self._t(self.attached), original_failure, self.step_dt)
        self.bridge_arm_targets[first] = self.targets[first, :5]
        self.failure |= lost
        fruit = self._target_fruit().data
        self.last_diagnostics.update(instant_grasp_success=original_success,
            bridge_confirmed=self.bridge_started.clone(), bridge_hold_s=self.bridge_hold_time.clone(),
            bridge_first_confirmation=first, failure_bridge_contact_loss=lost,
            bridge_original_failure=original_failure,
            bridge_arm_speed_rad_s=self.robot.data.joint_vel[:, self.jids[:5]].abs().amax(-1),
            bridge_fruit_speed_m_s=fruit.root_com_lin_vel_w.norm(dim=-1),
            bridge_fruit_angular_speed_rad_s=fruit.root_com_ang_vel_w.norm(dim=-1),
            success=self.success.clone(), failure=self.failure.clone())
