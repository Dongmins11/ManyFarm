"""Phase-local loaded-jaw velocity bound; same position targets/effort/gains.

This changes a physical actuator velocity limit, not measured states. It is a
comparison candidate, not a calibrated STS3215 motor model. Restore on reset.
"""
import torch
from .teacher_bridge_transport_unload_v2_env import TeacherBridgeTransportUnloadV2Env


class TeacherBridgeTransportServoEnv(TeacherBridgeTransportUnloadV2Env):
    def __init__(self,*args,jaw_hold_velocity_rad_s=.15,**kwargs):
        if not 0.<jaw_hold_velocity_rad_s<=1.5:
            raise ValueError('Loaded jaw speed must be in(0,1.5]rad/s')
        self.jaw_hold_velocity_rad_s=jaw_hold_velocity_rad_s
        super().__init__(*args,**kwargs)
        self.transport_jaw_limited=torch.zeros(self.num_envs,device=self.device,dtype=torch.bool)
        self.original_jaw_velocity_limits=self.robot.data.joint_vel_limits[:,self.jids[-1]].clone()

    def _pre_physics_step(self,proposed):
        super()._pre_physics_step(proposed)
        first=self.transport_before & ~self.transport_jaw_limited
        ids=first.nonzero().flatten()
        if ids.numel():
            self.robot.write_joint_velocity_limit_to_sim(
                torch.full((len(ids),1),self.jaw_hold_velocity_rad_s,device=self.device),
                joint_ids=[self.jids[-1]],env_ids=ids)
            self.transport_jaw_limited[first]=True

    def _get_rewards(self):
        reward=super()._get_rewards()
        if hasattr(self,'transport_jaw_limited'):
            self.chain_snapshot.update(transport_jaw_limited=self.transport_jaw_limited.clone(),
                transport_jaw_velocity_limit_rad_s=self.robot.data.joint_vel_limits[:,self.jids[-1]].clone())
        return reward

    def _reset_impl(self,ids):
        if hasattr(self,'transport_jaw_limited'):
            selected=self.robot._ALL_INDICES if ids is None else ids
            affected=selected[self.transport_jaw_limited[selected]]
            if affected.numel():
                self.robot.write_joint_velocity_limit_to_sim(self.original_jaw_velocity_limits[affected,None],
                    joint_ids=[self.jids[-1]],env_ids=affected)
            self.transport_jaw_limited[selected]=False
        super()._reset_impl(ids)
