"""Frozen HOME actor followed by learned pull in the same physical scene."""
import math
import torch
from isaaclab.utils.math import quat_apply
from .teacher_grasp_bridge_env import TeacherGraspBridgeEnv
from .teacher_load_reserve_env import TeacherLoadReserveEnv
from .env import HarvestEnv
from .grasp_bridge_60hz import bridge_step
from .pull_refine_60hz import PullRefinement,prepare_actions
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

    def _get_rewards(self):
        # Update the parent's read-only contact geometry/episode diagnostics.
        TeacherLoadReserveEnv._get_rewards(self)
        if not hasattr(self,'pull_active'):return torch.zeros(self.num_envs,device=self.device)
        task,version=self.settings.task,self.settings.reward_version
        try:
            self.settings.task='pull';self.settings.reward_version=6
            reward=HarvestEnv._get_rewards(self)
        finally:self.settings.task=task;self.settings.reward_version=version
        fruit=self._target_fruit().data;tcp,tcp_quat=self._tcp()
        tip=fruit.root_link_pos_w+quat_apply(fruit.root_link_quat_w,self.fruit_tips[self.target_index])
        arm_vectors=self.arm_contact.data.net_forces_w
        arm_forces=arm_vectors.norm(dim=-1);arm_max=arm_forces.amax(-1)
        elapsed=self._target_elapsed_steps()*self.step_dt
        terminal=self.success | self.failure | (self._target_elapsed_steps()>=self.max_episode_length-1)
        d=self.last_diagnostics
        extra,diag=self.pull_reward.step(active=self.policy_active_before,attached=self._t(self.attached),
            qualified=self.grip & self.raw_grip & (self.slip<self.settings.max_slip),
            force_fixed=d['fixed_force_N'],force_moving=d['moving_force_N'],
            displacement=tip-self._t(self.anchors),axis=self.settings.tension_axis,
            quat=fruit.root_link_quat_w,elapsed=elapsed,arm_force=arm_max,terminal=terminal,dt=self.step_dt)
        self.early_contact_lost |= (self.policy_active_before & (elapsed<3.) &
            ~(self.grip & self.raw_grip & (self.slip<self.settings.max_slip)))
        result=torch.where(self.policy_active_before,reward+extra,0.)
        d.update(qualified_grasp=self.grip.clone(),slip_m=self.slip.clone(),
            jaw_origin_rad=self.bridge_preload.origin.clone(),jaw_target_rad=self.targets[:,-1].clone(),
            jaw_total_close_deg=(self.bridge_preload.origin-self.targets[:,-1])*180/math.pi,
            jaw_latched=self.bridge_preload.latched.clone(),arm_ramp_scale=self.chain_scale.clone(),
            phase_elapsed_s=elapsed,arm_max_force_N=arm_max,ppo_active=self.policy_active_before.clone(),
            pull_refine_reward=extra.clone(),effective_reward=result.clone())
        for key,value in diag.items():d['bridge_pull_'+key]=value.clone()
        q=self.robot.data.joint_pos[:,self.jids]
        for j in range(5):
            d[f'arm_command_{j}']=self.actions[:,j].clone()
            d[f'arm_q_{j}_rad']=q[:,j].clone();d[f'arm_target_{j}_rad']=self.targets[:,j].clone()
        for j,axis in enumerate('xyz'):
            d[f'tcp_{axis}_m']=(tcp-self.scene.env_origins)[:,j].clone()
            d[f'fruit_{axis}_m']=(fruit.root_link_pos_w-self.scene.env_origins)[:,j].clone()
        for j in range(4):
            d[f'tcp_quat_{j}']=tcp_quat[:,j].clone();d[f'fruit_quat_{j}']=fruit.root_link_quat_w[:,j].clone()
        for j in range(arm_forces.shape[1]):d[f'arm_body_{j}_force_N']=arm_forces[:,j].clone()
        self.chain_snapshot={k:v.clone() for k,v in d.items()}
        if self.diagnostic_contacts:
            from .contact_points_60hz import capture_contact_points
            self.chain_contacts=capture_contact_points(self,self.margin_views)
        self._capture_handoff(d['chain_handoff'])
        self.extras['log'].update({'Chain/'+k:torch.tensor(float(v),device=self.device) for k,v in self.chain_totals.items()})
        for key,value in diag.items():self.extras['log']['BridgePull/'+key]=value[self.policy_active_before].float().mean() if self.policy_active_before.any() else value.new_tensor(0.)
        if not torch.isfinite(result).all():raise FloatingPointError('Nonfinite pull reward')
        return result

    def _capture_handoff(self,mask):
        remaining=self.handoff_limit-len(self.handoff_records)
        if remaining<=0:return
        for i in mask.nonzero().flatten()[:remaining].cpu().tolist():
            self.handoff_records.append(dict(env_id=i,domain_sample=self.domain_samples[i].detach().cpu(),
                q=self.robot.data.joint_pos[i].detach().cpu().clone(),
                qd=self.robot.data.joint_vel[i].detach().cpu().clone(),targets=self.targets[i].detach().cpu().clone(),
                fruits=torch.stack([f.data.root_state_w[i] for f in self.fruits]).detach().cpu().clone(),
                anchors=self.anchors[i].detach().cpu().clone(),target_index=int(self.target_index[i]),
                threshold=self.threshold[i].detach().cpu().clone(),
                jaw_origin=float(self.bridge_preload.origin[i]),jaw_latched=bool(self.bridge_preload.latched[i]),
                stored_arm_targets=self.bridge_arm_targets[i].detach().cpu().clone(),
                post_confirmation_hold_s=float(self.bridge_hold_time[i]),
                qualified=bool(self.grip[i]&self.raw_grip[i]),split=self.domain_split_name))

    def _reset_impl(self,ids):
        if hasattr(self,'pull_active'):
            selected=self.robot._ALL_INDICES if ids is None else ids
            finished=selected[(self.episode_length_buf[selected]>0)&
                (self.success|self.failure|self.reset_time_outs)[selected]]
            for i in finished.cpu().tolist():
                sample=self.domain_samples[i].cpu().tolist()
                d={k:float(v[i]) for k,v in self.chain_snapshot.items()}
                row=dict(env_id=i,confirmed=bool(self.bridge_started[i]),handoff=bool(self.pull_active[i]),
                    success=bool(self.success[i]),failure=bool(self.failure[i]),
                    timeout=bool(self.reset_time_outs[i]),early_contact_loss=bool(self.early_contact_lost[i]),sample=sample,
                    reasons=[k for k,v in d.items() if k.startswith('failure_') and v],terminal=d)
                self.chain_episode_records.append(row)
                self.chain_history.append(row);self.chain_history=self.chain_history[-4096:]
                self.chain_totals['episodes']+=1;self.chain_totals['confirmed']+=row['confirmed']
                self.chain_totals['handoffs']+=row['handoff'];self.chain_totals['success']+=row['success']
                self.chain_totals['early_contact_loss']+=row['early_contact_loss']
            # Keep memory bounded while retaining complete logs in preparation.
            self.chain_episode_records=self.chain_episode_records[-4096:]
        TeacherLoadReserveEnv._reset_impl(self,ids)
        if hasattr(self,'bridge_started'):
            selected=self.robot._ALL_INDICES if ids is None else ids
            self.bridge_serial[selected]+=1;self.bridge_started[selected]=False
            self.bridge_hold_time[selected]=0.;self.bridge_preload.reset(selected)
        if hasattr(self,'pull_active'):
            self.pull_active[selected]=False;self.pull_start_step[selected]=0
            self.early_contact_lost[selected]=False
            self.pull_reward.reset(selected)
