"""60Hz r2 원본 계산에서 추출. 재생성: sim/tools/import_teacher60.py."""

import torch

from .teacher_bridge_transport_constrained_env import TeacherBridgeTransportConstrainedEnv

from .transport_contact_unload_v2 import unload_step


class TeacherBridgeTransportUnloadV2Env(TeacherBridgeTransportConstrainedEnv):

    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.unload_spent=torch.zeros(self.num_envs,device=self.device)
        self.unload_diagnostics={}

    def _pre_physics_step(self,proposed):
        previous=self.targets[:,-1].clone()
        super()._pre_physics_step(proposed)
        if not self.transport_before.any():return
        d=self.last_diagnostics
        eligible=(self.transport_before & self.grip & self.raw_grip
            & (self.slip<self.settings.max_slip) & ~self.release_intent
            & d['stop_zone_ok'] & (d['stop_tcp_speed_m_s']<=.02)
            & (d['stop_fruit_pose_speed_m_s']<=.02)
            & (self.transport_path_diagnostics['transport_goal_error_m']<.005)
            & (d['fruit_speed_m_s']>.2))
        force_min=torch.minimum(d['fixed_force_N'],d['moving_force_N'])
        target,self.unload_spent,increment=unload_step(previous,self.unload_spent,
            eligible,force_min,self.step_dt)
        self.targets[self.transport_before,-1]=target[self.transport_before].clamp(self.lower[-1],self.upper[-1])
        self.actions[self.transport_before,-1]=(increment/(self.settings.gripper_speed*self.step_dt))[self.transport_before]
        self.unload_diagnostics=dict(transport_unload_rad=self.unload_spent.clone(),
            transport_unload_increment_rad=increment,transport_unload_eligible=eligible,
            transport_unload_before_force_N=force_min)
