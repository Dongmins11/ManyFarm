"""Live HOME -> retained handoff -> stored arm hold / bounded short motion.

No bank restoration or extra squeeze. Diagnostic6s timeout is not task success.
"""
import torch
from .teacher_bridge_motion_compare_env import TeacherBridgeMotionCompareEnv
from .component_contact_probe import bounded_increment


class TeacherComponentProbeEnv(TeacherBridgeMotionCompareEnv):
    def __init__(self, *args, component_mode='chain', probe_duration_s=6., probe_distance_m=.05, **kwargs):
        if component_mode not in ('chain', 'hold', 'short') or probe_duration_s < 5 or not 0 < probe_distance_m <= .075:
            raise ValueError('Requires chain/hold/short,>=5s and<=75mm diagnostic command path')
        self.component_mode = component_mode; self.probe_duration_s = probe_duration_s
        self.probe_distance_m = probe_distance_m
        super().__init__(*args, **kwargs)
        self.probe_started = torch.zeros(self.num_envs,device=self.device,dtype=torch.bool)
        self.probe_start_step = torch.zeros_like(self.episode_length_buf)
        self.probe_arm_targets = torch.zeros(self.num_envs,5,device=self.device)
        self.probe_origin_tcp = torch.zeros(self.num_envs,3,device=self.device)
        self.probe_spent = torch.zeros(self.num_envs,device=self.device)

    def _pre_physics_step(self, proposed):
        previous = self.targets.clone()
        super()._pre_physics_step(proposed)
        if self.component_mode == 'chain': return
        scope = self.transport_before & self.probe_started
        if not scope.any(): return
        if self.component_mode == 'hold':
            self.targets[scope,:5] = self.probe_arm_targets[scope]
            self.actions[scope,:5] = 0.
        else:
            _,_,j = self.path_kin.pose_and_jacobian(self.robot.data.joint_pos[:,self.jids])
            velocity = self.actions[:,:5]*self.settings.action_speed
            velocity,self.probe_spent = bounded_increment(velocity,j,self.probe_spent,scope,
                budget=self.probe_distance_m,dt=self.step_dt)
            self.targets[scope,:5] = (previous[:,:5]+velocity*self.step_dt)[scope].clamp(self.lower[:5],self.upper[:5])
            self.actions[scope,:5] = (velocity/self.settings.action_speed)[scope]

    def _update_task(self):
        super()._update_task()
        if not hasattr(self,'probe_started'): return
        first = self.last_diagnostics['transport_handoff'] & ~self.probe_started
        self.probe_started |= first
        self.probe_start_step[first] = self.episode_length_buf[first]
        self.probe_arm_targets[first] = self.targets[first,:5]
        p,_,j = self.path_kin.pose_and_jacobian(self.robot.data.joint_pos[:,self.jids])
        self.probe_origin_tcp[first] = p[first]
        elapsed = torch.where(self.probe_started,(self.episode_length_buf-self.probe_start_step)*self.step_dt,0.)
        velocity = self.actions[:,:5]*self.settings.action_speed
        self.last_diagnostics.update(component_probe_started=self.probe_started.clone(),
            component_probe_elapsed_s=elapsed, component_probe_finished=self.probe_started & (elapsed>=self.probe_duration_s-1e-6),
            component_probe_command_distance_m=self.probe_spent.clone(),
            component_probe_tcp_distance_m=(p-self.probe_origin_tcp).norm(dim=-1),
            component_probe_arm_target_error_rad=(self.targets[:,:5]-self.probe_arm_targets).abs().amax(-1),
            component_probe_command_speed_m_s=(j[:,:3]@velocity[:,:,None]).squeeze(-1).norm(dim=-1),
            component_probe_implicit_jaw_torque_Nm=self.robot.data.applied_torque[:,self.jids[-1]].clone())

    def _get_dones(self):
        terminated,timed_out = super()._get_dones()
        if self.component_mode != 'chain' and hasattr(self,'probe_started'):
            timed_out |= self.probe_started & ((self.episode_length_buf-self.probe_start_step)*self.step_dt>=self.probe_duration_s-1e-6)
        return terminated,timed_out

    def _reset_impl(self, ids):
        super()._reset_impl(ids)
        if hasattr(self,'probe_started'):
            selected=self.robot._ALL_INDICES if ids is None else ids
            self.probe_started[selected]=False;self.probe_spent[selected]=0.
            self.probe_start_step[selected]=0
