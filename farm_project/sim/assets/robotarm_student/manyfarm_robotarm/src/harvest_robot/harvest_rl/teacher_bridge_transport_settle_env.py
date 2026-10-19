"""Reduce compression only after a measured stationary box-waypoint plateau."""
import torch
from .teacher_bridge_transport_gain_env import TeacherBridgeTransportGainEnv,hold_stiffness
from .teacher_bridge_transport_unload_v2_env import TeacherBridgeTransportUnloadV2Env


def plateau_ticks(previous,eligible):
    return torch.where(eligible,previous+1,0)


class TeacherBridgeTransportSettleEnv(TeacherBridgeTransportGainEnv):
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.gain_plateau_ticks=torch.zeros(self.num_envs,device=self.device,dtype=torch.long)
        self.gain_start_step=torch.zeros_like(self.episode_length_buf)
        self.settle_diagnostics={}

    def _pre_physics_step(self,proposed):
        # Call the untouched2deg controller directly: never lower the gain on
        # the way to the box merely because transport has started.
        TeacherBridgeTransportUnloadV2Env._pre_physics_step(self,proposed)
        if not self.transport_before.any():return
        d=self.last_diagnostics
        force_min=torch.minimum(d['fixed_force_N'],d['moving_force_N'])
        eligible=(self.transport_before & self.grip & self.raw_grip
            & (self.slip<self.settings.max_slip) & ~self.release_intent
            & d['stop_zone_ok'] & (d['stop_tcp_speed_m_s']<=.02)
            & (d['stop_fruit_pose_speed_m_s']<=.02)
            & (self.transport_path_diagnostics['transport_goal_error_m']<.005)
            & (d['fruit_speed_m_s']>.2) & (force_min>.5))
        self.gain_plateau_ticks=plateau_ticks(self.gain_plateau_ticks,eligible)
        first=(self.gain_plateau_ticks>=6) & ~self.transport_gain_active
        self.gain_start_step[first]=self.episode_length_buf[first]
        self.transport_gain_active |= first
        ids=(self.transport_before & self.transport_gain_active).nonzero().flatten()
        if ids.numel():
            elapsed=(self.episode_length_buf[ids]-self.gain_start_step[ids])*self.step_dt
            gain=hold_stiffness(self.original_jaw_stiffness[ids],elapsed,
                               self.hold_stiffness_Nm_rad,self.gain_ramp_s)
            self._write_gain(ids,gain)
        self.settle_diagnostics=dict(transport_gain_eligible=eligible,
            transport_gain_plateau_ticks=self.gain_plateau_ticks.clone(),
            transport_gain_started=first,
            transport_gain_elapsed_s=torch.where(self.transport_gain_active,
                (self.episode_length_buf-self.gain_start_step)*self.step_dt,0.))

    def _get_rewards(self):
        reward=super()._get_rewards()
        self.chain_snapshot.update({k:v.clone() for k,v in self.settle_diagnostics.items()})
        return reward

    def _reset_impl(self,ids):
        super()._reset_impl(ids)
        if hasattr(self,'gain_plateau_ticks'):
            selected=self.robot._ALL_INDICES if ids is None else ids
            self.gain_plateau_ticks[selected]=0;self.gain_start_step[selected]=0
