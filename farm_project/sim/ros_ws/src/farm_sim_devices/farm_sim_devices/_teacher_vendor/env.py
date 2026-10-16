"""60Hz r2 원본 계산에서 추출. 재생성: sim/tools/import_teacher60.py."""

import torch

from .quaternion import quat_apply, quat_mul, quat_conjugate

from .sequence import forbidden_detach, target_elapsed

from .logic import mesh_settled_in_box, placement_outcome, rearm_confirmed_squeeze, pull_squeeze_error, placement_contained, horizontal_grasp_alignment, bilateral_contact, limited_joint_targets, dwell, stage_success, compliant_gripper_hold, grasp_diagnostics, qualified_grasp, placement_target, settled_in_box, above_box, controlled_release, update_pending_detach, recover_pending_detach


class HarvestEnv:

    def __init__(self, *args, **kwargs):
        self._initialize_sample(*args, **kwargs)

    def _native_recovery_enabled(self):
        return (self.settings.native_detach_recovery and self.settings.native_grasp_grace
                and self.settings.attachment_version == 3 and self.settings.task in ("pull", "harvest", "transport", "place"))

    def _grasp_center(self, fruit):
        if self.settings.grasp_version == 1:
            return fruit.data.root_link_pos_w
        # Body ellipsoid centre in assets.fruit_asset; excludes decorative stem.
        offset = torch.zeros_like(fruit.data.root_link_pos_w)
        offset[:,2] = -self.settings.length*.08
        return fruit.data.root_link_pos_w + quat_apply(fruit.data.root_link_quat_w, offset)

    def _grasp_orientation(self):
        _, quat = self._tcp()
        return horizontal_grasp_alignment(quat, self._target_fruit().data.root_link_quat_w,
                                          self.settings.grasp_angle_tolerance)

    def _pre_physics_step(self, actions):
        if self.settings.grasp_orientation == "horizontal":
            error, _ = self._grasp_orientation()
            tcp, _ = self._tcp()
            distance = (self._grasp_center(self._target_fruit())-tcp).norm(dim=-1)
            self.previous_orientation_potential = (self.settings.grasp_orientation_weight*(1-error.square())
                *torch.exp(-distance/.10)*(~self.has_grasped & self._t(self.attached)))
        if self.settings.target_mode == "external" and self.assignment_status != "RUNNING":
            raise RuntimeError("No running assignment; render while waiting, or assign_target/reset")
        if not torch.isfinite(actions).all():
            raise FloatingPointError("Non-finite policy command; stopping before applying it")
        tcp, _ = self._tcp()
        self.previous_distance = torch.linalg.vector_norm(self._grasp_center(self._target_fruit())-tcp, dim=-1)
        self.previous_tcp = tcp.clone()
        self.previous_fruit_com = self._target_fruit().data.root_com_pos_w.clone()
        self.previous_fruit_speed = self._target_fruit().data.root_com_lin_vel_w.norm(dim=-1).clone()
        self.previous_raw_grip = self.raw_grip.clone() if hasattr(self,"raw_grip") else torch.zeros(self.num_envs,dtype=torch.bool,device=self.device)
        self.previous_release_zone = above_box(self._target_fruit().data.root_link_pos_w-self.scene.env_origins,
            self._target_fruit().data.root_link_quat_w,self.settings)
        self.previous_fruit_quat = self._target_fruit().data.root_link_quat_w.clone()
        self.previous_gripper_q = self.robot.data.joint_pos[:,self.jids[-1]].clone()
        self.previous_actions.copy_(self.actions)
        self.actions.copy_(actions.clamp(-1, 1))
        if self.settings.release_intent_mode:
            begin = (~self.release_intent & self.release_armed & self.previous_release_zone
                     & (self.actions[:,-1] > 0.) & self.grip
                     & (self.previous_fruit_speed <= self.settings.release_speed)
                     & (self._target_fruit().data.root_com_ang_vel_w.norm(dim=-1)<1.))
            self.release_intent_tcp[begin] = tcp[begin]
            self.release_intent_arm[begin] = self.robot.data.joint_pos[begin][:,self.jids[:5]]
            self.release_intent_age[begin] = 0.
            self.release_intent |= begin
        speed = torch.tensor([self.settings.action_speed]*5 + [self.settings.gripper_speed], device=self.device)
        previous_gripper_target=self.targets[:,-1].clone()
        self.targets = limited_joint_targets(self.targets, self.robot.data.joint_pos[:,self.jids],
            self.actions, speed, self.step_dt, self.lower, self.upper, self.settings.gripper_max_error)
        # Position hold alone loses preload when the object settles/rotates.
        # Retain a bounded PD squeeze; an explicit opening action always overrides it.
        measured_gripper = self.robot.data.joint_pos[:,self.jids[-1]]
        squeeze_error=self.settings.gripper_hold_error
        from .logic import transport_stage_mask
        transport_scope=transport_stage_mask(self.settings.task,getattr(self,'expert_stage',None),self.has_grasped)
        expert_pull=(self.expert_stage==0) if hasattr(self,'expert_stage') else torch.zeros(self.num_envs,dtype=torch.bool,device=self.device)
        if self.settings.pull_squeeze_ramp and (self.settings.task=='pull' or hasattr(self,'expert_stage')):
            ramp=pull_squeeze_error(squeeze_error,self.grip_time,self.grip,self.has_grasped)
            squeeze_error=ramp if self.settings.task=='pull' else torch.where(expert_pull,ramp,squeeze_error)
        self.targets[:,-1], self.squeeze_active = compliant_gripper_hold(
            self.targets[:,-1], measured_gripper, self.actions[:,-1], self.squeeze_active,
            squeeze_error, self.lower[-1], self.upper[-1])
        if self.settings.detached_grip_hold:
            # Retain the established position target after separation. Never
            # follow every measured-angle fluctuation with a new closing target.
            from .logic import retain_detached_grip_target
            self.targets[:,-1]=retain_detached_grip_target(previous_gripper_target,self.targets[:,-1],
                ~self._t(self.attached) & ~expert_pull & ~(
                    transport_scope if getattr(self,"transport_adaptive_grip",self.settings.transport_adaptive_grip) else torch.zeros_like(expert_pull)),
                self.has_grasped,self.squeeze_active,self.actions[:,-1])
        self.capture_gripper_target_held=torch.zeros_like(self.has_grasped)
        self.transport_gripper_target_held=torch.zeros_like(self.has_grasped)
        if getattr(self,'capture_gripper_target_hold',False):
            from .logic import retain_confirming_grip_target, qualified_transport_hold_scope
            confirmation=getattr(self,'capture_settle_retention',torch.zeros_like(self.has_grasped))
            carrying=torch.zeros_like(self.has_grasped)
            if getattr(self,'transport_gripper_target_hold',False):
                carrying=qualified_transport_hold_scope(transport_scope,self._t(self.attached),
                    self.valid_detach,self.has_retained,self.grip,self.previous_raw_grip)
            self.targets[:,-1],held=retain_confirming_grip_target(
                previous_gripper_target,self.targets[:,-1],confirmation | carrying,
                self.has_grasped,self.squeeze_active,self.actions[:,-1],
                preload_start=carrying & getattr(self,'capture_transport_started',torch.zeros_like(carrying)),
                preload_step=getattr(self,'transport_gripper_preload_step',0.))
            self.targets[:,-1]=self.targets[:,-1].clamp(self.lower[-1],self.upper[-1])
            self.capture_gripper_target_held=held & confirmation
            self.transport_gripper_target_held=held & carrying
        self.transport_preload_adjusting=torch.zeros_like(self.has_grasped)
        if getattr(self,'transport_bounded_preload',False):
            from .logic import bounded_transport_preload
            context=transport_scope & ~self._t(self.attached) & self.valid_detach & self.has_retained & self.has_grasped
            self.targets[:,-1],self.transport_preload_origin,self.transport_preload_latched,self.transport_preload_adjusting=bounded_transport_preload(
                previous_gripper_target,self.targets[:,-1],measured_gripper,
                self.transport_preload_origin,self.transport_preload_latched,
                getattr(self,'capture_transport_started',torch.zeros_like(context)),context,
                self.grip & self.previous_raw_grip,self.squeeze_active,self.actions[:,-1],
                initial_step=getattr(self,'transport_gripper_preload_step',0.),
                error=self.transport_preload_error,max_close=self.transport_preload_max_close,
                rate=self.transport_preload_rate,dt=self.step_dt)
            self.targets[:,-1]=self.targets[:,-1].clamp(self.lower[-1],self.upper[-1])
        if self.settings.release_measured_open:
            from .release_control import unload_release_target
            self.targets[:,-1],self.release_target_unloaded=unload_release_target(
                self.targets[:,-1],measured_gripper,self.actions[:,-1],
                self.release_intent & self.valid_detach & self.has_retained,
                self.release_target_unloaded,self.settings.gripper_speed,self.step_dt,
                self.lower[-1],self.upper[-1])
        self.detach_event.zero_()
        self.grasp_event.zero_()

    def _update_task(self):
        if self.visual_updates:
            self._draw_stems()
        if not self.settings.native_grasp_grace:
            self._consume_joint_breaks()
        tcp, _ = self._tcp()
        fruit = self._target_fruit()
        self.distance = torch.linalg.vector_norm(self._grasp_center(fruit) - tcp, dim=-1)
        f = self._target_contact(self.fixed_contact)
        m = self._target_contact(self.moving_contact)
        self.raw_grip = bilateral_contact(f, m, self.distance, self.settings)
        self.grip = qualified_grasp(self.raw_grip, self.distance, self.settings)
        orientation_error, orientation_ok = self._grasp_orientation()
        orientation_required = (~self.has_grasped & (self.settings.grasp_orientation == "horizontal"))
        self.grip &= ~orientation_required | orientation_ok
        if self.settings.entry_first_grasp:
            from .entry_grasp import entry_gate
            from .logic import fruit_bounds
            tcp,tcp_quat=self._tcp()
            local=quat_apply(quat_conjugate(tcp_quat),self._grasp_center(fruit)-tcp)
            relative_quat=quat_mul(quat_conjugate(tcp_quat),fruit.data.root_link_quat_w)
            _,extent=fruit_bounds(torch.zeros_like(local),relative_quat,self.settings)
            self.entry_inside,self.entry_gap=entry_gate(local,extent[:,0],
                self.robot.data.joint_pos[:,self.jids[-1]],self.entry_inside,self.settings.diameter)
            # The capture-envelope contract belongs to the new approach expert.
            # After handoff, preserve the existing pull/transport grasp contract.
            entry_scope=getattr(self,"entry_grasp_active",torch.ones_like(self.entry_inside))
            self.grip &= self.entry_inside | ~entry_scope
        if self.settings.spring_grasp_grace:
            # A closed jaw cannot recreate the historical open-entry latch.
            # During post-break verification use current physical capture instead.
            from .logic import pending_capture_grip
            captured=pending_capture_grip(qualified_grasp(self.raw_grip,self.distance,self.settings),
                orientation_ok,self.settings.detached_capture_orientation)
            self.grip |= self.pending_detach & captured
        diagnostic = grasp_diagnostics(self.distance, self.actions[:,-1],
            self.robot.data.joint_vel[:,self.jids[-1]], f, m, self.raw_grip, self.settings)
        if self.settings.entry_first_grasp:
            diagnostic.update(entry_inside=self.entry_inside,entry_gap_m=self.entry_gap)
        diagnostic.update(centered_grasp=self.grip,
            offcenter_contact=self.raw_grip & (self.distance > self.settings.grasp_center_tolerance))
        self.diagnostic_steps += self.num_envs
        for name, mask in diagnostic.items():
            self.diagnostic_counts[name] = self.diagnostic_counts.get(name, 0) + mask.sum()
        # Snapshot before autoreset; all fields correspond to the same physical step.
        self.last_diagnostics = {**{key: value.clone() for key, value in diagnostic.items()}, "distance_m": self.distance.clone(),
            "close_action": self.actions[:,-1].clone(),
            "gripper_q_rad": self.robot.data.joint_pos[:,self.jids[-1]].clone(),
            "gripper_target_rad": self.targets[:,-1].clone(),
            "capture_gripper_target_held": getattr(self,'capture_gripper_target_held',torch.zeros_like(self.has_grasped)).float(),
            "transport_preload_latched": self.transport_preload_latched.float(),
            "transport_preload_adjusting": getattr(self,'transport_preload_adjusting',torch.zeros_like(self.has_grasped)).float(),
            "transport_preload_total_close_rad": torch.where(self.transport_preload_latched,self.transport_preload_origin-self.targets[:,-1],0.),
            "transport_gripper_target_held": getattr(self,'transport_gripper_target_held',torch.zeros_like(self.has_grasped)).float(),
            "gripper_velocity_rad_s": self.robot.data.joint_vel[:,self.jids[-1]].clone(),
            "fixed_force_N": f.norm(dim=-1), "moving_force_N": m.norm(dim=-1),
            "wrist_roll_rad": self.robot.data.joint_pos[:,self.jids[-2]].clone(),
            "grasp_orientation_error_rad": torch.asin(orientation_error),
            "break_had_confirmed_grasp": self.break_evidence[:,0].clone(),
            "break_centered_contact": self.break_evidence[:,1].clone(),
            "break_pull_direction_ok": self.break_evidence[:,2].clone(),
            "break_center_distance_m": self.break_evidence[:,3].clone(),
            "grasp_orientation_ok": orientation_ok.clone(),
            "capture_settle_entry": getattr(self,"capture_settle_entry",torch.zeros_like(self.grip)).clone(),
            "capture_settle_retention": getattr(self,"capture_settle_retention",torch.zeros_like(self.grip)).clone(),
            "retention_open_blocked": getattr(self,"retention_open_blocked",torch.zeros_like(self.grip)).clone(),
            "grasp_orientation_required": (orientation_required & ~(self.pending_detach & self.settings.detached_capture_orientation)).clone(),
            "pending_capture_orientation_blocked": (self.pending_detach & qualified_grasp(self.raw_grip,self.distance,self.settings) & ~orientation_ok).clone()}

        arm_forces = torch.linalg.vector_norm(self.arm_contact.data.net_forces_w, dim=-1)
        unwanted_finger = torch.maximum(
            torch.linalg.vector_norm(self.fixed_contact.data.net_forces_w[:,0]-f,dim=-1),
            torch.linalg.vector_norm(self.moving_contact.data.net_forces_w[:,0]-m,dim=-1))
        self.arm_collision = (arm_forces > 2.0).any(-1) | (unwanted_finger > 2.0)
        self.grip_time = torch.where(self.grip, self.grip_time+self.step_dt, torch.zeros_like(self.grip_time))
        confirmed = self.grip_time >= self.settings.grip_hold_s
        newly_confirmed = confirmed & ((self.grip_time-self.step_dt) < self.settings.grip_hold_s)
        self.squeeze_active |= newly_confirmed & (self.actions[:,-1] <= 0)
        if self.settings.pull_squeeze_rearm and (self.settings.task == "pull" or hasattr(self,"expert_stage")):
            rearmed = rearm_confirmed_squeeze(self.squeeze_active, confirmed, self.actions[:,-1])
            self.squeeze_active = rearmed if self.settings.task=="pull" else torch.where(self.expert_stage==0,rearmed,self.squeeze_active)
        self.grasp_event = confirmed & ~self.has_grasped
        _, tcp_quat = self._tcp()
        relative = quat_apply(quat_conjugate(tcp_quat), self._grasp_center(fruit) - tcp)
        refresh_reference = self.grasp_event
        if self.settings.stage_transfer:
            # A new confirmed grasp while still attached starts a fresh hold attempt.
            # Do not award grasp_event again or reset a detached-fruit slip reference.
            refresh_reference = refresh_reference | (newly_confirmed & self._t(self.attached))
        self.grasp_relative[refresh_reference] = relative[refresh_reference]
        self.pull_start_x[self.grasp_event] = self._grasp_center(fruit)[self.grasp_event,0]
        self.has_grasped |= confirmed
        if self.settings.spring_grasp_grace and self.settings.attachment_version==4:
            from .logic import early_detach_check
            pending_slip=(relative-self.pending_detach_relative).norm(dim=-1)
            (self.pending_detach,self.pending_detach_time,self.pending_detach_age,
             accepted,rejected)=early_detach_check(self.pending_detach,self.raw_grip,self.grip,
                self.distance,pending_slip,self.pending_detach_time,self.pending_detach_age,
                self.step_dt,self.settings.grip_hold_s,self.settings.grasp_center_tolerance,self.settings.max_slip)
            self.pending_detach_rejected |= rejected
            self.valid_detach |= accepted
            self.detach_event |= accepted
            self.has_grasped |= accepted
            self.grasp_relative[accepted]=relative[accepted]
        elif self.settings.native_grasp_grace:
            self._consume_joint_breaks()
            pending_slip = (relative-self.pending_detach_relative).norm(dim=-1)
            if self._native_recovery_enabled():
                (self.pending_detach, self.pending_detach_time, accepted, rejected,
                 self.pending_detach_age, self.pending_detach_lost) = recover_pending_detach(
                    self.pending_detach, self.grip, self.raw_grip, self.distance, pending_slip,
                    self.pending_detach_time, self.pending_detach_age, self.pending_detach_lost,
                    self.step_dt, self.settings.grip_hold_s, self.settings.max_slip,
                    max(.015, self.settings.grasp_center_tolerance))
            else:
                self.pending_detach, self.pending_detach_time, accepted, rejected = update_pending_detach(
                    self.pending_detach,self.grip,pending_slip,self.pending_detach_time,
                    self.step_dt,self.settings.grip_hold_s,self.settings.max_slip)
            self.pending_detach_rejected |= rejected
            self.valid_detach |= accepted
            self.detach_event |= accepted
        self.slip = torch.linalg.vector_norm(relative-self.grasp_relative,dim=-1)
        stable = self.grip & self.has_grasped & (self.slip < self.settings.max_slip)
        # First confirmation step precedes application of the test load: do not count it.
        self.loaded_time = dwell(self.loaded_time, stable & self._t(self.attached) & ~self.grasp_event, self.step_dt)
        self.detached_time = dwell(self.detached_time, stable & self.valid_detach & ~self._t(self.attached), self.step_dt)
        self.has_retained |= self.detached_time >= self.settings.detached_hold_s
        local_pos = fruit.data.root_link_pos_w - self.scene.env_origins
        released = ~self.raw_grip & (self.robot.data.joint_pos[:, self.jids[-1]] > .65)
        in_box = placement_contained(local_pos, fruit.data.root_link_quat_w, fruit.data.root_com_lin_vel_w, self.settings)
        self.released_in_box = (placement_contained(local_pos, fruit.data.root_link_quat_w, torch.zeros_like(local_pos), self.settings)
                                & released & self.valid_detach & self.has_retained & ~self._t(self.attached))
        valid_place = in_box & released & self.valid_detach & self.has_retained & ~self._t(self.attached)
        if self.settings.reward_version >= 7 and self.settings.task in ("harvest","transport","place"):
            speed = fruit.data.root_com_lin_vel_w.norm(dim=-1)
            tcp_speed = (tcp-self.previous_tcp).norm(dim=-1)/self.step_dt
            zone = above_box(local_pos,fruit.data.root_link_quat_w,self.settings)
            angular_slow=fruit.data.root_com_ang_vel_w.norm(dim=-1)<1.
            if getattr(self,"transport_pose_stop",self.settings.transport_pose_stop):
                from .logic import orientation_speed, transport_stage_mask
                pose_slow=orientation_speed(self.previous_fruit_quat,fruit.data.root_link_quat_w,self.step_dt)<1.
                angular_slow=torch.where(transport_stage_mask(self.settings.task,getattr(self,"expert_stage",None),self.has_grasped),pose_slow,angular_slow)
            self.stop_angular_slow=angular_slow
            fruit_speed_ok = speed <= self.settings.release_speed
            pose_speed = speed
            if self.settings.transport_linear_pose_stop and hasattr(self, "previous_fruit_com"):
                from .logic import transport_stop_speed, transport_stage_mask
                pose_speed = (fruit.data.root_com_pos_w-self.previous_fruit_com).norm(dim=-1)/self.step_dt
                scope = transport_stage_mask(self.settings.task,getattr(self,"expert_stage",None),self.has_grasped)
                fruit_speed_ok = torch.where(scope, transport_stop_speed(pose_speed,speed,self.settings.release_speed),fruit_speed_ok)
            slow=fruit_speed_ok&(tcp_speed<=self.settings.release_speed)&angular_slow
            paused = zone & slow & stable & self.has_retained & self.valid_detach
            # Arming survives slow finger opening, but expires if the hand accelerates or leaves the zone.
            self.release_armed &= zone & (tcp_speed <= self.settings.release_speed)
            self.stop_time = dwell(self.stop_time,paused,self.step_dt)
            self.release_armed |= self.stop_time >= self.settings.release_stop_s
            lost = self.previous_raw_grip & ~self.raw_grip & self.valid_detach & ~self.valid_release
            approved = controlled_release(lost,self.release_armed,self.previous_release_zone,
                self.previous_fruit_speed,tcp_speed,fruit.data.root_com_lin_vel_w[:,:2].norm(dim=-1),self.settings)
            opening = ((self.actions[:,-1] > .05) | (self.robot.data.joint_pos[:,self.jids[-1]]-self.previous_gripper_q > .005))
            approved &= opening & (self.robot.data.joint_pos[:,self.jids[-1]] > .65) & (fruit.data.root_com_ang_vel_w.norm(dim=-1)<1.)
            if self.settings.release_intent_mode:
                from .logic import release_intent_step
                motion_ok = ((tcp-self.release_intent_tcp).norm(dim=-1)<=.01) & (
                    (self.robot.data.joint_pos[:,self.jids[:5]]-self.release_intent_arm).abs().amax(dim=-1)<=.03)
                self.release_intent,self.release_intent_age,approved = release_intent_step(
                    self.release_intent,self.release_intent_age,lost,self.actions[:,-1],
                    motion_ok & (tcp_speed<=self.settings.release_speed),self.step_dt)
            self.valid_release |= approved
            self.bad_release |= lost & ~approved
            if self.settings.attachment_version==4 and self.settings.stem_response_version>=2:
                in_box=torch.zeros_like(self.raw_grip)
                for i,vertices in enumerate(self.fruit_collision_hulls):
                    in_box |= (self.target_index==i) & mesh_settled_in_box(local_pos,fruit.data.root_link_quat_w,
                        fruit.data.root_com_lin_vel_w,vertices,self.settings)
            else:
                in_box = settled_in_box(local_pos,fruit.data.root_link_quat_w,fruit.data.root_com_lin_vel_w,self.settings)
            self.released_in_box = self.valid_release & ~self.raw_grip
            # Release approval describes motion quality, not whether the fruit was deposited.
            valid_place = placement_outcome(in_box, self.raw_grip, self._t(self.attached),
                                            self.has_retained, self.valid_detach)

        self.place_time = torch.where(valid_place, self.place_time+self.step_dt, torch.zeros_like(self.place_time))
        # Grasp stage learns bilateral HOLD without rewarding accidental knock-off.
        self.success = stage_success(self.settings.task, confirmed, self._t(self.attached),
            self.loaded_time, self.detached_time, self.place_time, self.settings)
        if self.settings.task == "transport":
            self.success = (self.stop_time >= self.settings.release_stop_s) & self.grip & self.has_retained & self.valid_detach
        high_force = torch.maximum(torch.linalg.vector_norm(f, dim=-1), torch.linalg.vector_norm(m, dim=-1)) > self.settings.max_contact_force
        dropped = local_pos[:, 2] < .48
        stray = torch.linalg.vector_norm(local_pos[:, :2], dim=-1) > 1.5
        bad_detach = (~self._t(self.attached) & ~self.valid_detach & ~self.pending_detach) | self.pending_detach_rejected
        if self.settings.task in ("grasp", "hold"):
            bad_detach = ~self._t(self.attached)
        # Any detached distractor terminates the episode, preventing indiscriminate sweeping.
        other_detach = forbidden_detach(self.attached,self.collected,self.target_index)
        detached_other = ((~self.attached) & ~self.collected &
            (torch.arange(self.settings.num_fruits,device=self.device)[None,:] != self.target_index[:,None]))
        self.failure = high_force | dropped | stray | bad_detach | other_detach | (arm_forces > 12.0).any(-1) | (unwanted_finger > 12.0)
        # An unapproved release is diagnostic only; wait for containment or real failure.
        self.success &= ~self.failure
        self.collection_event.zero_()
        if self.settings.sequence and self.settings.task in ("harvest","place"):
            # Earlier fruits remain dynamic in the box and must still be contained at final success.
            contained = torch.stack([(mesh_settled_in_box(f.data.root_link_pos_w-self.scene.env_origins,
                f.data.root_link_quat_w,f.data.root_com_lin_vel_w,self.fruit_collision_hulls[i],self.settings)
                if self.settings.attachment_version==4 and self.settings.stem_response_version>=2 else
                settled_in_box(f.data.root_link_pos_w-self.scene.env_origins,f.data.root_link_quat_w,f.data.root_com_lin_vel_w,self.settings))
                for i,f in enumerate(self.fruits)],dim=1)
            self.success &= ((~self.collected) | contained).all(-1)
            self.collection_event = self.success & ~self._t(self.collected)
            ids = self.collection_event.nonzero().flatten()
            self.collected[ids,self.target_index[ids]] = True
            self.episode_metrics["fruits_collected"] += len(ids)
            remaining = (self.ripe & ~self.collected).any(-1)
            if self.settings.target_mode == "nearest":
                self.pending_next = self.collection_event & remaining
                self.success &= ~remaining
            else:
                self.pending_next.zero_()
        body_retreat = torch.where(self.has_grasped, self.pull_start_x-self._grasp_center(fruit)[:,0],
                                   torch.zeros_like(self.distance))
        tip_position = fruit.data.root_link_pos_w+quat_apply(fruit.data.root_link_quat_w,self.fruit_tips[self.target_index])
        self.last_diagnostics.update(body_retreat_m=body_retreat,
            stem_retreat_m=self._t(self.anchors)[:,0]-tip_position[:,0],
            valid_detach=self.valid_detach.clone(), detached_hold_s=self.detached_time.clone(),
            break_load_N=self._t(self.break_load).clone(),
            break_extension_m=torch.linalg.vector_norm(self._t(self.break_displacement), dim=-1),
            stem_extension_m=torch.linalg.vector_norm(tip_position-self._t(self.anchors), dim=-1),
            break_dwell_s=self._t(self.break_duration).clone(),
            stem_overtravel_break=(torch.linalg.vector_norm(self._t(self.break_displacement),dim=-1) >= self.settings.stem_max_extension)
                if self.settings.attachment_version == 4 and self.settings.stem_response_version >= 2 else torch.zeros_like(self.success),
            stem_load_N=self._t(self.load).clone(), break_threshold_N=self._t(self.threshold).clone(),
            target_color_id=self._t(self.color_ids).clone(), ripe_count=self.ripe.sum(-1),
            target_elapsed_s=self._target_elapsed_steps()*self.step_dt,
            target_index=self.target_index.clone(), harvested_count=self.collected.sum(-1),
            failure_other_detach=other_detach.clone(),
            other_detached_count=detached_other.sum(-1),
            other_break_tension_N=(self.break_load*detached_other).amax(-1),
            other_break_extension_m=(self.break_displacement.norm(dim=-1)*detached_other).amax(-1),
            other_break_dwell_s=(self.break_duration*detached_other).amax(-1),
            detached_stem_force_N=(self.applied_stem_force.norm(dim=-1)*(~self.attached)).amax(-1),
            detached_stem_torque_Nm=(self.applied_stem_torque.norm(dim=-1)*(~self.attached)).amax(-1),
            failure_green_detach=((~self.attached) & ~self.ripe).any(-1),
            stem_force_measured=torch.full_like(self.success,self.settings.attachment_version != 3),
            native_joint_break=(~self._t(self.attached)) if self.settings.attachment_version == 3 else torch.zeros_like(self.success),
            fruit_x_m=local_pos[:,0].clone(), fruit_y_m=local_pos[:,1].clone(), fruit_z_m=local_pos[:,2].clone(),
            fruit_speed_m_s=fruit.data.root_com_lin_vel_w.norm(dim=-1),
            release_stop_s=self.stop_time.clone(), valid_release=self.valid_release.clone(),
            transport_eligible=(self.valid_detach & self.has_retained & self.grip & ~self._t(self.attached)).clone(),
            has_retained=self.has_retained.clone(),
            pending_detach=self.pending_detach.clone(), pending_detach_s=self.pending_detach_time.clone(),
            pending_detach_age_s=self.pending_detach_age.clone(), pending_contact_lost_s=self.pending_detach_lost.clone(),
            failure_pending_detach=self.pending_detach_rejected.clone(),
            release_quality_violation=self.bad_release.clone(), in_box=in_box.clone(),
            placement_hold_s=self.place_time.clone(), released_in_box=self.released_in_box.clone(),
            placement_distance_m=torch.linalg.vector_norm(local_pos-placement_target(self.settings,self.device),dim=-1),
            center_error_m=self.distance.clone(),
            center_error_x_m=relative[:,0].clone(), center_error_y_m=relative[:,1].clone(),
            center_error_z_m=relative[:,2].clone(), grip_hold_s=self.grip_time.clone(),
            attached=self._t(self.attached).clone(), success=self.success.clone(), failure=self.failure.clone(),
            failure_high_force=high_force.clone(), failure_bad_detach=bad_detach.clone(),
            failure_dropped=dropped.clone(), failure_stray=stray.clone(),
            failure_arm_collision=(arm_forces > 12.0).any(-1), failure_unwanted_finger=unwanted_finger > 12.0)
        # Preserve each release gate in evaluation traces, not only reward logs.
        if self.settings.reward_version >= 7 and self.settings.task in ("harvest","transport","place"):
            self.last_diagnostics.update(
                stop_zone_ok=zone.clone(),
                stop_fruit_speed_ok=fruit_speed_ok.clone(),
                stop_fruit_pose_speed_m_s=pose_speed.clone(),
                stop_tcp_speed_ok=(tcp_speed <= self.settings.release_speed),
                stop_angular_ok=angular_slow.clone(),
                stop_stable_grip_ok=stable.clone(),
                stop_all_ok=paused.clone(),
                stop_tcp_speed_m_s=tcp_speed.clone(),
                stop_slip_m=self.slip.clone(),
                release_armed=self.release_armed.clone())
        if not torch.isfinite(self.robot.data.joint_pos).all() or not torch.isfinite(local_pos).all():
            raise FloatingPointError("Non-finite simulator state")

    def _target_elapsed_steps(self):
        return target_elapsed(self.episode_length_buf,self.target_start_step,
                              self.settings.target_mode == "external" or
                              (self.settings.sequence and self.settings.timeout_scope == "fruit"))

    def _get_dones(self):
        self._update_task()
        timed_out = self._target_elapsed_steps() >= self.max_episode_length - 1
        if self.settings.sequence and self.settings.timeout_scope == "fruit":
            timed_out &= ~self.collection_event
        if self.settings.target_mode == "external":
            if bool(self.failure[0]):
                self.assignment_status = "FAILED"
            elif bool(self.success[0]):
                self.assignment_status = "SUCCEEDED"
            elif bool(timed_out[0]):
                self.assignment_status = "TIMED_OUT"
            # Caller consumes status; never auto-reset the physical scene.
            return torch.zeros_like(self.success), torch.zeros_like(timed_out)
        return self.success | self.failure, timed_out

    def proprio(self):
        q = self.robot.data.joint_pos[:, self.jids]
        qd = self.robot.data.joint_vel[:, self.jids]
        return torch.cat((2*(q-self.lower)/(self.upper-self.lower)-1, qd/1.5, self.actions), dim=-1)

    def _get_observations(self):
        self._advance_target()
        tcp, quat = self._tcp()
        fruit = self._target_fruit()
        others = torch.zeros(self.num_envs, 8, 3, device=self.device)
        mask = torch.zeros(self.num_envs, 8, device=self.device)
        for i, obj in enumerate(self.fruits):
            others[:, i] = obj.data.root_link_pos_w-tcp
            mask[:, i] = 1 if not self.settings.sequence else torch.where(self.collected[:,i],0.,torch.where(self.ripe[:,i],1.,-1.))
        box = torch.tensor([.4,0.,.8], device=self.device)+self.scene.env_origins
        progress = self.grip_time/self.settings.grip_hold_s
        if self.settings.stage_transfer:
            progress = progress.clamp(0,1)
        elif self.settings.task == "hold":
            progress = self.loaded_time/self.settings.hold_s
        elif self.settings.task == "pull":
            progress = self.detached_time/self.settings.detached_hold_s
        elif self.settings.task in ("harvest","transport","place") and self.settings.reward_version >= 7:
            progress = self.stop_time/self.settings.release_stop_s
        scalar = torch.stack((self._t(self.attached).float(), progress,
            self.has_grasped.float(), self.valid_detach.float(),
            1-self._target_elapsed_steps()/self.max_episode_length, self.place_time/self.settings.place_hold_s), dim=-1)
        obs = torch.cat((self.proprio(), tcp-self.scene.env_origins, quat,
            fruit.data.root_link_pos_w-tcp, fruit.data.root_com_lin_vel_w,
            fruit.data.root_link_quat_w, box-tcp, scalar, others.flatten(1), mask,
            self._t(self.anchors)-tcp, (self._t(self.load)/self.settings.break_force)[:,None],
            (self._t(self.break_timer)/self.settings.break_hold_s)[:,None],
            (self._t(self.threshold)/self.settings.break_force)[:,None]), dim=-1)
        if obs.shape[-1] != 82 or not torch.isfinite(obs).all():
            raise RuntimeError(f"Invalid observation contract: {obs.shape}")
        return {"policy": obs}
