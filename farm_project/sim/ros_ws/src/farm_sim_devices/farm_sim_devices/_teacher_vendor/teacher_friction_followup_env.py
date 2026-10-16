"""60Hz r2 원본 계산에서 추출. 재생성: sim/tools/import_teacher60.py."""

import math

import torch

from .teacher_jaw_surface_compare_v2_env import TeacherJawSurfaceCompareEnv

from .friction_followup import FollowupSpec, early_escape

from .transport_posture_escape import escape_velocity

from .logic import fruit_bounds


class TeacherFrictionFollowupEnv(TeacherJawSurfaceCompareEnv):

    def __init__(self,*args,followup_spec=None,**kwargs):
        self.followup_spec=(followup_spec or FollowupSpec()).validate()
        super().__init__(*args,**kwargs)
        self.followup_limited=torch.zeros_like(self.has_grasped)
        self.followup_default_limit=self.robot.data.joint_vel_limits[:,self.jids[-1]].clone()
        self.bridge_preload.rate=math.radians(self.followup_spec.bridge_rate_deg_s)
        self.followup_diagnostics={}

    def _pre_physics_step(self,proposed):
        previous=self.targets[:,:5].clone()
        super()._pre_physics_step(proposed)
        bridge=(self.bridge_started & ~self.pull_active & ~self.transport_before
                & ~self.deposit_before & ~self.release_intent & ~self.failure)
        cap=self.followup_spec.bridge_velocity_cap
        limited=bridge & (cap<1.5)
        changed=limited!=self.followup_limited
        # The parent's transport limit and actual open/deposit rules take over
        # afterwards. Restore our pre-bridge limit only outside those phases.
        restore=changed & ~limited & ~self.transport_before & ~self.deposit_before
        set_ids=(changed & limited).nonzero().flatten()
        if len(set_ids):self.robot.write_joint_velocity_limit_to_sim(torch.full((len(set_ids),1),cap,device=self.device),joint_ids=[self.jids[-1]],env_ids=set_ids)
        ids=restore.nonzero().flatten()
        if len(ids):self.robot.write_joint_velocity_limit_to_sim(self.followup_default_limit[ids,None],joint_ids=[self.jids[-1]],env_ids=ids)
        self.followup_limited=limited.clone()
        active=torch.zeros_like(bridge);angular=torch.zeros_like(self.grip_time)
        if self.followup_spec.transport_mode=='early_position' and self.transport_before.any():
            p,r,j=self.path_kin.pose_and_jacobian(self.robot.data.joint_pos[:,self.jids])
            fruit=self._target_fruit().data
            center,extent=fruit_bounds(fruit.root_link_pos_w-self.scene.env_origins,fruit.root_link_quat_w,self.settings)
            goal_center=center.clone();goal_center[:,:2]=center.new_tensor([self.settings.box_min[:2],self.settings.box_max[:2]]).mean(0)
            goal_center[:,2]=self.settings.box_max[2]+extent[:,2]+.035
            goal=p+goal_center-center;error=(goal-p).norm(dim=-1)
            qualified=self.grip & self.raw_grip & (self.slip<self.settings.max_slip)
            scope=self.transport_before & ~self.deposit_before & ~self.release_intent & ~self.failure
            blocked=self.transport_path_diagnostics.get('transport_blocked_joints',torch.zeros_like(error))
            eligible=early_escape(scope,self.transport_path.clear,error,blocked,qualified)
            fresh=eligible & ~self.posture_latched
            self.posture_rotation[fresh]=r[fresh];self.posture_latched|=fresh
            angle=(((self.posture_rotation@r.transpose(1,2)).diagonal(dim1=-2,dim2=-1).sum(-1)-1)/2).clamp(-1,1).acos()
            active=scope & qualified & self.transport_path.clear & self.posture_latched & (angle<.6) & (error>.003)
            elapsed=(self.episode_length_buf-self.transport_start_step)*self.step_dt
            ramp=.25+.75*(elapsed/3.).clamp(0,1)
            if active.any():
                velocity,blocked=escape_velocity(j,4*(goal-p),previous,self.lower,self.upper,ramp)
                self.targets[active,:5]=(previous+velocity*self.step_dt)[active]
                self.actions[active,:5]=(velocity/self.settings.action_speed)[active]
                predicted=(j@velocity[:,:,None]).squeeze(-1)
                angular=predicted[:,3:].norm(dim=-1)
                self.transport_path_diagnostics.update(transport_path_predicted_speed_m_s=
                    (j[:,:3]@(self.actions[:,:5]*self.settings.action_speed)[:,:,None]).squeeze(-1).norm(dim=-1))
        self.followup_diagnostics=dict(followup_bridge_limited=limited,
            followup_actual_velocity_limit_rad_s=self.robot.data.joint_vel_limits[:,self.jids[-1]].clone(),
            followup_escape_active=active,followup_escape_predicted_angular_rad_s=angular)
