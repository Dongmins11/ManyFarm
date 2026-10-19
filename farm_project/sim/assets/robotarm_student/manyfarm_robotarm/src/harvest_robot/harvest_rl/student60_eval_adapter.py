"""Student command writer and read-only evaluation bookkeeping.

No Teacher pre-step/controller is called. Physical plant and outcome methods are
injected by the Isaac-only subclass; CPU tests can exercise this boundary.
"""
import numpy as np
import torch
from harvest_runtime.student60 import apply_sim_command, encode_command


def forbidden_teacher(*args, **kwargs):
    raise RuntimeError('Teacher control is forbidden in Student60 evaluation')


def reset_student_servo(env,ids,gain,limit):
    """Restore the pinned initial drive only at explicit episode reset."""
    env.robot.write_joint_stiffness_to_sim(gain[ids,None],joint_ids=[env.jids[-1]],env_ids=ids)
    env.robot.actuators['gripper'].stiffness[ids,0]=gain[ids]
    env.robot.write_joint_velocity_limit_to_sim(limit[ids,None],joint_ids=[env.jids[-1]],env_ids=ids)


def student_release_begin(opening,deposit,armed,previous_qualified,intent,already_released):
    # Evaluate at the command boundary, before opening can remove contact.
    return opening & deposit & armed & previous_qualified & ~intent & ~already_released


class Student60CommandBoundary:
    def _pre_physics_step(self, placeholder):
        if torch.any(placeholder != 0) or self.pending_student_command is None:
            raise ValueError('Only an explicit Student60 command may drive this environment')
        # Truth is saved solely for the unchanged physical outcome predicates.
        tcp, _ = self._tcp()
        fruit = self._target_fruit().data
        self.previous_tcp = tcp.clone()
        self.previous_fruit_com = fruit.root_com_pos_w.clone()
        self.previous_fruit_speed = fruit.root_com_lin_vel_w.norm(dim=-1).clone()
        self.previous_fruit_quat = fruit.root_link_quat_w.clone()
        self.previous_raw_grip = getattr(self,'raw_grip',torch.zeros_like(self.has_grasped)).clone()
        self.previous_gripper_q = self.robot.data.joint_pos[:, self.jids[-1]].clone()
        self.previous_actions.copy_(self.actions)
        previous = self.targets.clone()
        apply_sim_command(self, self.pending_student_command)
        speed = self.targets.new_tensor([self.settings.action_speed]*5 + [self.settings.gripper_speed])
        # Diagnostic opening direction, NEVER integrated back into the command.
        self.actions = (self.targets-previous)/(speed*self.step_dt)
        self.policy_active_before = self.pull_active.clone()
        self.entry_grasp_active = ~self.pull_active
        self.transport_before = self.transport_active.clone()
        self.deposit_before = self.deposit_active.clone()
        if hasattr(self,'_record_assessment_inputs'):self._record_assessment_inputs()
        self.detach_event.zero_(); self.grasp_event.zero_()
        self.last_applied_command = encode_command(
            self.targets[0].cpu().numpy(),
            [float(self.robot.data.joint_stiffness[0, self.jids[-1]]),
             float(self.robot.data.joint_vel_limits[0, self.jids[-1]])],
            self.lower.cpu().numpy(), self.upper.cpu().numpy())
        np.testing.assert_allclose(self.last_applied_command, self.pending_student_command, atol=3e-7)
        self.pending_student_command = None
        self.control_checks = getattr(self, 'control_checks', 0)+1

    def _verify_student_command(self):
        current = encode_command(self.targets[0].cpu().numpy(),
            [float(self.robot.data.joint_stiffness[0, self.jids[-1]]),
             float(self.robot.data.joint_vel_limits[0, self.jids[-1]])],
            self.lower.cpu().numpy(), self.upper.cpu().numpy())
        np.testing.assert_allclose(current, self.last_applied_command, atol=3e-7)

    def _apply_action(self):
        self._verify_student_command()
        # Only the original actuator target + response6 plant/stem wrench.
        self.original_plant_action()
        self._verify_student_command()
        self.physics_control_checks = getattr(self, 'physics_control_checks', 0)+1

    def _get_observations(self):
        # DirectRLEnv needs a tensor result; no privileged Teacher observations
        # are produced. Student60Controller gets separate native sensor inputs.
        return {'policy': torch.zeros((self.num_envs, 82), device=self.device)}
