"""Single persistent Isaac scene, with per-target Student outcome assessment.

Only this new subclass disables automatic episode reset. Fruit physics,
attachments and deposited fruit remain in the same scene during all motions.
Simulator truth is confined to outcome/obstacle supervision, never policy input.
"""
import torch
from .student60_box_outcome_env import BoxOutcomeCameraStudentEnv


class StudentMissionEnv(BoxOutcomeCameraStudentEnv):
    def __init__(self, *args, camera_kind='d435', frozen_urdf=None, **kwargs):
        self.camera_kind = camera_kind; self.frozen_urdf = frozen_urdf
        self.mission_active = False; self.assessing = False; self.physical_resets = 0
        super().__init__(*args, **kwargs)

    def _setup_scene(self):
        if self.camera_kind == 'd435': return super()._setup_scene()
        # Same plant setup, only the explicitly different camera rig changes.
        from .student60_eval_env import Student60EvalEnv
        super(Student60EvalEnv, self)._setup_scene()
        from harvest_sensors.u20_deployment_rig import U20DeploymentRig
        self.student_rig = U20DeploymentRig(self.camera_kin, self.camera_config,
                                          self.camera_frame, frozen_urdf=self.frozen_urdf)

    def _reset_idx(self, ids):
        if self.mission_active and len(ids):
            raise RuntimeError('Physical reset forbidden during a multi-fruit mission')
        self.physical_resets += int(bool(len(ids)))
        return super()._reset_idx(ids)

    def author_multifruit_scene(self, minimum_separation_m=.12):
        """Initial scene construction only, never a between-target reset.

        The old domain deliberately parked the second colour outside the work
        area. Keep its assets/dynamics but place both fruits in the held-out
        reachable bank, with independently sampled domain orientations.
        """
        if self.mission_active: raise RuntimeError('Cannot author fruit during mission')
        from .teacher_domain import sample_pose, reset_geometry
        pool = self.domain_pools[self.domain_stage]
        points = self.points[pool]
        first = int(torch.randint(len(pool), (1,), generator=self.domain_rng, device=self.device)[0])
        distances = (points-points[first]).norm(dim=-1)
        choices = (distances >= minimum_separation_m).nonzero().flatten()
        if not len(choices): raise RuntimeError('No separated two-fruit scene in held-out bank')
        second = int(choices[torch.randint(len(choices),(1,),generator=self.domain_rng,device=self.device)][0])
        rows=[]
        for slot, choice in enumerate([first,second]):
            quat, tilt, yaw = sample_pose(1,self.domain,self.domain_stage,self.domain_rng,self.device)
            offset=self.points.new_tensor([0.,0.,-self.settings.length*.08])
            root,anchor=reset_geometry(points[choice:choice+1],quat,offset,self.fruit_tips[slot])
            fruit=self.fruits[slot];state=fruit.data.default_root_state.clone()
            state[:,:3]=root+self.scene.env_origins;state[:,3:7]=quat;state[:,7:]=0
            fruit.write_root_state_to_sim(state);fruit.reset()
            self.anchors[:,slot]=anchor+self.scene.env_origins;self.rest_quat[:,slot]=quat
            rows.append(dict(slot=slot,bank_id=int(self.domain_bank_ids[pool[choice]]),
                root_world_m=state[0,:3].cpu().tolist(),tilt_deg=float(tilt[0]*180/torch.pi),yaw_deg=float(yaw[0]*180/torch.pi)))
        self.ripe[:]=True
        self._draw_stems()
        return rows

    def begin_target_assessment(self, slot):
        """Reset evaluator memory only; never robot, fruit or attachment state."""
        if self.assessing or not 0 <= slot < len(self.fruits) or bool(self.collected[0, slot]) or not bool(self.attached[0, slot]):
            raise ValueError('Invalid pending target assessment')
        self.target_index[0] = slot
        names = '''entry_inside transport_started transport_origin transport_potential
            pending_detach_age pending_detach_lost pending_detach pending_detach_time
            pending_detach_relative pending_detach_rejected grip_time place_time loaded_time
            detached_time grasp_relative slip pull_start_x pull_best_retreat pull_recovery_potential
            stop_time stop_best_time place_best_time release_target_unloaded release_intent
            release_intent_age release_intent_tcp release_intent_arm release_armed valid_release
            bad_release release_paid has_grasped transport_preload_latched transport_preload_origin
            squeeze_active valid_detach has_retained grip raw_grip grasp_event detach_event success
            failure collection_event pending_next bridge_started bridge_hold_time pull_active
            early_contact_lost transport_active transport_before deposit_active deposit_before
            deposit_first_command deposit_hold_time outcome_hold box_outcome_hold student_opened
            progress_extension progress_3s progress_first actions previous_actions'''.split()
        for name in names:
            value = getattr(self, name, None)
            if value is not None: value.zero_()
        self.place_best_distance.fill_(float('inf'))
        self.progress_history.fill_(float('nan')); self.progress_history_step = 0
        self.target_start_step[:] = self.episode_length_buf
        self.mission_target_start = int(self.episode_length_buf[0])
        self.assessing = True; self.assignment_status = 'RUNNING'

    def commit_box_success(self):
        if not self.assessing or not bool(self.success[0]): raise ValueError('No actual settled-box success')
        self.collected[0, self.target_index[0]] = True
        self.assessing = False; self.assignment_status = 'SUCCEEDED'

    def supervisor_fault(self):
        from harvest_runtime.deposit_guard import still_in_box
        if not torch.isfinite(self.robot.data.joint_pos).all(): return 'nonfinite_joint'
        sensors = (self.arm_contact, self.fixed_contact, self.moving_contact)
        if not all(torch.isfinite(s.data.net_forces_w).all() for s in sensors): return 'nonfinite_contact'
        if float(self.arm_contact.data.net_forces_w.norm(dim=-1).max()) > 12.: return 'arm_collision'
        # Fingers must be clear during stow/HOME/return; force threshold is not
        # used to synthesize a hardware force measurement.
        if not self.assessing and max(float(s.data.net_forces_w.norm(dim=-1).max()) for s in sensors[1:]) > 2.:
            return 'motion_finger_collision'
        for i, fruit in enumerate(self.fruits):
            if not torch.isfinite(fruit.data.root_link_pos_w).all(): return 'nonfinite_fruit'
            if bool(self.collected[0, i]):
                if not still_in_box(fruit, self): return 'deposited_fruit_left_box'
            elif (not self.assessing or i != int(self.target_index[0])) and not bool(self.attached[0, i]):
                return 'unassigned_fruit_detached'
        if self.assessing and bool(self.failure[0]): return 'harvest_safety_failure'
        return ''

    def _get_dones(self):
        if self.assessing: self._update_task()
        # Caller consumes outcomes. No DirectRLEnv reset, including success.
        return torch.zeros_like(self.success), torch.zeros_like(self.success)

    def _get_rewards(self):
        if self.assessing: return super()._get_rewards()
        return torch.zeros(self.num_envs, device=self.device)
