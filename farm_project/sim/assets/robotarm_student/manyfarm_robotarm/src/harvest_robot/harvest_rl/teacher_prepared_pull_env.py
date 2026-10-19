"""Additional measured12mm probe in the same scene before frozen learned pull.

Only command/control state changes. Original attachment, contact, failure,
retention, box gates and finite physical task clock remain authoritative.
"""
import torch
from .teacher_transport_posture_env import TeacherTransportPostureEnv
from .bridge_pull_path import PullPath,PullPathSpec

SPEC=dict(command_travel_m=.012,required_actual_axial_m=.010,max_lateral_m=.002,
          speed_m_s=.005,joint_speed_rad_s=.04,orientation_length_m=.08,
          hold_s=.5,timeout_s=4.5,actor_clock='Local2s+time after preparation; original physical timeout unchanged')


class TeacherPreparedPullEnv(TeacherTransportPostureEnv):
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.prep_started=torch.zeros_like(self.pull_active)
        self.prep_moved=torch.zeros_like(self.pull_active)
        self.prep_done=torch.zeros_like(self.pull_active)
        self.prep_start_step=torch.zeros_like(self.episode_length_buf)
        self.prep_native_step=torch.zeros_like(self.episode_length_buf)
        self.prep_hold=torch.zeros(self.num_envs,device=self.device)
        self.prep_origin=torch.zeros(self.num_envs,3,device=self.device)
        self.prep_hold_targets=self.targets[:,:5].clone()
        self.prep_path=PullPath(self.num_envs,self.device,PullPathSpec(speed_m_s=.005,
            travel_m=.012,joint_speed_rad_s=.04,orientation_length_m=.08))
        self.prep_diag={}

    def _get_observations(self):
        obs=super()._get_observations()
        if hasattr(self,'prep_started'):
            scope=self.prep_started & ~self.transport_active & ~self.deposit_active
            elapsed=torch.where(self.prep_done,self.episode_length_buf-self.prep_native_step,0)
            obs['policy'][scope,42]=(1-(40+elapsed)/self.max_episode_length)[scope]
        return obs

    def _pre_physics_step(self,proposed):
        previous=self.targets[:,:5].clone()
        # A prep controller must not advance the old fallback's hidden waypoint.
        saved={k:getattr(self.path,k).clone() for k in ('started','origin','rotation','travel')}
        saved_risk=self.risk_latched.clone()
        super()._pre_physics_step(proposed)
        scope=self.prep_started & ~self.prep_done & ~self.transport_before & ~self.deposit_before & ~self.release_intent
        if scope.any():
            for k,v in saved.items():getattr(self.path,k)[scope]=v[scope]
            self.risk_latched[scope]=saved_risk[scope]
            p,r,j=self.path_kin.pose_and_jacobian(self.robot.data.joint_pos[:,self.jids])
            qualified=self.grip & self.raw_grip & (self.slip<self.settings.max_slip)
            elapsed=(self.episode_length_buf-self.prep_start_step)*self.step_dt
            moving=scope & ~self.prep_moved & self._t(self.attached) & ~self.failure & (elapsed<SPEC['timeout_s'])
            commands=self.actions.clone()
            commands[:,:5]=0.
            result,diag=self.prep_path.step(commands,p,r,j,active=moving,
                attached=self._t(self.attached),qualified=qualified,valid_detach=self.valid_detach,
                release=self.release_intent,axis=self.settings.tension_axis,
                ramp=torch.ones(self.num_envs,device=self.device),action_speed=self.settings.action_speed,dt=self.step_dt)
            self.targets[scope,:5]=previous[scope];self.actions[scope,:5]=0.
            self.targets[moving,:5]=(previous+result[:,:5]*self.settings.action_speed*self.step_dt)[moving].clamp(self.lower[:5],self.upper[:5])
            self.actions[moving,:5]=result[moving,:5]
            held=scope & self.prep_moved & self._t(self.attached)
            self.targets[held,:5]=self.prep_hold_targets[held]
            for k in ('path_active','path_hold','risk_first'):
                if k in self.path_diagnostics:self.path_diagnostics[k][scope]=False
            self.prep_command_diag=diag
        native=self.prep_done & self.pull_active & ~self.transport_before & ~self.deposit_before & ~self.release_intent & self._t(self.attached)
        native_elapsed=(self.episode_length_buf-self.prep_native_step)*self.step_dt
        ramp=.2+.8*(native_elapsed/.5).clamp(0,1)
        learned=native & ~self.path_diagnostics.get('path_active',torch.zeros_like(native))
        if learned.any():
            delta=(self.targets[:,:5]-previous)*ramp[:,None]
            self.targets[learned,:5]=(previous+delta)[learned]
            self.actions[learned,:5]=(delta/(self.settings.action_speed*self.step_dt))[learned]
            self.chain_scale[learned]=ramp[learned]
        self.prep_pre_diag=dict(prep_command_scope=scope,prep_native_scope=native,prep_native_ramp=ramp)

    def _update_task(self):
        super()._update_task()
        if not hasattr(self,'prep_started'):return
        p,r,j=self.path_kin.pose_and_jacobian(self.robot.data.joint_pos[:,self.jids])
        first=self.pull_active & ~self.prep_started & ~self.failure
        self.prep_origin[first]=p[first];self.prep_start_step[first]=self.episode_length_buf[first]
        self.prep_started|=first
        qualified=self.grip & self.raw_grip & (self.slip<self.settings.max_slip)
        attached=self._t(self.attached)
        delta=p-self.prep_origin;axis=p.new_tensor(self.settings.tension_axis);axis/=axis.norm()
        axial=(delta*axis).sum(-1);lateral=(delta-axial[:,None]*axis).norm(dim=-1)
        reached=(self.prep_started & ~self.prep_moved & ~self.prep_done & qualified & attached & ~self.failure &
            (axial>=SPEC['required_actual_axial_m']) & (lateral<=SPEC['max_lateral_m']))
        self.prep_hold_targets[reached]=self.targets[reached,:5];self.prep_moved|=reached
        valid=self.prep_started & self.prep_moved & ~reached & qualified & attached & ~self.failure & (axial>=.010-1e-6) & (lateral<=.002+1e-6)
        self.prep_hold=torch.where(valid,self.prep_hold+self.step_dt,0.)
        bypass=self.prep_started & self.valid_detach & ~attached & ~self.failure
        completed=(self.prep_hold>=.5-1e-6) | bypass
        native_first=completed & ~self.prep_done
        self.prep_done|=completed;self.prep_native_step[native_first]=self.episode_length_buf[native_first]
        elapsed=(self.episode_length_buf-self.prep_start_step)*self.step_dt
        self.prep_diag=dict(prep_started=self.prep_started.clone(),prep_first=first,
            prep_moved=self.prep_moved.clone(),prep_done=self.prep_done.clone(),prep_native_first=native_first,
            prep_actual_axial_m=torch.where(self.prep_started,axial,0.),prep_actual_lateral_m=torch.where(self.prep_started,lateral,0.),
            prep_hold_s=self.prep_hold.clone(),prep_bypass_valid_detach=bypass,
            prep_timeout=self.prep_started & ~self.prep_done & (elapsed>=4.5),
            prep_elapsed_s=torch.where(self.prep_started,elapsed,0.))

    def _get_rewards(self):
        result=super()._get_rewards()
        self.chain_snapshot.update({k:v.clone() for k,v in self.prep_diag.items()})
        if hasattr(self,'prep_pre_diag'):self.chain_snapshot.update({k:v.clone() for k,v in self.prep_pre_diag.items()})
        if hasattr(self,'prep_command_diag'):self.chain_snapshot.update({'prep_path_'+k:v.clone() for k,v in self.prep_command_diag.items()})
        return result

    def _reset_impl(self,ids):
        super()._reset_impl(ids)
        if hasattr(self,'prep_started'):
            selected=self.robot._ALL_INDICES if ids is None else ids
            for k in ('prep_started','prep_moved','prep_done','prep_start_step','prep_native_step','prep_hold'):
                getattr(self,k)[selected]=0
            self.prep_path.reset(selected)


from .teacher_handoff_observer import HandoffObserver
class ObservedPreparedEnv(HandoffObserver,TeacherPreparedPullEnv):
    pass
