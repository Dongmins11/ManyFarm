"""60Hz r2 원본 계산에서 추출. 재생성: sim/tools/import_teacher60.py."""

import torch

from .teacher_pull_stability_env import TeacherPullStabilityEnv

from .transport_posture_escape import escape_velocity

from .logic import fruit_bounds


class TeacherTransportPostureEnv(TeacherPullStabilityEnv):

    def __init__(self,*args,posture_mode='off',**kwargs):
        if posture_mode not in ('off','position','null','center'):
            raise ValueError('Unknown posture comparison')
        self.posture_mode=posture_mode
        super().__init__(*args,**kwargs)
        self.posture_ticks=torch.zeros_like(self.episode_length_buf)
        self.posture_latched=torch.zeros_like(self.pull_active)
        self.posture_rotation=torch.eye(3,device=self.device).repeat(self.num_envs,1,1)
        self.posture_diagnostics={}
        self.center_path=torch.zeros(self.num_envs,device=self.device)

    def _pre_physics_step(self,proposed):
        previous=self.targets[:,:5].clone()
        super()._pre_physics_step(proposed)
        p,r,j=self.path_kin.pose_and_jacobian(self.robot.data.joint_pos[:,self.jids])
        qualified=(self.grip & self.raw_grip & (self.slip<self.settings.max_slip)
                   if hasattr(self,'raw_grip') else torch.zeros_like(self.pull_active))
        scope=self.transport_before & qualified & ~self.deposit_before & ~self.release_intent & ~self.failure
        base=self.actions[:,:5]*self.settings.action_speed
        fruit=self._target_fruit().data
        center,extent=fruit_bounds(fruit.root_link_pos_w-self.scene.env_origins,fruit.root_link_quat_w,self.settings)
        box_goal=center.clone();box_goal[:,:2]=center.new_tensor([self.settings.box_min[:2],self.settings.box_max[:2]]).mean(0)
        box_goal[:,2]=self.settings.box_max[2]+extent[:,2]+.035
        goal=p+box_goal-center
        error=(goal-p).norm(dim=-1)
        blocked=self.transport_path_diagnostics.get('transport_blocked_joints',torch.zeros_like(error))
        stalled=scope & self.transport_path.clear & (error>.02) & (base.abs().amax(-1)<.005) & (blocked>=1)
        self.posture_ticks=torch.where(stalled,self.posture_ticks+1,0)
        fresh=(self.posture_ticks>=10) & ~self.posture_latched
        if self.posture_mode in ('position','null'):
            self.posture_rotation[fresh]=r[fresh];self.posture_latched|=fresh
        else:fresh=torch.zeros_like(fresh)
        angle=(((self.posture_rotation@r.transpose(1,2)).diagonal(dim1=-2,dim2=-1).sum(-1)-1)/2).clamp(-1,1).acos()
        active=scope & self.posture_latched & (angle<.6) & (error>.003)
        elapsed=(self.episode_length_buf-self.transport_start_step)*self.step_dt
        ramp=.25+.75*(elapsed/3.).clamp(0,1)
        velocity=base.clone()
        if active.any():
            v,mask=escape_velocity(j,4*(goal-p),previous,self.lower,self.upper,ramp,centering=self.posture_mode=='null')
            velocity[active]=v[active]
        correction=torch.zeros_like(active);increment=torch.zeros_like(error)
        if self.posture_mode=='center':
            delta=self._grasp_center(self._target_fruit())-self._tcp()[0]
            correction=scope & self.transport_path.clear & (delta.norm(dim=-1)>.008) & (self.center_path<.002-1e-9)
            # At most2mm of requested corrective TCP motion; never move an
            # unqualified/free-slipping fruit or rewrite its measured state.
            wanted=delta*2.;wanted*= (.002/wanted.norm(dim=-1).clamp_min(1e-12)).clamp_max(1)[:,None]
            wanted*=((.002-self.center_path).clamp_min(0)/(wanted.norm(dim=-1)*.05).clamp_min(1e-12)).clamp_max(1)[:,None]
            jc=j.clone();jc[:,3:]*=.08
            desired=torch.cat((wanted,torch.zeros_like(wanted)),-1)
            eye=torch.eye(5,device=p.device)
            dv=torch.linalg.solve(jc.transpose(1,2)@jc+.003**2*eye,jc.transpose(1,2)@desired[:,:,None]).squeeze(-1)
            predicted=(j[:,:3]@dv[:,:,None]).squeeze(-1)
            correction &= (predicted*delta).sum(-1)>0
            velocity[correction]+=dv[correction]
            increment=predicted.norm(dim=-1)*.05*correction
            self.center_path+=increment
        changed=active|correction
        if changed.any():
            # Final combined commands keep original speed, elbow and joint guards.
            lo=self.lower[:5];hi=self.upper[:5].clone();hi[2]=hi[2].clamp_max(1.45)
            velocity=velocity.maximum((lo-previous)/.05).minimum((hi-previous)/.05)
            predicted=(j@velocity[:,:,None]).squeeze(-1)
            scale=(.3*ramp/velocity.abs().amax(-1).clamp_min(1e-12)).clamp_max(1.)
            scale=scale.minimum((.035*ramp/predicted[:,:3].norm(dim=-1).clamp_min(1e-12)).clamp_max(1.))
            velocity*=scale[:,None]
            self.targets[changed,:5]=(previous+velocity*.05)[changed]
            self.actions[changed,:5]=(velocity/self.settings.action_speed)[changed]
            self.transport_path_diagnostics.update(transport_path_predicted_speed_m_s=
                (j[:,:3]@(self.actions[:,:5]*self.settings.action_speed)[:,:,None]).squeeze(-1).norm(dim=-1),
                motion_compare_command_rad_s=(self.actions[:,:5]*self.settings.action_speed).abs().amax(-1))
        self.posture_diagnostics=dict(posture_stall=stalled,posture_ticks=self.posture_ticks.clone(),
            posture_first=fresh,posture_active=active,posture_changed=changed,posture_scope=scope,
            posture_angle_rad=angle,posture_center_active=correction,posture_center_path_m=self.center_path.clone(),
            posture_predicted_angular_rad_s=(j[:,3:]@(self.actions[:,:5]*self.settings.action_speed)[:,:,None]).squeeze(-1).norm(dim=-1),
            posture_base_max_rad_s=base.abs().amax(-1))
