"""Separate inference adapter; the learned bridge-pull source stays frozen."""
import torch
from .teacher_bridge_pull_env import TeacherBridgePullEnv
from .matched_pull_60hz import TensorGraspKinematics
from .settings import CACHE
from .bridge_pull_path import PullPath


class TeacherBridgePullPathEnv(TeacherBridgePullEnv):
    def __init__(self,*args,path_spec,**kwargs):
        super().__init__(*args,**kwargs)
        self.path=PullPath(self.num_envs,self.device,path_spec)
        self.path_kin=TensorGraspKinematics(CACHE/'harvest_training.urdf',self.settings.diameter,device=self.device)
        self.path_diagnostics={}

    def _pre_physics_step(self,proposed):
        previous=self.targets.clone()
        super()._pre_physics_step(proposed)
        q=self.robot.data.joint_pos[:,self.jids]
        p,r,j=self.path_kin.pose_and_jacobian(q)
        actual=self._tcp()[0]-self.scene.env_origins
        error=(p-actual).norm(dim=-1)
        if (error>.002).any():raise ValueError('Cached controller FK differs from actual TCP by over2mm')
        # Parent already applied its exact ramp and original jaw controller.
        # Convert its target increments back to bounded commands for this adapter.
        command=self.actions.clone()
        command[:,:5]=(self.targets[:,:5]-previous[:,:5])/(self.settings.action_speed*self.step_dt)
        elapsed=self._target_elapsed_steps()*self.step_dt
        ramp=.2+.8*((elapsed-2.)/.5).clamp(0.,1.)
        qualified=torch.zeros_like(self.pull_active)
        if hasattr(self,'raw_grip') and hasattr(self,'slip'):
            qualified=self.grip & self.raw_grip & (self.slip<self.settings.max_slip)
        result,diag=self.path.step(command,p,r,j,active=self.pull_active,
            attached=self._t(self.attached),qualified=qualified,
            valid_detach=self.valid_detach,release=self.release_intent,axis=self.settings.tension_axis,
            ramp=ramp,action_speed=self.settings.action_speed,dt=self.step_dt)
        scope=diag['path_active'] | diag['path_hold']
        self.targets[scope,:5]=(previous[:,:5]+result[:,:5]*self.settings.action_speed*self.step_dt)[scope].clamp(self.lower[:5],self.upper[:5])
        self.actions[scope,:5]=result[scope,:5]
        diag['path_fk_error_m']=error
        self.path_diagnostics=diag

    def _get_rewards(self):
        result=super()._get_rewards()
        if hasattr(self,'path_diagnostics'):
            self.last_diagnostics.update(self.path_diagnostics)
            self.chain_snapshot.update({k:v.clone() for k,v in self.path_diagnostics.items()})
        return result

    def _reset_impl(self,ids):
        super()._reset_impl(ids)
        if hasattr(self,'path'):
            self.path.reset(self.robot._ALL_INDICES if ids is None else ids)
