"""Separate 60Hz grasp domain; preserves the frozen HarvestEnv implementation."""
import math
from types import SimpleNamespace
from unittest.mock import patch
import torch
from . import env as base_environment
from .env import HarvestEnv
from .teacher_domain import canonical_quaternion, sample_pose, reset_geometry, promote_stage


class TeacherDomainEnv(HarvestEnv):
    def __init__(self, *args, domain, domain_stage=0, domain_split='train', **kwargs):
        self.domain = domain
        self.domain_stage = domain_stage
        self.domain_ready = False
        original_config = base_environment.HarvestEnvCfg
        def domain_config():
            cfg = original_config()
            # Full robot meshes exceed PhysX's default 163840 patches at 2048
            # environments. Contact loss due to overflow must not shape PPO.
            count = kwargs.get('num_envs', 32)
            capacity = 1 << max(20, (count*512-1).bit_length())
            cfg.sim.physx.gpu_max_rigid_patch_count = capacity
            return cfg
        # Install only while the frozen parent's constructor makes its config.
        # No source edit or lasting change to other environments in this process.
        with patch.object(base_environment, 'HarvestEnvCfg', domain_config):
            super().__init__(*args, **kwargs)
        if self.settings.num_fruits != 2 or self.fruit_colors != domain['colors']:
            raise ValueError('Domain requires the actual Red and Yellow assets')
        bank_size = len(self.bank_np['points'])
        train_end, validation_end = int(bank_size*.8), int(bank_size*.9)
        ranges = {'train': (0, train_end), 'validation': (train_end, validation_end),
                  'test': (validation_end, bank_size)}
        start, end = ranges[domain_split]
        self.domain_bank_ids = torch.arange(start, end, device=self.device)
        self.points = torch.tensor(self.bank_np['points'][start:end],
            device=self.device, dtype=torch.float32)
        self.domain_rng = torch.Generator(device=self.device).manual_seed(self.settings.seed+100003)
        self.domain_samples = torch.zeros((self.num_envs, 6), device=self.device)
        self.domain_history = torch.zeros((domain['recent_window'], 9), device=self.device)
        self.domain_count = self.domain_cursor = 0
        self.last_domain_episodes = []
        self.domain_totals = torch.zeros((len(domain['stages']), 2), device=self.device)
        self.domain_pools = []
        from .kinematics import ArmKinematics
        from .settings import CACHE
        home_tcp = self.points.new_tensor(ArmKinematics(CACHE/'harvest_training.urdf').grasp_fk(
            self.bank_np['home'], self.settings.diameter)[:3, 3])
        distance = (self.points-home_tcp).norm(dim=-1)
        lo = self.points.new_tensor(self.settings.region_origin)+self.points.new_tensor(self.settings.region_min)
        hi = self.points.new_tensor(self.settings.region_origin)+self.points.new_tensor(self.settings.region_max)
        inside = ((self.points >= lo) & (self.points <= hi)).all(-1)
        for stage in domain['stages']:
            pool = (inside & (distance > domain['minimum_home_distance_m'])
                    & (distance < stage['max_home_distance_m'])).nonzero().flatten()
            if not len(pool):
                raise ValueError(f'No reachable bank candidates in stage {stage}')
            self.domain_pools.append(pool)
        self.domain_distances = distance
        self.domain_ready = True

    def _target_fruit(self):
        if not getattr(self, 'domain_ready', False):
            return super()._target_fruit()
        names = ('root_link_pos_w', 'root_link_quat_w', 'root_com_pos_w',
                 'root_com_lin_vel_w', 'root_com_ang_vel_w')
        data = {name: self._t(torch.stack([getattr(f.data, name) for f in self.fruits], 1))
                for name in names}
        return SimpleNamespace(data=SimpleNamespace(**data))

    def _get_observations(self):
        observation = super()._get_observations()
        if self.domain_ready:
            obs = observation['policy']
            obs[:, 21:25] = canonical_quaternion(obs[:, 21:25])
            obs[:, 31:35] = canonical_quaternion(obs[:, 31:35])
            # One target in the working area. The spare color is not an obstacle
            # or a policy input; its position cannot leak a color/target shortcut.
            obs[:, 44:76] = 0
            obs[:, 44:47] = obs[:, 25:28]
            obs[:, 68] = 1
        return observation

    def _reset_impl(self, env_ids):
        ready = getattr(self, 'domain_ready', False)
        if ready:
            ids = self.robot._ALL_INDICES if env_ids is None else env_ids
            finished = ids[(self.episode_length_buf[ids] > 0)
                           & (self.success | self.failure | self.reset_time_outs)[ids]]
            if len(finished):
                samples = self.domain_samples[finished]
                early = ~self._t(self.attached)[finished] & ~self.has_grasped[finished]
                rows = torch.cat((torch.stack((self.success[finished], self.failure[finished],
                    early, self.arm_collision[finished]), -1).float(), samples[:, 1:]), -1)
                stages = samples[:, -1].long()
                self.domain_totals[:, 0].scatter_add_(0, stages, torch.ones_like(stages, dtype=torch.float))
                self.domain_totals[:, 1].scatter_add_(0, stages, self.success[finished].float())
                rows = rows[-len(self.domain_history):]
                indices = (torch.arange(len(rows), device=self.device)+self.domain_cursor)%len(self.domain_history)
                self.domain_history[indices] = rows
                self.domain_cursor = (self.domain_cursor+len(rows))%len(self.domain_history)
                self.domain_count = min(len(self.domain_history), self.domain_count+len(rows))
                if getattr(self, 'domain_evaluation', False):
                    sample_rows = self.domain_samples[finished].cpu().tolist()
                    success = self.success[finished].cpu().tolist()
                    failure = self.failure[finished].cpu().tolist()
                    reasons = {key:value[finished].cpu().tolist()
                        for key,value in self.last_diagnostics.items() if key.startswith('failure_')}
                    for i, env_id in enumerate(finished.cpu().tolist()):
                        sample = sample_rows[i]
                        self.last_domain_episodes.append(dict(env_id=env_id, success=success[i],
                            failure=failure[i], timeout=not success[i] and not failure[i],
                            bank_point_id=int(sample[0]), tilt_deg=sample[1], yaw_deg=sample[2],
                            home_distance_m=sample[3], color=self.domain['colors'][int(sample[4])],
                            stage=int(sample[5]), reasons=[key for key,values in reasons.items() if values[i]]))
        super()._reset_impl(env_ids)
        if not ready:
            return
        ids = self.robot._ALL_INDICES if env_ids is None else env_ids
        n = len(ids)
        pool = self.domain_pools[self.domain_stage]
        choice = torch.randint(len(pool), (n,), generator=self.domain_rng, device=self.device)
        point_id = pool[choice]
        color = torch.randint(2, (n,), generator=self.domain_rng, device=self.device)
        quat, tilt, yaw = sample_pose(n, self.domain, self.domain_stage, self.domain_rng, self.device)
        self.target_index[ids] = color
        self.ripe[ids] = False
        self.ripe[ids, color] = True
        offset = self.points.new_tensor([0., 0., -self.settings.length*.08])
        for slot, fruit in enumerate(self.fruits):
            active = color == slot
            nominal = self.points[point_id].clone()
            # Spare is a normal dynamic body outside the arm/box working area.
            # This placement happens only at reset, never to keep a grasp alive.
            nominal[~active] = nominal.new_tensor([1.25, 1.25, .9])
            q = quat.clone()
            q[~active] = q.new_tensor([1., 0., 0., 0.])
            root, anchor = reset_geometry(nominal, q, offset, self.fruit_tips[slot])
            state = fruit.data.default_root_state[ids].clone()
            state[:, :3] = root+self.scene.env_origins[ids]
            state[:, 3:7] = q
            state[:, 7:] = 0
            fruit.write_root_state_to_sim(state, env_ids=ids)
            fruit.reset(ids)
            self.anchors[ids, slot] = anchor+self.scene.env_origins[ids]
            self.rest_quat[ids, slot] = q
        # Existing threshold randomization is retained, using this domain's RNG.
        self.threshold[ids] = self.settings.break_force*(.8+.4*torch.rand(
            (n, 2), generator=self.domain_rng, device=self.device))
        q = self.robot.data.default_joint_pos[ids].clone()
        home = self.home.expand(n, -1).clone()
        home[:, :5] += (2*torch.rand((n, 5), generator=self.domain_rng, device=self.device)-1)*self.domain['home_arm_jitter_rad']
        home = torch.maximum(torch.minimum(home, self.upper), self.lower)
        q[:, self.jids] = home
        self.robot.write_joint_state_to_sim(q, torch.zeros_like(q), env_ids=ids)
        self.targets[ids] = home
        self.robot.set_joint_position_target(home, joint_ids=self.jids, env_ids=ids)
        self.domain_samples[ids] = torch.stack((self.domain_bank_ids[point_id].float(), tilt*180/math.pi,
            yaw*180/math.pi, self.domain_distances[point_id], color.float(),
            torch.full_like(tilt, self.domain_stage)), -1)
        self._draw_stems()

    def _get_rewards(self):
        self.last_domain_episodes = []
        reward = super()._get_rewards()
        if self.domain_ready:
            self.extras['log'].update(self.domain_metrics())
        return reward

    def domain_metrics(self):
        rows = self.domain_history[:self.domain_count]
        result = {'Domain/stage': self.points.new_tensor(self.domain_stage),
                  'Domain/recent_episodes': self.points.new_tensor(self.domain_count)}
        masks = {'current': rows[:, 8] == self.domain_stage,
                 'red': rows[:, 7] == 0, 'yellow': rows[:, 7] == 1,
                 'tilt_0_10': rows[:, 4] <= 10,
                 'tilt_10_20': (rows[:, 4] > 10) & (rows[:, 4] <= 20),
                 'tilt_20_30': rows[:, 4] > 20,
                 'distance_near': rows[:, 6] <= .18,
                 'distance_far': rows[:, 6] > .18}
        for i in range(4):
            masks[f'yaw_sector_{i}'] = ((rows[:, 5]+180)/90).floor().clamp(0, 3) == i
        for name, mask in masks.items():
            count = mask.sum()
            result[f'Domain/{name}_episodes'] = count
            result[f'Domain/{name}_success'] = (rows[:, 0]*mask).sum()/count.clamp_min(1)
        for name, column in [('early_detach', 2), ('arm_collision', 3), ('failure', 1)]:
            result[f'Domain/recent_{name}'] = rows[:, column].sum()/max(1, self.domain_count)
        return result

    def advance_curriculum(self, iteration):
        values = self.domain_metrics()
        count = int(values['Domain/current_episodes'])
        rate = float(values['Domain/current_success'])
        stage = promote_stage(self.domain, self.domain_stage, iteration, count, rate)
        if stage != self.domain_stage:
            self.domain_stage = stage
            print('TEACHER60_DOMAIN_PROMOTED', dict(iteration=iteration, stage=stage,
                previous_stage_episodes=count, previous_stage_success=rate,
                **self.domain['stages'][stage]), flush=True)
        # Existing episodes keep their initial poses/anchors. Only future resets
        # use the new stage; there is no curriculum-induced mid-episode reset.

    def domain_state(self):
        return dict(stage=self.domain_stage, count=self.domain_count, cursor=self.domain_cursor,
            history=self.domain_history.cpu(), totals=self.domain_totals.cpu(),
            generator_state=self.domain_rng.get_state().cpu())

    def restore_domain_state(self, state):
        self.domain_stage = state['stage']
        self.domain_count, self.domain_cursor = state['count'], state['cursor']
        self.domain_history.copy_(state['history'])
        self.domain_totals.copy_(state['totals'])
        self.domain_rng.set_state(state['generator_state'])

    def domain_audit(self):
        return dict(stage=self.domain_stage, pool_sizes=[len(p) for p in self.domain_pools],
            totals_by_stage=self.domain_totals.cpu().tolist(),
            recent={k: float(v) for k, v in self.domain_metrics().items()},
            sample_columns=['bank_point_id', 'tilt_deg', 'yaw_deg', 'home_distance_m', 'color_id', 'stage'],
            reset_samples=self.domain_samples[:min(self.num_envs, 128)].cpu().tolist(),
            active_fruits_per_workspace=1, physical_color_actors_per_env=2)
