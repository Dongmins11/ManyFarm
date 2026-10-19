"""Separate constrained-path comparison; all physical failure gates remain."""
import torch
from .teacher_bridge_transport_path_env import TeacherBridgeTransportPathEnv
from .bridge_transport_constrained import solve_velocity


class TeacherBridgeTransportConstrainedEnv(TeacherBridgeTransportPathEnv):
    def _pre_physics_step(self,proposed):
        previous=self.targets.clone()
        super()._pre_physics_step(proposed)
        scope=self.transport_before
        if not scope.any():return
        p,r,j=self.path_kin.pose_and_jacobian(self.robot.data.joint_pos[:,self.jids])
        from .logic import fruit_bounds
        center,extent=fruit_bounds(self._target_fruit().data.root_link_pos_w-self.scene.env_origins,
            self._target_fruit().data.root_link_quat_w,self.settings)
        box_goal=center.clone()
        box_goal[:,:2]=center.new_tensor([self.settings.box_min[:2],self.settings.box_max[:2]]).mean(0)
        box_goal[:,2]=self.settings.box_max[2]+extent[:,2]+.035
        goal=p+box_goal-center
        exit_goal=self.transport_path.origin.clone();exit_goal[:,0]-=.03
        target=torch.where(self.transport_path.clear[:,None],goal,exit_goal)
        skew=self.transport_path.rotation@r.transpose(1,2)
        angular=2.*torch.stack((skew[:,2,1]-skew[:,1,2],skew[:,0,2]-skew[:,2,0],skew[:,1,0]-skew[:,0,1]),-1)
        wanted=torch.cat((4.*(target-p),angular*.02),-1)
        elapsed=(self.episode_length_buf-self.transport_start_step)*self.step_dt
        ramp=.25+.75*(elapsed/3.).clamp(0.,1.)
        velocity,blocked=solve_velocity(j,wanted,previous[:,:5],self.lower,self.upper,ramp)
        qualified=self.grip & self.raw_grip & (self.slip<self.settings.max_slip)
        velocity=torch.where((scope & qualified)[:,None],velocity,0.)
        self.targets[scope,:5]=(previous[:,:5]+velocity*self.step_dt)[scope].clamp(self.lower[:5],self.upper[:5])
        self.actions[scope,:5]=(velocity/self.settings.action_speed)[scope]
        self.transport_path_diagnostics.update(transport_blocked_joints=blocked.sum(-1),
            transport_path_predicted_speed_m_s=(j[:,:3]@velocity[:,:,None]).squeeze(-1).norm(dim=-1))
