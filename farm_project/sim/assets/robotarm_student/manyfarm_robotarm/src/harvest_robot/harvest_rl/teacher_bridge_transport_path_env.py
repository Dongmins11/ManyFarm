"""Position-feedback transport comparison from the identical retained pull state."""
import torch
from .teacher_bridge_transport_env import TeacherBridgeTransportEnv
from .bridge_transport_path import TransportPath
from .logic import fruit_bounds


class TeacherBridgeTransportPathEnv(TeacherBridgeTransportEnv):
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.transport_path=TransportPath(self.num_envs,self.device)
        self.transport_path_diagnostics={}

    def _pre_physics_step(self,proposed):
        previous=self.targets.clone()
        super()._pre_physics_step(proposed)
        scope=self.transport_before
        if not scope.any():return
        p,r,j=self.path_kin.pose_and_jacobian(self.robot.data.joint_pos[:,self.jids])
        fruit=self._target_fruit().data
        center,extent=fruit_bounds(fruit.root_link_pos_w-self.scene.env_origins,
                                  fruit.root_link_quat_w,self.settings)
        goal_center=center.clone()
        goal_center[:,:2]=center.new_tensor(self.settings.box_min[:2]+self.settings.box_max[:2]).reshape(2,2).mean(0)
        goal_center[:,2]=self.settings.box_max[2]+extent[:,2]+.035
        goal=p+goal_center-center
        qualified=self.grip & self.raw_grip & (self.slip<self.settings.max_slip)
        elapsed=(self.episode_length_buf-self.transport_start_step)*self.step_dt
        velocity,diag=self.transport_path.step(p,r,j,goal,active=scope,
            qualified=qualified,elapsed=elapsed,dt=self.step_dt)
        self.targets[scope,:5]=(previous[:,:5]+velocity*self.step_dt)[scope].clamp(self.lower[:5],self.upper[:5])
        self.targets[scope,-1]=previous[scope,-1]
        self.actions[scope,:5]=(velocity/self.settings.action_speed)[scope]
        self.actions[scope,-1]=0.
        self.transport_path_diagnostics=diag

    def _get_rewards(self):
        reward=super()._get_rewards()
        self.chain_snapshot.update({k:v.clone() for k,v in self.transport_path_diagnostics.items()})
        return reward

    def _reset_impl(self,ids):
        super()._reset_impl(ids)
        if hasattr(self,'transport_path'):
            self.transport_path.reset(self.robot._ALL_INDICES if ids is None else ids)
