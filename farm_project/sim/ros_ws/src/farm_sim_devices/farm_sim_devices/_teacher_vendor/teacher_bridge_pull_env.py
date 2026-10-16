"""60Hz r2 원본 계산에서 추출. 재생성: sim/tools/import_teacher60.py."""

import torch

from .teacher_grasp_bridge_env import TeacherGraspBridgeEnv

from .teacher_load_reserve_env import TeacherLoadReserveEnv

from .grasp_bridge_60hz import bridge_step

from .pull_refine_60hz import PullRefinement, prepare_actions

from .bridge_pull_training import BridgePullReward


class TeacherBridgePullEnv(TeacherGraspBridgeEnv):

    def __init__(self,*args,grasp_policy,**kwargs):
        super().__init__(*args,**kwargs)
        self.grasp_policy=grasp_policy
        self.domain_split_name=kwargs['domain_split']
        self.pull_active=torch.zeros_like(self.has_grasped)
        self.pull_start_step=torch.zeros_like(self.episode_length_buf)
        self.policy_active_before=self.pull_active.clone()
        self.early_contact_lost=torch.zeros_like(self.has_grasped)
        self.refinement=PullRefinement(.5,.2,False)
        self.pull_reward=BridgePullReward(self.num_envs,self.device)
        self.chain_episode_records=[]
        self.chain_totals=dict(episodes=0,confirmed=0,handoffs=0,success=0,early_contact_loss=0)
        self.chain_history=[]
        self.handoff_records=[];self.handoff_limit=128
        self.diagnostic_contacts=False

    def _target_elapsed_steps(self):
        result=super()._target_elapsed_steps()
        if hasattr(self,'pull_active'):
            result=torch.where(self.pull_active,self.episode_length_buf-self.pull_start_step+40,result)
        return result

    def _pre_physics_step(self,proposed):
        self.policy_active_before=self.pull_active.clone()
        with torch.no_grad():grasp=self.grasp_policy(self._get_observations())
        proposed=torch.where(self.pull_active[:,None],proposed,grasp)
        previous=self.targets.clone()
        commands,scale,_=prepare_actions(proposed,self._target_elapsed_steps()*self.step_dt,
            self.has_grasped,self.release_intent,self._t(self.attached),self.valid_detach,self.refinement)
        commands=torch.where(self.pull_active[:,None],commands,proposed)
        self.chain_scale=torch.where(self.pull_active,scale,0.)
        self.entry_grasp_active=~self.pull_active
        TeacherLoadReserveEnv._pre_physics_step(self,commands)
        holding=self.bridge_started & ~self.pull_active & ~self.release_intent
        self.actions[holding]=0.;self.targets[holding,:5]=self.bridge_arm_targets[holding]
        target,_=self.bridge_preload.step(previous[:,-1],self.targets[:,-1],
            self.robot.data.joint_pos[:,self.jids[-1]],self.actions[:,-1],
            self.bridge_started & ~self.release_intent,speed=self.settings.gripper_speed,
            dt=self.step_dt,max_error=self.settings.gripper_max_error,lower=self.lower[-1],upper=self.upper[-1])
        self.targets[:,-1]=target

    def _update_task(self):
        task=self.settings.task
        try:
            self.settings.task='pull';TeacherLoadReserveEnv._update_task(self)
        finally:self.settings.task=task
        if not hasattr(self,'pull_active'):return
        original_failure=self.failure.clone();original_success=self.success.clone()
        pending=~self.pull_active
        qualified=self.grip & self.raw_grip & (self.slip<self.settings.max_slip)
        confirmed=(self.grip_time>=self.settings.grip_hold_s)&self._t(self.attached)
        started,hold,passed,lost,first=bridge_step(self.bridge_started,self.bridge_hold_time,
            confirmed,qualified,self._t(self.attached),original_failure,self.step_dt)
        self.bridge_started=torch.where(pending,started,self.bridge_started)
        self.bridge_hold_time=torch.where(pending,hold,self.bridge_hold_time)
        first &= pending;self.bridge_arm_targets[first]=self.targets[first,:5]
        handoff=pending & passed
        self.pull_start_step[handoff]=self.episode_length_buf[handoff]
        self.pull_reward.handoff(handoff,self._target_fruit().data.root_link_quat_w)
        self.pull_active |= handoff
        self.failure=original_failure | (pending & lost)
        self.success=self.policy_active_before & original_success & ~self.failure
        self.last_diagnostics.update(chain_handoff=handoff,chain_pull_active=self.pull_active.clone(),
            chain_bridge_confirmed=self.bridge_started.clone(),chain_bridge_hold_s=self.bridge_hold_time.clone(),
            chain_bridge_loss=pending & lost,chain_original_failure=original_failure,
            success=self.success.clone(),failure=self.failure.clone())
