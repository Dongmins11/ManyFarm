"""60Hz r2 원본 계산에서 추출. 재생성: sim/tools/import_teacher60.py."""

import torch

from .quaternion import quat_apply

from .teacher_bridge_pull_env import TeacherBridgePullEnv

from .matched_pull_60hz import TensorGraspKinematics

from .settings import CACHE

from .bridge_pull_path import PullPath

from .bridge_pull_risk import directional_risk


class TeacherBridgePullRiskEnv(TeacherBridgePullEnv):

    def __init__(self,*args,path_spec,**kwargs):
        super().__init__(*args,**kwargs)
        self.path=PullPath(self.num_envs,self.device,path_spec)
        self.path_kin=TensorGraspKinematics(self.kinematics_path,self.settings.diameter,device=self.device)
        self.risk_latched=torch.zeros_like(self.pull_active)
        self.path_diagnostics={}

    def _pre_physics_step(self,proposed):
        previous=self.targets.clone()
        super()._pre_physics_step(proposed)
        qualified=torch.zeros_like(self.pull_active)
        if hasattr(self,'raw_grip') and hasattr(self,'slip'):
            qualified=self.grip & self.raw_grip & (self.slip<self.settings.max_slip)
        fruit=self._target_fruit().data
        tip=fruit.root_link_pos_w+quat_apply(fruit.root_link_quat_w,self.fruit_tips[self.target_index])
        risk=directional_risk(tip-self._t(self.anchors),self.settings.tension_axis,
            self.pull_active,self._t(self.attached),qualified,self.release_intent,self.path.spec)
        first=risk & ~self.risk_latched
        self.risk_latched |= risk
        p,r,j=self.path_kin.pose_and_jacobian(self.robot.data.joint_pos[:,self.jids])
        error=(p-(self._tcp()[0]-self.scene.env_origins)).norm(dim=-1)
        if (error>.002).any():raise ValueError('Cached FK differs from actual TCP by over2mm')
        command=self.actions.clone()
        command[:,:5]=(self.targets[:,:5]-previous[:,:5])/(self.settings.action_speed*self.step_dt)
        # Restart only the adapter speed ramp when intervention begins; never the
        # policy clock, physics, jaw origin/budget or contact/retention histories.
        elapsed=self._target_elapsed_steps()*self.step_dt
        if not hasattr(self,'risk_start_s'):self.risk_start_s=torch.zeros_like(elapsed)
        self.risk_start_s[first]=elapsed[first]
        ramp=.2+.8*((elapsed-self.risk_start_s)/.5).clamp(0.,1.)
        result,diag=self.path.step(command,p,r,j,active=self.pull_active & self.risk_latched,
            attached=self._t(self.attached),qualified=qualified,valid_detach=self.valid_detach,
            release=self.release_intent,axis=self.settings.tension_axis,ramp=ramp,
            action_speed=self.settings.action_speed,dt=self.step_dt)
        scope=diag['path_active'] | diag['path_hold']
        self.targets[scope,:5]=(previous[:,:5]+result[:,:5]*self.settings.action_speed*self.step_dt)[scope].clamp(self.lower[:5],self.upper[:5])
        self.actions[scope,:5]=result[scope,:5]
        diag.update(path_fk_error_m=error,risk_active=self.risk_latched.clone(),risk_first=first)
        self.path_diagnostics=diag
