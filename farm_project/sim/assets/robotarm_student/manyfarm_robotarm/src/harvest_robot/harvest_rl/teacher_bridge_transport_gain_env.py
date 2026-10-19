"""Ramp the jaw position gain after retained detach; restore before next HOME.

No target rebasing, contact flags, external forces or velocity-state writes.
This is an uncalibrated phase-local servo comparison, not the old physics profile.
"""
import torch
from .teacher_bridge_transport_unload_v2_env import TeacherBridgeTransportUnloadV2Env


def hold_stiffness(original,elapsed,final,ramp_s):
    if final<=0 or ramp_s<=0:raise ValueError('Positive gain/ramp required')
    return original+(final-original)*(elapsed/ramp_s).clamp(0.,1.)


class TeacherBridgeTransportGainEnv(TeacherBridgeTransportUnloadV2Env):
    def __init__(self,*args,hold_stiffness_Nm_rad=2.,gain_ramp_s=1.,**kwargs):
        if not 0.<hold_stiffness_Nm_rad<=8. or gain_ramp_s<=0.:
            raise ValueError('Requires jaw gain(0,8]Nm/rad and positive ramp')
        self.hold_stiffness_Nm_rad=hold_stiffness_Nm_rad;self.gain_ramp_s=gain_ramp_s
        super().__init__(*args,**kwargs)
        self.transport_gain_active=torch.zeros(self.num_envs,device=self.device,dtype=torch.bool)
        self.original_jaw_stiffness=self.robot.data.joint_stiffness[:,self.jids[-1]].clone()

    def _write_gain(self,ids,gain):
        self.robot.write_joint_stiffness_to_sim(gain[:,None],joint_ids=[self.jids[-1]],env_ids=ids)
        # ImplicitActuator uses its own coefficients for the approximate torque
        # diagnostics. Keep them consistent with the actual PhysX drive gain.
        self.robot.actuators['gripper'].stiffness[ids,0]=gain

    def _pre_physics_step(self,proposed):
        super()._pre_physics_step(proposed)
        ids=self.transport_before.nonzero().flatten()
        if ids.numel():
            elapsed=(self.episode_length_buf[ids]-self.transport_start_step[ids])*self.step_dt
            gain=hold_stiffness(self.original_jaw_stiffness[ids],elapsed,
                               self.hold_stiffness_Nm_rad,self.gain_ramp_s)
            self._write_gain(ids,gain);self.transport_gain_active[ids]=True

    def _get_rewards(self):
        reward=super()._get_rewards()
        if hasattr(self,'transport_gain_active'):
            self.chain_snapshot.update(transport_gain_active=self.transport_gain_active.clone(),
                transport_jaw_stiffness_Nm_rad=self.robot.data.joint_stiffness[:,self.jids[-1]].clone())
        return reward

    def _reset_impl(self,ids):
        if hasattr(self,'transport_gain_active'):
            selected=self.robot._ALL_INDICES if ids is None else ids
            affected=selected[self.transport_gain_active[selected]]
            if affected.numel():self._write_gain(affected,self.original_jaw_stiffness[affected])
            self.transport_gain_active[selected]=False
        super()._reset_impl(ids)
