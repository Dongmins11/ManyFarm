"""Motion comparisons after actual pull retention; original deposit remains intact."""
import torch
from .teacher_bridge_deposit_env import TeacherBridgeDepositEnv
from .transport_motion_compare import solve_motion, validate_motion
from .logic import fruit_bounds


class TeacherBridgeMotionCompareEnv(TeacherBridgeDepositEnv):
    def __init__(self, *args, transport_speed_m_s=.035, orientation_length_m=.02, **kwargs):
        validate_motion(transport_speed_m_s, orientation_length_m)
        self.transport_speed_m_s = transport_speed_m_s
        self.orientation_length_m = orientation_length_m
        super().__init__(*args, **kwargs)

    def _pre_physics_step(self, proposed):
        previous = self.targets.clone()
        super()._pre_physics_step(proposed)
        scope = self.transport_before
        if not scope.any(): return
        p, r, jacobian = self.path_kin.pose_and_jacobian(self.robot.data.joint_pos[:, self.jids])
        qualified = self.grip & self.raw_grip & (self.slip < self.settings.max_slip)
        elapsed = (self.episode_length_buf-self.transport_start_step)*self.step_dt
        ramp = .25+.75*(elapsed/3.).clamp(0., 1.)
        # The baseline is exactly the original parent command. Candidate rows
        # replace only arm commands, integrated once from the pre-step targets.
        if (self.transport_speed_m_s, self.orientation_length_m) != (.035, .02):
            center, extent = fruit_bounds(self._target_fruit().data.root_link_pos_w-self.scene.env_origins,
                self._target_fruit().data.root_link_quat_w, self.settings)
            box_goal = center.clone()
            box_goal[:, :2] = center.new_tensor([self.settings.box_min[:2], self.settings.box_max[:2]]).mean(0)
            box_goal[:, 2] = self.settings.box_max[2]+extent[:, 2]+.035
            goal = p+box_goal-center
            exit_goal = self.transport_path.origin.clone(); exit_goal[:, 0] -= .03
            target = torch.where(self.transport_path.clear[:, None], goal, exit_goal)
            skew = self.transport_path.rotation@r.transpose(1, 2)
            angular = 2.*torch.stack((skew[:, 2, 1]-skew[:, 1, 2],
                skew[:, 0, 2]-skew[:, 2, 0], skew[:, 1, 0]-skew[:, 0, 1]), -1)
            wanted = torch.cat((4.*(target-p), angular*self.orientation_length_m), -1)
            velocity, blocked = solve_motion(jacobian, wanted, previous[:, :5], self.lower,
                self.upper, ramp, speed=self.transport_speed_m_s, orientation_length=self.orientation_length_m)
            velocity = torch.where((scope & qualified)[:, None], velocity, 0.)
            self.targets[scope, :5] = (previous[:, :5]+velocity*self.step_dt)[scope].clamp(self.lower[:5], self.upper[:5])
            self.actions[scope, :5] = (velocity/self.settings.action_speed)[scope]
            self.transport_path_diagnostics['transport_blocked_joints'] = blocked.sum(-1)
        commanded = self.actions[:, :5]*self.settings.action_speed
        self.transport_path_diagnostics.update(
            transport_path_predicted_speed_m_s=(jacobian[:, :3]@commanded[:, :, None]).squeeze(-1).norm(dim=-1),
            motion_compare_command_rad_s=commanded.abs().amax(-1),
            motion_compare_ramp=ramp.clone(), motion_compare_qualified=qualified.clone(),
            motion_compare_speed_limit_m_s=torch.full_like(ramp, self.transport_speed_m_s),
            motion_compare_orientation_length_m=torch.full_like(ramp, self.orientation_length_m))
