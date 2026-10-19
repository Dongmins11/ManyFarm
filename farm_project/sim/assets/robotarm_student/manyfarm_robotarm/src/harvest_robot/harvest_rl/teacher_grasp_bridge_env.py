"""Learn approach contacts that survive the real fixed-prefix pull handoff."""
import math
import torch
from .teacher_load_reserve_env import TeacherLoadReserveEnv
from .bounded_grip_60hz import BoundedGripPreload
from .grasp_bridge_60hz import SPEC, bridge_step


class TeacherGraspBridgeEnv(TeacherLoadReserveEnv):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.bridge_started = torch.zeros_like(self.has_grasped)
        self.bridge_hold_time = torch.zeros_like(self.grip_time)
        self.bridge_arm_targets = self.targets[:, :5].clone()
        self.bridge_preload = BoundedGripPreload(self.num_envs, self.device,
            math.radians(SPEC['preload_deg']), math.radians(SPEC['preload_rate_deg_s']))
        self.bridge_episode_records = []
        self.bridge_serial = torch.zeros(self.num_envs,device=self.device,dtype=torch.long)
        self.bridge_totals = dict(confirmed=0, passed=0, contact_loss=0, original_failure=0)

    def _pre_physics_step(self, proposed):
        previous = self.targets.clone()
        super()._pre_physics_step(proposed)
        if not hasattr(self, 'bridge_started'):
            return
        scope = self.bridge_started & ~self.release_intent
        self.actions[scope] = 0.
        self.targets[scope, :5] = self.bridge_arm_targets[scope]
        target, _ = self.bridge_preload.step(previous[:, -1], self.targets[:, -1],
            self.robot.data.joint_pos[:, self.jids[-1]], self.actions[:, -1], scope,
            speed=self.settings.gripper_speed, dt=self.step_dt,
            max_error=self.settings.gripper_max_error, lower=self.lower[-1], upper=self.upper[-1])
        self.targets[:, -1] = target

    def _update_task(self):
        super()._update_task()
        if not hasattr(self, 'bridge_started'):
            return
        original_success, original_failure = self.success.clone(), self.failure.clone()
        qualified = self.grip & self.raw_grip & (self.slip < self.settings.max_slip)
        (self.bridge_started, self.bridge_hold_time, self.success,
            lost, first) = bridge_step(self.bridge_started, self.bridge_hold_time,
                original_success, qualified, self._t(self.attached), original_failure, self.step_dt)
        self.bridge_arm_targets[first] = self.targets[first, :5]
        self.failure |= lost
        fruit = self._target_fruit().data
        self.last_diagnostics.update(instant_grasp_success=original_success,
            bridge_confirmed=self.bridge_started.clone(), bridge_hold_s=self.bridge_hold_time.clone(),
            bridge_first_confirmation=first, failure_bridge_contact_loss=lost,
            bridge_original_failure=original_failure,
            bridge_arm_speed_rad_s=self.robot.data.joint_vel[:, self.jids[:5]].abs().amax(-1),
            bridge_fruit_speed_m_s=fruit.root_com_lin_vel_w.norm(dim=-1),
            bridge_fruit_angular_speed_rad_s=fruit.root_com_ang_vel_w.norm(dim=-1),
            success=self.success.clone(), failure=self.failure.clone())

    def _get_rewards(self):
        result = super()._get_rewards()
        if not hasattr(self, 'bridge_started'):
            return result
        proposed = self.confirmation_proposed
        scope = self.bridge_started & ~self.success & ~self.failure
        cost = SPEC['proposal_cost_per_s']*self.step_dt*scope*torch.log1p(proposed.square()).mean(-1)
        result = result-cost
        self.extras['log'].update({'Bridge/'+key:value.float().mean()
            for key,value in dict(confirmed=self.bridge_started, hold_s=self.bridge_hold_time,
                contact_loss=self.last_diagnostics['failure_bridge_contact_loss'],
                passed=self.success, raw_proposal_cost=cost).items()})
        if not torch.isfinite(result).all():
            raise FloatingPointError('Nonfinite bridge reward')
        stream=getattr(self,'bridge_trace_stream',None)
        if stream is not None:
            import json
            d=self.last_diagnostics
            columns=['bridge_confirmed','bridge_hold_s','bridge_first_confirmation',
                'instant_grasp_success','bilateral_contact','centered_grasp','fixed_force_N',
                'moving_force_N','distance_m','bridge_arm_speed_rad_s',
                'gripper_velocity_rad_s','bridge_fruit_speed_m_s','success','failure',
                'failure_bridge_contact_loss','bridge_original_failure','attached']
            values=torch.stack([d[k].float() for k in columns],-1).cpu().tolist()
            stream.write(json.dumps(dict(batch=getattr(self,'bridge_evaluation_batch',0),
                episode_serial=self.bridge_serial.cpu().tolist(),
                episode_step=self.episode_length_buf.cpu().tolist(),
                columns=columns,rows=values))+'\n')
        return result

    def _reset_impl(self, env_ids):
        if hasattr(self, 'bridge_started'):
            ids = self.robot._ALL_INDICES if env_ids is None else env_ids
            finished = ids[(self.episode_length_buf[ids] > 0)
                & (self.success | self.failure | self.reset_time_outs)[ids]]
            for key, values in dict(confirmed=self.bridge_started, passed=self.success,
                    contact_loss=self.last_diagnostics.get('failure_bridge_contact_loss', self.failure),
                    original_failure=self.last_diagnostics.get('bridge_original_failure', self.failure)).items():
                self.bridge_totals[key] += int(values[finished].sum())
            if getattr(self, 'domain_evaluation', False):
                for i in finished.cpu().tolist():
                    self.bridge_episode_records.append(dict(env_id=i,
                        batch=getattr(self,'bridge_evaluation_batch',0),episode_serial=int(self.bridge_serial[i]),
                        confirmed=bool(self.bridge_started[i]), passed=bool(self.success[i]),
                        hold_s=float(self.bridge_hold_time[i]),
                        contact_loss=bool(self.last_diagnostics['failure_bridge_contact_loss'][i]),
                        original_failure=bool(self.last_diagnostics['bridge_original_failure'][i]),
                        attached=bool(self._t(self.attached)[i]),
                        bank_point_id=int(self.domain_samples[i, 0]),
                        color=self.domain['colors'][int(self.domain_samples[i, 4])],
                        tilt_deg=float(self.domain_samples[i, 1]), yaw_deg=float(self.domain_samples[i, 2]),
                        arm_speed_rad_s=float(self.last_diagnostics['bridge_arm_speed_rad_s'][i]),
                        jaw_speed_rad_s=float(self.last_diagnostics['gripper_velocity_rad_s'][i]),
                        fruit_speed_m_s=float(self.last_diagnostics['bridge_fruit_speed_m_s'][i])))
        super()._reset_impl(env_ids)
        if hasattr(self, 'bridge_started'):
            self.bridge_serial[ids] += 1
            self.bridge_started[ids] = False
            self.bridge_hold_time[ids] = 0.
            self.bridge_preload.reset(ids)
