"""Train approach contacts that survive a small real arm movement, no PPO here."""
import torch
from .teacher_grasp_bridge_env import TeacherGraspBridgeEnv
from .dynamic_grasp_60hz import SPEC,dynamic_step
from .bridge_pull_path import PullPath,PullPathSpec
from .matched_pull_60hz import TensorGraspKinematics
from .settings import CACHE


class TeacherDynamicGraspEnv(TeacherGraspBridgeEnv):
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.motion_started=torch.zeros_like(self.has_grasped)
        self.motion_moved=torch.zeros_like(self.has_grasped)
        self.motion_hold=torch.zeros(self.num_envs,device=self.device)
        self.motion_start_step=torch.zeros_like(self.episode_length_buf)
        self.motion_origin=torch.zeros(self.num_envs,3,device=self.device)
        self.motion_hold_targets=self.targets[:,:5].clone()
        self.motion_best=torch.zeros(self.num_envs,device=self.device)
        self.motion_kin=TensorGraspKinematics(CACHE/'harvest_training.urdf',self.settings.diameter,device=self.device)
        self.motion_path=PullPath(self.num_envs,self.device,PullPathSpec(speed_m_s=SPEC['command_speed_m_s'],
            travel_m=SPEC['command_travel_m'],joint_speed_rad_s=.04,orientation_length_m=.08))
        self.motion_records=[]

    def _pre_physics_step(self,proposed):
        previous=self.targets[:,:5].clone()
        super()._pre_physics_step(proposed)
        if not self.motion_started.any():return
        p,r,j=self.motion_kin.pose_and_jacobian(self.robot.data.joint_pos[:,self.jids])
        qualified=self.grip & self.raw_grip & (self.slip<self.settings.max_slip)
        scope=self.motion_started & ~self.motion_moved & ~self.failure & ~self.release_intent
        result,diag=self.motion_path.step(self.actions,p,r,j,active=scope,
            attached=self._t(self.attached),qualified=qualified,valid_detach=self.valid_detach,
            release=self.release_intent,axis=self.settings.tension_axis,
            ramp=torch.ones(self.num_envs,device=self.device),action_speed=self.settings.action_speed,dt=self.step_dt)
        self.targets[scope,:5]=(previous+result[:,:5]*self.settings.action_speed*self.step_dt)[scope].clamp(self.lower[:5],self.upper[:5])
        self.actions[scope,:5]=result[scope,:5]
        hold=self.motion_started & self.motion_moved & ~self.release_intent
        self.targets[hold,:5]=self.motion_hold_targets[hold];self.actions[hold,:5]=0.
        self.motion_command_diag=diag

    def _update_task(self):
        super()._update_task()
        if not hasattr(self,'motion_started'):return
        original_success=self.success.clone()
        p,r,j=self.motion_kin.pose_and_jacobian(self.robot.data.joint_pos[:,self.jids])
        error=(p-(self._tcp()[0]-self.scene.env_origins)).norm(dim=-1)
        if (error>.002).any():raise ValueError('Dynamic grasp FK differs from actual TCP')
        axis=p.new_tensor(self.settings.tension_axis);axis=axis/axis.norm()
        delta=p-self.motion_origin;axial=(delta*axis).sum(-1)
        lateral=(delta-axial[:,None]*axis).norm(dim=-1)
        qualified=self.grip & self.raw_grip & (self.slip<self.settings.max_slip)
        elapsed=(self.episode_length_buf-self.motion_start_step)*self.step_dt
        started,moved,hold,success,failed,first,new_moved=dynamic_step(self.motion_started,
            self.motion_moved,self.motion_hold,bridge_passed=original_success,
            qualified=qualified,attached=self._t(self.attached),failed=self.failure,
            axial=axial,lateral=lateral,elapsed=elapsed,dt=self.step_dt)
        self.motion_origin[first]=p[first];self.motion_start_step[first]=self.episode_length_buf[first]
        self.motion_hold_targets[new_moved]=self.targets[new_moved,:5]
        self.motion_started,self.motion_moved,self.motion_hold=started,moved,hold
        self.success=success & ~self.failure;self.failure|=failed
        axial=torch.where(first,0.,axial);lateral=torch.where(first,0.,lateral)
        self.last_diagnostics.update(dynamic_started=started.clone(),dynamic_first=first,
            dynamic_moved=moved.clone(),dynamic_axial_m=axial,dynamic_lateral_m=lateral,
            dynamic_hold_s=hold.clone(),dynamic_elapsed_s=torch.where(started & ~first,elapsed,0.),
            failure_dynamic_contact_or_motion=failed,dynamic_original_bridge_passed=original_success,
            dynamic_fk_error_m=error,success=self.success.clone(),failure=self.failure.clone())

    def _get_rewards(self):
        reward=super()._get_rewards()
        if not hasattr(self,'motion_started'):return reward
        d=self.last_diagnostics
        scope=self.motion_started & ~self.failure
        progress=(d['dynamic_axial_m']/SPEC['required_actual_axial_m']).clamp(0,1)*scope
        gain=(progress-self.motion_best).clamp_min(0);self.motion_best=self.motion_best.maximum(progress)
        extra=SPEC['progress_budget']*gain+SPEC['success_bonus']*self.success+SPEC['hold_reward_per_s']*self.step_dt*scope
        self.extras['log'].update({'DynamicGrasp/'+k:v.float().mean() for k,v in dict(
            started=self.motion_started,moved=self.motion_moved,hold_s=self.motion_hold,
            passed=self.success,objective_failure=d['failure_dynamic_contact_or_motion'],extra_reward=extra).items()})
        if hasattr(self,'motion_command_diag'):d.update({'dynamic_command_'+k:v for k,v in self.motion_command_diag.items()})
        stream=getattr(self,'dynamic_trace_stream',None)
        if stream is not None:
            import json
            columns=[k for k in sorted(d) if k.startswith(('dynamic_','failure_dynamic'))]+['success','failure','attached','fixed_force_N','moving_force_N','distance_m']
            columns=[k for k in columns if k in d]
            values=torch.stack([d[k].float() for k in columns],-1).cpu().tolist()
            stream.write(json.dumps(dict(episode_serial=self.bridge_serial.cpu().tolist(),
                episode_step=self.episode_length_buf.cpu().tolist(),columns=columns,rows=values))+'\n')
        return reward+extra

    def _reset_impl(self,ids):
        if hasattr(self,'motion_started'):
            selected=self.robot._ALL_INDICES if ids is None else ids
            finished=selected[(self.episode_length_buf[selected]>0)&(self.success|self.failure|self.reset_time_outs)[selected]]
            if getattr(self,'domain_evaluation',False):
                for i in finished.cpu().tolist():
                    d=self.last_diagnostics
                    self.motion_records.append(dict(env_id=i,success=bool(self.success[i]),
                        started=bool(self.motion_started[i]),moved=bool(self.motion_moved[i]),hold_s=float(self.motion_hold[i]),
                        axial_m=float(d['dynamic_axial_m'][i]),lateral_m=float(d['dynamic_lateral_m'][i]),
                        failure=bool(self.failure[i]),sample=self.domain_samples[i].cpu().tolist()))
        super()._reset_impl(ids)
        if hasattr(self,'motion_started'):
            self.motion_started[selected]=False;self.motion_moved[selected]=False;self.motion_hold[selected]=0.
            self.motion_best[selected]=0.;self.motion_start_step[selected]=0;self.motion_path.reset(selected)
            if hasattr(self,'motion_command_diag'):
                for v in self.motion_command_diag.values():v[selected]=0
