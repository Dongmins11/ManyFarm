"""Isaac plant of the frozen Teacher60, with a Student-only command boundary.

Import after AppLauncher. Inherited scene/reset methods preserve original assets,
drives, fingers, floor and domain. Teacher controllers/reward functions are never
executed. Their physical grasp/bridge/retention/stop predicates are reused solely
as an evaluator; release must additionally come from an actual Student command.
"""
import torch
from isaaclab.utils.math import quat_apply
from .student60_eval_adapter import Student60CommandBoundary, forbidden_teacher,reset_student_servo,student_release_begin
from .teacher_friction_progress_env import TeacherFrictionProgressEnv
from .teacher_bridge_transport_env import TeacherBridgeTransportEnv
from .env import HarvestEnv
from .student60_response6_boundary import apply_response6_plant
from .logic import mesh_settled_in_box, release_intent_step, fruit_bounds
from .deposit_60hz import deposit_dwell
from .transport_progress_budget import extension_eligible


class Student60EvalEnv(Student60CommandBoundary, TeacherFrictionProgressEnv):
    def original_plant_action(self):
        # Resolve the adapter after response6_runtime has entered. Caching the
        # pre-context function silently evaluates a different stem model.
        apply_response6_plant(self, HarvestEnv)

    def __init__(self, *args, camera_kin, camera_config, camera_frame, **kwargs):
        self.camera_kin=camera_kin; self.camera_config=camera_config; self.camera_frame=camera_frame
        super().__init__(*args, grasp_policy=forbidden_teacher, transport_policy=forbidden_teacher, **kwargs)
        self.pending_student_command=None
        self.control_checks=0; self.physics_control_checks=0
        self.student_initial_gain=self.original_jaw_stiffness.clone()
        self.student_initial_limit=self.followup_default_limit.clone()

    def _setup_scene(self):
        super()._setup_scene()
        from .d435_rig import DualD435Rig
        self.student_rig=DualD435Rig(self.camera_kin,self.camera_config,self.camera_frame)

    def _record_assessment_inputs(self):
        self.student_opening_begin=student_release_begin(self.actions[:,-1]>0.,self.deposit_before,
            self.release_armed,self.grip,self.release_intent,self.valid_release)
        self.release_intent |= self.student_opening_begin
        self.release_intent_age[self.student_opening_begin]=0.
        self.student_opened=getattr(self,'student_opened',torch.zeros_like(self.success)) | self.student_opening_begin
        # The original bounded progress extension observes the pre-physics goal.
        fruit=self._target_fruit().data
        center,extent=fruit_bounds(fruit.root_link_pos_w-self.scene.env_origins,fruit.root_link_quat_w,self.settings)
        goal=center.clone();goal[:,:2]=center.new_tensor([self.settings.box_min[:2],self.settings.box_max[:2]]).mean(0)
        goal[:,2]=self.settings.box_max[2]+extent[:,2]+.035
        error=(goal-center).norm(dim=-1)
        self.transport_path_diagnostics={'transport_goal_error_m':error}
        index=self.progress_history_step%61;past=self.progress_history[(self.progress_history_step-60)%61]
        self.progress_3s=past-error
        self.progress_history[index]=torch.where(self.transport_before,error,float('nan'))
        self.progress_history_step+=1

    def _update_task(self):
        # No pre-step/Teacher actor/IK/path/servo methods are in this call graph.
        # Includes the original 0.25s contact, 2s bridge, valid break, 0.5s retained
        # and 0.3s physical stop plus all original collision/drop/stray failures.
        TeacherBridgeTransportEnv._update_task(self)
        stopped=self.success & ~self.deposit_active & ~self.failure
        self.deposit_start_step[stopped]=self.episode_length_buf[stopped]
        self.deposit_arm_targets[stopped]=self.targets[stopped,:5]
        self.deposit_start_arm_q[stopped]=self.robot.data.joint_pos[stopped][:,self.jids[:5]]
        tcp,_=self._tcp()
        self.deposit_start_tcp[stopped]=tcp[stopped]
        self.deposit_active |= stopped
        self.release_armed |= stopped
        # Original Teacher sets intent at handoff because it then opens itself.
        # Here stop does not supply a missing Student opening action.
        begin=self.student_opening_begin
        fruit=self._target_fruit().data
        local=fruit.root_link_pos_w-self.scene.env_origins
        inside=torch.zeros_like(self.success)
        for i,vertices in enumerate(self.fruit_collision_hulls):
            inside |= (self.target_index==i) & mesh_settled_in_box(local,
                fruit.root_link_quat_w,fruit.root_com_lin_vel_w,vertices,self.settings)
        d=self.last_diagnostics
        clear=(~self.raw_grip & (d['fixed_force_N']<self.settings.contact_threshold)
               & (d['moving_force_N']<self.settings.contact_threshold))
        hold,eligible=deposit_dwell(self.deposit_hold_time,inside,clear,self._t(self.attached),
            self.has_retained,self.valid_detach,self.failure,self.step_dt)
        self.deposit_hold_time[self.deposit_before]=hold[self.deposit_before]
        hand_still=((tcp-self.deposit_start_tcp).norm(dim=-1)<=.01) & (
            (self.robot.data.joint_pos[:,self.jids[:5]]-self.deposit_start_arm_q).abs().amax(-1)<=.03)
        hand_still &= (tcp-self.previous_tcp).norm(dim=-1)/self.step_dt<=self.settings.release_speed
        lost=self.previous_raw_grip & ~self.raw_grip & ~self.valid_release
        intent,age,approved=release_intent_step(self.release_intent,self.release_intent_age,
            lost,self.actions[:,-1],hand_still,self.step_dt)
        self.release_intent[self.deposit_before]=intent[self.deposit_before]
        self.release_intent_age[self.deposit_before]=age[self.deposit_before]
        self.valid_release |= approved & self.deposit_before
        self.bad_release |= lost & ~approved & self.deposit_before
        self.success=(self.deposit_before & eligible & self.student_opened
            & (self.deposit_hold_time>=self.settings.place_hold_s) & ~self.failure
            & self.valid_release & ~self.bad_release)
        d.update(success=self.success.clone(),failure=self.failure.clone(),
            deposit_handoff=stopped,deposit_active=self.deposit_active.clone(),
            deposit_mesh_inside=inside,deposit_both_jaws_clear=clear,deposit_eligible=eligible,
            deposit_hold_s=self.deposit_hold_time.clone(),deposit_hand_still=hand_still,
            student_opening_intent=begin,student_opened=self.student_opened.clone(),
            valid_release=self.valid_release.clone(),release_quality_violation=self.bad_release.clone())
        self._verify_student_command()

    def _get_dones(self):
        self._update_task()
        timed_out=self._target_elapsed_steps()>=self.max_episode_length-1
        qualified=self.grip & self.raw_grip & (self.slip<self.settings.max_slip)
        scope=self.transport_before & ~self.deposit_active & ~self.release_intent
        d=self.last_diagnostics
        first=extension_eligible(timed_out,scope,self.failure,qualified,self.has_retained,
            self.valid_detach,self._t(self.attached),self.transport_path_diagnostics['transport_goal_error_m'],
            self.progress_3s,torch.minimum(d['fixed_force_N'],d['moving_force_N']),self.progress_extension>0)
        self.progress_extension[first]=6.
        elapsed=(self.episode_length_buf-self.transport_start_step)*self.step_dt
        permitted=scope & qualified & (self.progress_extension>0) & ~self.failure
        timed_out=torch.where(permitted,elapsed>=self.settings.episode_s+self.progress_extension-self.step_dt,timed_out)
        timed_out=torch.where(self.deposit_active,
            (self.episode_length_buf-self.deposit_start_step)*self.step_dt>=self.deposit_timeout_s-self.step_dt,timed_out)
        return self.success | self.failure,timed_out

    def _get_rewards(self):
        d=self.last_diagnostics
        d.update(progress_extension_s=self.progress_extension.clone(),
            progress_3s_m=torch.nan_to_num(self.progress_3s),slip_m=self.slip.clone(),
            qualified_grasp=self.grip.clone(),chain_bridge_confirmed=self.bridge_started.clone(),
            chain_bridge_hold_s=self.bridge_hold_time.clone(),chain_pull_active=self.pull_active.clone())
        self.chain_snapshot={k:v.clone() for k,v in d.items()}
        self.extras['log']={}
        return torch.zeros(self.num_envs,device=self.device)

    def _reset_impl(self,ids):
        if hasattr(self,'student_rig'): self.student_rig.active=False
        if hasattr(self,'student_initial_gain'):
            selected=self.robot._ALL_INDICES if ids is None else ids
            reset_student_servo(self,selected,self.student_initial_gain,self.student_initial_limit)
        super()._reset_impl(ids)
        if hasattr(self,'student_opened'):
            selected=self.robot._ALL_INDICES if ids is None else ids
            self.student_opened[selected]=False
