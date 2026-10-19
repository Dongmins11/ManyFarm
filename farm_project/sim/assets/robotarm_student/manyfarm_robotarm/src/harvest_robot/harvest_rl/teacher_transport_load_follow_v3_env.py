"""Separate bounded load-follow candidate; frozen grasp/pull/stop/deposit code.

The only new actuation is decreasing the stored jaw target during qualified,
detached transport. Existing unloading/gain/release modes permanently disable
this extra budget for the episode. Original arm pause and failures still run.
"""
import torch
from .teacher_bridge_motion_compare_env import TeacherBridgeMotionCompareEnv
from .transport_load_follow import LoadFollowSpec, follow_step


class TeacherTransportLoadFollowV3Env(TeacherBridgeMotionCompareEnv):
    def __init__(self, *args, load_follow_spec=None, **kwargs):
        self.load_follow_spec = (load_follow_spec or LoadFollowSpec()).validate()
        super().__init__(*args, **kwargs)
        self.load_follow_spent = torch.zeros(self.num_envs, device=self.device)
        self.load_follow_disabled = torch.zeros(self.num_envs, device=self.device, dtype=torch.bool)
        self.load_follow_diagnostics = {}

    def _pre_physics_step(self, proposed):
        super()._pre_physics_step(proposed)
        scope = self.transport_before & ~self.deposit_before
        d = self.last_diagnostics
        # Reset leaves contact diagnostics empty until the first physics tick.
        # No transport is eligible then; do not read a sensor before initialization.
        force_min = (torch.minimum(d['fixed_force_N'], d['moving_force_N'])
                     if scope.any() else torch.zeros(self.num_envs, device=self.device))
        previous = self.targets[:, -1].clone()
        measured = self.robot.data.joint_pos[:, self.jids[-1]]
        near_stop = torch.zeros_like(scope)
        if scope.any():
            near_stop = (d['stop_zone_ok'] &
                         (self.transport_path_diagnostics['transport_goal_error_m'] < .005))
        # Modes are mutually exclusive. Budget is not renewed after an unload.
        self.load_follow_disabled |= (self.deposit_before | self.release_intent |
            self.transport_gain_active | (self.unload_spent > 0.))
        qualified = (self.grip & self.raw_grip & (self.slip < self.settings.max_slip)
                     if scope.any() else torch.zeros_like(scope))
        eligible = (scope & qualified & ~self._t(self.attached) & self.valid_detach &
                    self.has_retained & ~self.failure & self.bridge_preload.latched &
                    ~self.load_follow_disabled & ~near_stop & (self.actions[:, -1] <= 0.)) if scope.any() else torch.zeros_like(scope)
        target, spent, increment, weak = follow_step(previous, measured,
            self.bridge_preload.origin, self.load_follow_spent, eligible, force_min,
            spec=self.load_follow_spec, dt=self.step_dt, lower=self.lower[-1],
            contact_threshold=self.settings.contact_threshold,
            max_error=self.settings.gripper_max_error)
        changed = increment > 0.
        self.targets[changed, -1] = target[changed]
        self.actions[changed, -1] = -increment[changed]/(self.settings.gripper_speed*self.step_dt)
        self.load_follow_spent = spent
        self.load_follow_diagnostics = dict(
            load_follow_scope=scope.clone(), load_follow_eligible=eligible,
            load_follow_disabled=self.load_follow_disabled.clone(),
            load_follow_near_stop=near_stop, load_follow_qualified_before=qualified,
            load_follow_force_before_N=force_min.clone(),
            load_follow_jaw_before_rad=previous,
            load_follow_measured_before_rad=measured.clone(),
            load_follow_increment_rad=increment,
            load_follow_spent_rad=spent.clone(), load_follow_weak_before=weak)

    def _get_rewards(self):
        reward = super()._get_rewards()
        self.chain_snapshot.update({k: v.clone() for k, v in self.load_follow_diagnostics.items()})
        return reward

    def _reset_impl(self, ids):
        super()._reset_impl(ids)
        if hasattr(self, 'load_follow_spent'):
            selected = self.robot._ALL_INDICES if ids is None else ids
            self.load_follow_spent[selected] = 0.
            self.load_follow_disabled[selected] = False
