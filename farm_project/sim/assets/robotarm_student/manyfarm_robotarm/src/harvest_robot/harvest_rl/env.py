"""Isaac Lab PhysX environment. Launch SimulationApp before importing this module."""
import time
import json
from types import SimpleNamespace
import numpy as np
import torch
import isaaclab.sim as sim_utils
from isaaclab.assets import Articulation, ArticulationCfg, RigidObject, RigidObjectCfg
from isaaclab.actuators import ImplicitActuatorCfg
from isaaclab.envs import DirectRLEnv, DirectRLEnvCfg
from isaaclab.scene import InteractiveSceneCfg
from isaaclab.sensors import ContactSensor, ContactSensorCfg, TiledCamera, TiledCameraCfg
from isaaclab.utils import configclass
from isaaclab.utils.math import quat_apply, quat_mul, quat_conjugate, matrix_from_quat
from isaaclab.markers import VisualizationMarkers, VisualizationMarkersCfg
from .sequence import fruit_colors, next_target, forbidden_detach, sample_color_ids, target_elapsed, random_target, sample_separated
from .assets import collision_hull_points, fruit_asset, find_body_path, bind_verified_material
from .settings import CACHE, ASSETS, JOINTS, TaskSettings
from .logic import mesh_settled_in_box, pull_direction_cost, placement_outcome, pull_recovery_step, rearm_confirmed_squeeze, pull_squeeze_error, tensile_progress_reward, placement_contained, horizontal_grasp_alignment, attachment_wrench, bilateral_contact, contained_in_box, valid_pull, limited_joint_targets, dwell, stage_success, compliant_gripper_hold, grasp_diagnostics, grasp_shaping, qualified_grasp, centered_grasp_shaping, pull_stage_shaping, separation_stage_shaping, harvest_place_shaping, placement_target, settled_in_box, above_box, controlled_release, update_pending_detach, recover_pending_detach, harvest_stage_bonus, transport_potential_step


@configclass
class HarvestEnvCfg(DirectRLEnvCfg):
    decimation = 12
    episode_length_s = 20.0
    action_space = 6
    observation_space = 82
    state_space = 0
    sim = sim_utils.SimulationCfg(dt=1/240, render_interval=12,
        physics_material=sim_utils.RigidBodyMaterialCfg(static_friction=1.0, dynamic_friction=.8, restitution=0.0))
    scene = InteractiveSceneCfg(num_envs=32, env_spacing=3.0, replicate_physics=True)


class HarvestEnv(DirectRLEnv):
    def __init__(self, settings=None, num_envs=32, device="cuda:0", cameras=False,
                 robot_usd=None, robot_root_pose=None, fruit_color_override=None, fruit_asset_cache=None,
                 visual_scene="greenhouse_v1", **kwargs):
        from .visual_scene import describe
        self.visual_scene = describe(visual_scene)
        self.settings = (settings or TaskSettings()).validate()
        self.assignment_status = "WAIT_TARGET"
        if self.settings.target_mode == "external" and num_envs != 1:
            raise ValueError("External target API currently supports one environment")
        self.use_cameras = cameras
        self.robot_usd = str(robot_usd or (CACHE / "harvest_robot.usd"))
        self.robot_root_pose = robot_root_pose or ((0.,0.,0.),(1.,0.,0.,0.))
        self.fruit_color_override = fruit_color_override
        self.fruit_asset_cache = fruit_asset_cache
        if fruit_color_override is not None and (len(fruit_color_override) != self.settings.num_fruits
                or any(c not in ("Red","Yellow","Green") for c in fruit_color_override)):
            raise ValueError("Invalid explicit fruit colors")
        if not (CACHE / "harvest_robot.usd").exists():
            raise FileNotFoundError("Run src/harvest_robot/prepare.py --headless first")
        bank = np.load(CACHE / "workspace.npz")
        if abs(float(bank["diameter"]) - self.settings.diameter) > 1e-6:
            raise ValueError("Regenerate workspace with prepare.py --diameter matching this run")
        self.bank_np = {k: bank[k] for k in bank.files}
        cfg = HarvestEnvCfg()
        cfg.seed = self.settings.seed
        cfg.sim.device = device
        cfg.scene.num_envs = num_envs
        cfg.decimation = self.settings.decimation*self.settings.contact_substeps
        cfg.sim.dt = self.settings.physics_dt/self.settings.contact_substeps
        from .simulation_clock import render_interval
        cfg.sim.render_interval = render_interval(cfg.sim.dt,cfg.decimation,self.settings.render_hz)
        cfg.episode_length_s = self.settings.episode_s
        # Refresh RTX outputs after teleport/reset before constructing Student histories.
        cfg.num_rerenders_on_reset = 2 if cameras else 0
        # Free spectator view only. Neither D435 nor policy camera transforms move.
        cfg.viewer.eye = (1.8, -2.0, 1.65) if visual_scene == 'legacy' else (-.6, -1.6, 1.65)
        cfg.viewer.lookat = (.35, -.1, .8)
        super().__init__(cfg, **kwargs)
        self.jids, _ = self.robot.find_joints(["arm_2_"+j for j in JOINTS], preserve_order=True)
        if len(self.jids) != 6:
            raise RuntimeError(f"Wrong controlled joints: {self.robot.joint_names}")
        self.tcp_body = self.robot.find_bodies("arm_2_gripper_link")[0][0]
        self.tcp_offset = torch.tensor([-.0079+self.settings.diameter/2, -.000218121, -.085], device=self.device).repeat(num_envs, 1)
        self.points = torch.tensor(self.bank_np["points"], device=self.device, dtype=torch.float32)
        split = int(len(self.points)*.8)
        self.points = self.points[:split] if self.settings.workspace_split == "train" else self.points[split:]
        self.home = torch.tensor(self.bank_np["home"], device=self.device, dtype=torch.float32)
        self.lower = torch.tensor(self.bank_np["lower"], device=self.device, dtype=torch.float32)
        self.upper = torch.tensor(self.bank_np["upper"], device=self.device, dtype=torch.float32)
        self.fruit_tips = torch.tensor(np.asarray(self.tips_np),device=self.device,dtype=torch.float32)
        self.tip = torch.tensor(self.attachment_np, device=self.device, dtype=torch.float32).repeat(num_envs, 1)
        self.target_index = torch.zeros(num_envs,dtype=torch.long,device=self.device)
        self.collected = torch.zeros(num_envs,self.settings.num_fruits,dtype=torch.bool,device=self.device)
        self.pending_next = torch.zeros(num_envs,dtype=torch.bool,device=self.device)
        self.collection_event = torch.zeros_like(self.pending_next)
        self.color_ids = torch.tensor([("Red","Yellow","Green").index(color) for color in self.fruit_colors],device=self.device).repeat(num_envs,1)
        self.ripe = self.color_ids != 2
        self.target_start_step = torch.zeros(num_envs,dtype=torch.long,device=self.device)
        self.actions = torch.zeros(num_envs, 6, device=self.device)
        self.previous_actions = torch.zeros_like(self.actions)
        self.targets = self.home.repeat(num_envs, 1)
        shape = (num_envs, self.settings.num_fruits)
        self.anchors = torch.zeros(*shape, 3, device=self.device)
        self.rest_quat = torch.zeros(*shape, 4, device=self.device)
        self.rest_quat[...,0] = 1
        self.attached = torch.ones(shape, dtype=torch.bool, device=self.device)
        self.break_timer = torch.zeros(shape, device=self.device)
        self.break_duration = torch.zeros(*shape,device=self.device)
        self.break_load = torch.zeros(*shape,device=self.device)
        self.break_displacement = torch.zeros(*shape,3,device=self.device)
        self.break_evidence = torch.zeros(self.num_envs,6,device=self.device)
        self.threshold = torch.full(shape, self.settings.break_force, device=self.device)
        self.entry_inside = torch.zeros(num_envs,device=self.device,dtype=torch.bool)
        self.previous_distance = torch.zeros(num_envs, device=self.device)
        self.previous_gripper_q = torch.zeros(num_envs, device=self.device)
        self.diagnostic_counts = {}
        self.diagnostic_steps = 0
        self.last_diagnostics = {}
        self.grip_time = torch.zeros(num_envs, device=self.device)
        self.place_time = torch.zeros_like(self.grip_time)
        self.loaded_time = torch.zeros_like(self.grip_time)
        self.detached_time = torch.zeros_like(self.grip_time)
        self.grasp_relative = torch.zeros(num_envs, 3, device=self.device)
        self.slip = torch.zeros_like(self.grip_time)
        self.pull_start_x = torch.zeros_like(self.grip_time)
        self.pull_best_retreat = torch.zeros_like(self.grip_time)
        self.pull_recovery_potential = torch.zeros_like(self.grip_time)
        self.place_best_distance = torch.full_like(self.grip_time, float("inf"))
        self.stop_time = torch.zeros_like(self.grip_time)
        self.stop_best_time = torch.zeros_like(self.grip_time)
        self.release_armed = torch.zeros(num_envs,dtype=torch.bool,device=self.device)
        self.release_intent = torch.zeros_like(self.release_armed)
        self.release_target_unloaded = torch.zeros_like(self.release_armed)
        self.release_intent_age = torch.zeros(num_envs,device=self.device)
        self.release_intent_tcp = torch.zeros(num_envs,3,device=self.device)
        self.release_intent_arm = torch.zeros(num_envs,5,device=self.device)
        self.valid_release = torch.zeros_like(self.release_armed)
        self.bad_release = torch.zeros_like(self.release_armed)
        self.place_best_time = torch.zeros_like(self.grip_time)
        self.release_paid = torch.zeros(num_envs, dtype=torch.bool, device=self.device)
        self.has_grasped = torch.zeros(num_envs, dtype=torch.bool, device=self.device)
        self.squeeze_active = torch.zeros_like(self.has_grasped)
        self.transport_preload_latched = torch.zeros_like(self.has_grasped)
        self.transport_preload_origin = torch.zeros(num_envs, device=self.device)
        self.valid_detach = torch.zeros_like(self.has_grasped)
        self.transport_started = torch.zeros_like(self.has_grasped)
        self.transport_origin = torch.zeros(num_envs,device=self.device)
        self.transport_potential = torch.zeros(num_envs,device=self.device)
        self.pending_detach = torch.zeros_like(self.has_grasped)
        self.pending_detach_time = torch.zeros(num_envs,device=self.device)
        self.pending_detach_age = torch.zeros_like(self.pending_detach_time)
        self.pending_detach_lost = torch.zeros_like(self.pending_detach_time)
        self.pending_detach_relative = torch.zeros(num_envs,3,device=self.device)
        self.pending_detach_rejected = torch.zeros_like(self.has_grasped)
        self.has_retained = torch.zeros_like(self.has_grasped)
        self.grip = torch.zeros_like(self.has_grasped)
        self.success = torch.zeros_like(self.has_grasped)
        self.failure = torch.zeros_like(self.has_grasped)
        self.detach_event = torch.zeros_like(self.has_grasped)
        self.grasp_event = torch.zeros_like(self.has_grasped)
        self.load = torch.zeros(shape, device=self.device)
        self.applied_stem_force = torch.zeros((*shape,3), device=self.device)
        self.applied_stem_torque = torch.zeros_like(self.applied_stem_force)
        self.easy_episode = torch.zeros(num_envs, dtype=torch.bool, device=self.device)
        self.episode_metrics = {key: 0 for key in ("fruits_collected", "episodes", "success", "grasp", "detach", "failure",
            "easy_episodes", "easy_success", "home_episodes", "home_success")}
        self.arm_collision = torch.zeros_like(self.has_grasped)
        self.joint_attachments = None
        if self.settings.attachment_version == 3:
            from .joint_attachment import JointAttachments
            self.joint_attachments = JointAttachments(self.sim.stage)
        self.visual_updates = self.use_cameras or self.sim.has_gui() or self.sim.has_rtx_sensors() or self.render_mode == "rgb_array"
        self.transport_replay = torch.zeros(num_envs,dtype=torch.bool,device=self.device)
        from .recent_metrics import RecentEpisodes
        self.recent_episodes = RecentEpisodes(4096,self.device)
        self.start_bank = None
        self.bank_collector = None
        if self.settings.start_bank:
            from .stage_bank import StageStartBank
            self.start_bank=StageStartBank(self.settings.start_bank,self.settings,self.device)
            if self.settings.attachment_version==4:
                import hashlib
                from pathlib import Path
                if self.start_bank.robot_usd_sha256!=hashlib.sha256(Path(self.robot_usd).read_bytes()).hexdigest():
                    raise ValueError('Stage bank current robot USD mismatch')
        self.stem_inverse_inertia = ([torch.linalg.inv(f.data.default_inertia.to(self.device).reshape(-1,3,3)) for f in self.fruits]
            if self.settings.attachment_version == 4 and self.settings.stem_response_version >= 2 else None)
        self._initialized = True

    def _setup_scene(self):
        s = self.settings
        self.robot = Articulation(ArticulationCfg(
            prim_path="/World/envs/env_.*/Robot",
            spawn=sim_utils.UsdFileCfg(usd_path=self.robot_usd,
                activate_contact_sensors=True,
                articulation_props=sim_utils.ArticulationRootPropertiesCfg(
                    enabled_self_collisions=True, solver_position_iteration_count=32 if s.contact_solver_refine else 12, solver_velocity_iteration_count=16 if s.contact_solver_refine else 4)),
            init_state=ArticulationCfg.InitialStateCfg(pos=self.robot_root_pose[0],rot=self.robot_root_pose[1]),
            actuators={"arm": ImplicitActuatorCfg(joint_names_expr=["arm_2_(?!gripper$).*"],
                         stiffness=25.0, damping=1.5, effort_limit_sim=2.0, velocity_limit_sim=1.2),
                       "gripper": ImplicitActuatorCfg(joint_names_expr=["arm_2_gripper"],
                         stiffness=s.gripper_stiffness, damping=s.gripper_damping, effort_limit_sim=s.gripper_effort, velocity_limit_sim=1.5)}))
        self.scene.articulations["robot"] = self.robot
        self.fruits = []
        self.fruit_collision_hulls = []
        fruit_assets = {}
        self.fruit_colors = list(self.fruit_color_override) if self.fruit_color_override is not None else fruit_colors(s.num_fruits, s.sequence)
        self.tips_np = []
        for i in range(s.num_fruits):
            color = "Red" if s.sequence and s.random_colors else self.fruit_colors[i]
            if color not in fruit_assets:
                fruit_assets[color] = fruit_asset(s, color, cache=self.fruit_asset_cache)
            usd, tip = fruit_assets[color]
            self.fruit_collision_hulls.append(torch.as_tensor(collision_hull_points(usd),device=self.device))
            self.tips_np.append(tip)
            self.attachment_np = self.tips_np[0]
            fruit = RigidObject(RigidObjectCfg(prim_path=f"/World/envs/env_.*/Fruit_{i}",
                spawn=sim_utils.UsdFileCfg(usd_path=usd, activate_contact_sensors=True,
                    rigid_props=sim_utils.RigidBodyPropertiesCfg(max_linear_velocity=3.0, max_angular_velocity=20.0,
                        linear_damping=0.0, angular_damping=0.02, disable_gravity=False,
                        **(dict(solver_position_iteration_count=32,solver_velocity_iteration_count=16) if s.contact_solver_refine else {})),
                    collision_props=sim_utils.CollisionPropertiesCfg(contact_offset=.001, rest_offset=0.0)),
                init_state=RigidObjectCfg.InitialStateCfg(pos=(.5, -.3, .9))))
            self.fruits.append(fruit)
            self.scene.rigid_objects[f"fruit_{i}"] = fruit
        tree = sim_utils.UsdFileCfg(usd_path=str(ASSETS / "Tree_01.usdc"), scale=s.tree_scale)
        tree.func("/World/envs/env_0/Tree", tree, translation=s.tree_position)
        if self.visual_scene['version'] == 'legacy' and s.background == "grove":
            for row in range(3):
                for column in range(5):
                    tree.func(f"/World/envs/env_0/BackgroundTree_{row}_{column}",tree,
                        translation=(1.05+row*.32, s.tree_position[1]+(column-2)*.34, .04*(column%2)))
        trunk = sim_utils.CylinderCfg(radius=.012, height=1.10, collision_props=sim_utils.CollisionPropertiesCfg(),
                                      visual_material=sim_utils.PreviewSurfaceCfg(diffuse_color=(.17,.12,.04)))
        trunk.func("/World/envs/env_0/TrunkCollision", trunk,
                   translation=(s.tree_position[0], s.tree_position[1], .55))
        ground = sim_utils.GroundPlaneCfg()
        ground.func("/World/Ground", ground)
        if self.visual_scene['version'] != 'legacy':
            from .visual_scene import spawn, gray_ground
            # This scene already uses the original policy frame, including when
            # the current side-mounted robot is transformed as a whole.
            # Keep the physical tree/trunk and attachment anchor points intact.
            world_from_crop=np.eye(4)
            world_from_crop[:3,3]=(s.region_origin[0],s.region_origin[1],0.)
            self.visual_scene=spawn(self.sim.stage,'/World/envs/env_0/GreenhouseVisual',world_from_crop)
            gray_ground(self.sim.stage)
        self.fixed_path = find_body_path(self.sim.stage, "arm_2_gripper_link")
        self.moving_path = find_body_path(self.sim.stage, "arm_2_moving_jaw_so101_v1_link")
        # Imported URDF materials can override the scene default. Bind explicitly.
        material = sim_utils.RigidBodyMaterialCfg(static_friction=s.grip_friction,
            dynamic_friction=s.dynamic_friction,restitution=s.restitution,friction_combine_mode="average",
            compliant_contact_stiffness=s.contact_stiffness,compliant_contact_damping=s.contact_damping)
        material.func("/World/GripMaterial",material)
        self.material_colliders = []
        for path in (self.fixed_path,self.moving_path):
            self.material_colliders += bind_verified_material(self.sim.stage, path.replace("env_.*","env_0"),"/World/GripMaterial")
        fruit_material='/World/GripMaterial'
        if s.contact_stiffness:
            # Grip compliance experiment must not turn fruit-box contact soft.
            fruit_material='/World/FruitMaterial'
            rigid_material=sim_utils.RigidBodyMaterialCfg(static_friction=s.grip_friction,
                dynamic_friction=s.dynamic_friction,restitution=s.restitution,friction_combine_mode='average')
            rigid_material.func(fruit_material,rigid_material)
        for i in range(s.num_fruits):
            self.material_colliders += bind_verified_material(self.sim.stage, f"/World/envs/env_0/Fruit_{i}",fruit_material)
        filters = [f"/World/envs/env_.*/Fruit_{i}" for i in range(s.num_fruits)]
        self.fixed_contact = ContactSensor(ContactSensorCfg(prim_path=self.fixed_path,
            filter_prim_paths_expr=filters, history_length=1, update_period=0.0))
        self.moving_contact = ContactSensor(ContactSensorCfg(prim_path=self.moving_path,
            filter_prim_paths_expr=filters, history_length=1, update_period=0.0))
        self.scene.sensors["fixed_contact"] = self.fixed_contact
        self.scene.sensors["moving_contact"] = self.moving_contact
        parent = self.fixed_path.rsplit("/", 1)[0]
        self.arm_contact = ContactSensor(ContactSensorCfg(
            prim_path=parent+"/arm_2_(?!gripper_link$|moving_jaw_so101_v1_link$).*",
            history_length=1, update_period=0.0))
        self.scene.sensors["arm_contact"] = self.arm_contact
        if self.use_cameras:
            from scipy.spatial.transform import Rotation
            from .kinematics import ArmKinematics
            kin = ArmKinematics(CACHE / "harvest_training.urdf")
            tf = np.linalg.inv(kin.fk(np.zeros(6), "arm_2/gripper_link")) @ kin.fk(
                np.zeros(6), "arm_2/wrist_camera_color_optical_frame")
            q = Rotation.from_matrix(tf[:3,:3]).as_quat()
            self.camera = TiledCamera(TiledCameraCfg(prim_path=self.fixed_path + "/StudentCamera",
                update_period=s.physics_dt*s.decimation, height=96, width=128,
                data_types=["rgb"], spawn=sim_utils.PinholeCameraCfg(focal_length=1.93,
                    horizontal_aperture=3.68, clipping_range=(.015, 4.0)),
                offset=TiledCameraCfg.OffsetCfg(pos=tuple(tf[:3,3]), rot=tuple(q[[3,0,1,2]]), convention="ros")))
            self.scene.sensors["wrist_rgb"] = self.camera
        self.scene.clone_environments(copy_from_source=False)
        self.scene.filter_collisions(global_prim_paths=["/World/Ground"])
        light = sim_utils.DomeLightCfg(intensity=2200.0, color=(.85,.85,.85))
        light.func("/World/Light", light)
        # Connector visualization is separate from spring physics; updated on reset.
        self.stems = VisualizationMarkers(VisualizationMarkersCfg(prim_path="/Visuals/StemConnectors",
            markers={"stem": sim_utils.CylinderCfg(radius=1.0, height=1.0,
                visual_material=sim_utils.PreviewSurfaceCfg(diffuse_color=(.13,.25,.04)))}))
        meta = json.loads((ASSETS / "manifest.json").read_text())["Tree_01"]
        self.stem_points_np = np.array(meta["stem_points"])[::20] * s.tree_scale + s.tree_position

    def _t(self, tensor):
        return tensor[torch.arange(self.num_envs,device=self.device), self.target_index]

    def _target_fruit(self):
        if self.settings.num_fruits == 1 or (not self.settings.sequence and self.settings.target_mode != "external"):
            return self.fruits[0]
        names = ("root_link_pos_w", "root_link_quat_w", "root_com_pos_w", "root_com_lin_vel_w", "root_com_ang_vel_w")
        data = {name:self._t(torch.stack([getattr(f.data,name) for f in self.fruits],dim=1)) for name in names}
        return SimpleNamespace(data=SimpleNamespace(**data))

    def _target_contact(self, sensor):
        return self._t(sensor.data.force_matrix_w[:,0])

    def _native_recovery_enabled(self):
        return (self.settings.native_detach_recovery and self.settings.native_grasp_grace
                and self.settings.attachment_version == 3 and self.settings.task in ("pull", "harvest", "transport", "place"))

    def _consume_joint_breaks(self):
        if self.joint_attachments is None:
            return
        events = self.joint_attachments.consume()
        if not events:
            return
        # Group by fruit: compute tensors once per fruit, not once per broken joint.
        grouped = {}
        for env_id, fruit_id in events:
            grouped.setdefault(fruit_id, set()).add(env_id)
        tcp, quat = self._tcp()
        for fruit_id, ids in grouped.items():
            ids = torch.tensor(sorted(ids), device=self.device, dtype=torch.long)
            self.attached[ids,fruit_id] = False
            fruit = self.fruits[fruit_id]
            tip = self.fruit_tips[fruit_id].expand(len(ids),-1)
            self.break_displacement[ids,fruit_id] = (fruit.data.root_link_pos_w[ids]
                + quat_apply(fruit.data.root_link_quat_w[ids],tip)-self.anchors[ids,fruit_id])
            center = self._grasp_center(fruit)[ids]
            distance = (center-tcp[ids]).norm(dim=-1)
            contact = bilateral_contact(self.fixed_contact.data.force_matrix_w[ids,0,fruit_id],
                self.moving_contact.data.force_matrix_w[ids,0,fruit_id],distance,self.settings)
            qualified = qualified_grasp(contact,distance,self.settings)
            provisional = (contact & (distance <= max(.015,self.settings.grasp_center_tolerance))
                           if self._native_recovery_enabled() else qualified)
            target = self.target_index[ids] == fruit_id
            valid = self.has_grasped[ids] & qualified & target
            valid_ids = ids[valid]
            self.detach_event[valid_ids] = True
            self.valid_detach[valid_ids] = True
            if self.settings.native_grasp_grace:
                pending = ~valid & provisional & target
                pending_ids = ids[pending]
                self.pending_detach[pending_ids] = True
                self.pending_detach_time[pending_ids] = 0
                relative = quat_apply(quat_conjugate(quat[ids]),center-tcp[ids])
                self.pending_detach_relative[pending_ids] = relative[pending]

    def close(self):
        if getattr(self,"joint_attachments",None) is not None:
            self.joint_attachments.close()
        super().close()

    def _tcp(self):
        pos = self.robot.data.body_link_pos_w[:, self.tcp_body]
        quat = self.robot.data.body_link_quat_w[:, self.tcp_body]
        return pos + quat_apply(quat, self.tcp_offset), quat

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

    def _set_stem_wrench(self, fruit, index, force, torque):
        # This composer belongs exclusively to the attachment/hold load. Refresh
        # its cached world-to-body pose every physics step, including after reset.
        if self.settings.attachment_version == 4 and self.settings.stem_response_version >= 3:
            fruit.permanent_wrench_composer.reset()
        self.applied_stem_force[:,index] = force
        self.applied_stem_torque[:,index] = torque
        fruit.permanent_wrench_composer.set_forces_and_torques(
            forces=force[:,None], torques=torque[:,None], is_global=True)

    def _apply_action(self):
        self.robot.set_joint_position_target(self.targets, joint_ids=self.jids)
        s = self.settings
        self._consume_joint_breaks()
        for i, fruit in enumerate(self.fruits):
            tip = torch.tensor(self.tips_np[i],device=self.device,dtype=torch.float32).expand(self.num_envs,-1)
            pos = fruit.data.root_link_pos_w + quat_apply(fruit.data.root_link_quat_w, tip)
            if s.attachment_version == 3:
                force = torch.zeros(self.num_envs,1,3,device=self.device)
                if s.task == "hold":
                    force[:,0,0] = s.hold_force*self.has_grasped*self.attached[:,i]*(self.target_index == i)
                self._set_stem_wrench(fruit, i, force[:,0], torch.zeros_like(force[:,0]))
                continue
            lever = pos - fruit.data.root_com_pos_w
            vel = fruit.data.root_com_lin_vel_w + torch.linalg.cross(fruit.data.root_com_ang_vel_w, lever)
            previous = self.attached[:, i].clone()
            world_inverse_inertia = None
            if self.stem_inverse_inertia is not None:
                rotation = matrix_from_quat(fruit.data.root_link_quat_w)
                world_inverse_inertia = rotation @ self.stem_inverse_inertia[i] @ rotation.transpose(-1,-2)
            force, torque, attached, timer, load = attachment_wrench(
                pos - self.anchors[:, i], vel, lever, s, previous,
                self.break_timer[:, i], self.physics_dt, self.threshold[:, i], world_inverse_inertia)
            # Restoring orientation is an explicitly approximate compliant stem, not a rigid constraint.
            quat = quat_mul(fruit.data.root_link_quat_w, quat_conjugate(self.rest_quat[:,i]))
            restoring = -(s.angular_k * 2 * quat[:, 1:] * torch.sign(quat[:, :1])
                          + s.angular_d * fruit.data.root_com_ang_vel_w)
            if world_inverse_inertia is not None:
                eye = torch.eye(3,device=self.device)
                damping = torch.linalg.solve(eye + self.physics_dt*s.angular_d*world_inverse_inertia,
                    (s.angular_d*fruit.data.root_com_ang_vel_w)[...,None]).squeeze(-1)
                restoring = -s.angular_k*2*quat[:,1:]*torch.sign(quat[:,:1]) - damping
            torque += restoring * attached[:, None]
            self.attached[:, i] = attached
            self.break_timer[:, i] = timer
            self.load[:, i] = load * attached
            if s.task == "hold":
                # A real external load, not a grasp weld. Remains active after slip until reset.
                force[:,0] += s.hold_force * self.has_grasped * attached * (self.target_index == i)
            # Composer accepts torch arrays in supported Isaac Lab builds.
            self._set_stem_wrench(fruit, i, force, torque)
            broke = previous & ~attached
            self.break_duration[broke,i] = timer[broke]
            self.break_load[broke,i] = load[broke]
            self.break_displacement[broke,i] = (pos-self.anchors[:,i])[broke]
            pulling = valid_pull(pos-self.anchors[:,i],s)
            tcp,_ = self._tcp()
            instant_grip = bilateral_contact(
                self._target_contact(self.fixed_contact),
                self._target_contact(self.moving_contact),
                torch.linalg.vector_norm(self._grasp_center(fruit)-tcp,dim=-1),s)
            instant_grip = qualified_grasp(instant_grip,
                torch.linalg.vector_norm(self._grasp_center(fruit)-tcp,dim=-1),s)
            selected_break = broke & (self.target_index == i)
            evidence = torch.stack((self.has_grasped.float(),instant_grip.float(),pulling.float(),
                torch.linalg.vector_norm(self._grasp_center(fruit)-tcp,dim=-1),
                self._target_contact(self.fixed_contact).norm(dim=-1),
                self._target_contact(self.moving_contact).norm(dim=-1)),dim=-1)
            self.break_evidence[selected_break] = evidence[selected_break]
            self.detach_event |= broke & self.has_grasped & instant_grip & pulling & (self.target_index == i)
            self.valid_detach |= self.detach_event
            if s.spring_grasp_grace and s.task=='harvest':
                # Only the selected fruit already captured at break can be checked.
                from .logic import captured_break_candidate
                candidate=captured_break_candidate(selected_break,self.valid_detach,instant_grip,
                    self.has_grasped,s.captured_break_grace)
                self.pending_detach |= candidate
                self.pending_detach_time[candidate]=0
                self.pending_detach_age[candidate]=0
                _,tcp_quat=self._tcp()
                relative=quat_apply(quat_conjugate(tcp_quat),self._grasp_center(fruit)-tcp)
                self.pending_detach_relative[candidate]=relative[candidate]
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

    def _get_rewards(self):
        s = self.settings
        fruit = self._target_fruit().data.root_link_pos_w - self.scene.env_origins
        box = torch.tensor([.40, 0., .80], device=self.device)
        box_dist = torch.linalg.vector_norm(fruit-box, dim=-1)
        reward = (.5 * torch.exp(-12*self.distance) * ~self.valid_detach + .5*self.grip.float()) * self.step_dt
        if s.reward_version == 2:
            tcp, quat = self._tcp()
            local_error = quat_apply(quat_conjugate(quat), self._target_fruit().data.root_link_pos_w-tcp)
            reward = grasp_shaping(self.previous_distance, self.distance, local_error,
                self.previous_gripper_q, self.robot.data.joint_pos[:,self.jids[-1]],
                self.grip, self.grip_time, self.step_dt) * ~self.valid_detach
        if s.reward_version in (3, 4, 5, 6, 7, 8):
            orientation_allowed = None
            if s.grasp_orientation == "horizontal":
                error, aligned = self._grasp_orientation()
                required = ~self.has_grasped & self._t(self.attached)
                orientation_allowed = ~required | aligned
            if s.entry_first_grasp:
                orientation_allowed=self.entry_inside if orientation_allowed is None else orientation_allowed & self.entry_inside
            reward = centered_grasp_shaping(self.previous_distance, self.distance,
                self.previous_gripper_q, self.robot.data.joint_pos[:,self.jids[-1]],
                self.raw_grip, self.grip_time, self.step_dt, s, orientation_allowed) * ~self.valid_detach
            if s.grasp_orientation == "horizontal":
                # Discounted potential progress; no bonus for loitering or early failure.
                terminal = self.success | self.failure | (self._target_elapsed_steps() >= self.max_episode_length-1)
                potential = s.grasp_orientation_weight*(1-error.square())*torch.exp(-self.distance/.10)
                potential = torch.where(required & ~terminal, potential, torch.zeros_like(potential))
                reward += .99*potential-self.previous_orientation_potential
        if s.entry_first_grasp:
            from .entry_grasp import entry_cost
            target=self._target_fruit()
            tip=target.data.root_link_pos_w+quat_apply(target.data.root_link_quat_w,self.fruit_tips[self.target_index])
            displacement=(tip-self._t(self.anchors)).norm(dim=-1)
            cost=entry_cost(self.entry_inside,self._t(self.attached),self.distance,
                self._target_contact(self.fixed_contact).norm(dim=-1),self._target_contact(self.moving_contact).norm(dim=-1),
                -self.actions[:,-1],displacement,self.entry_gap,s.diameter,self.step_dt)
            reward-=cost
            self.last_diagnostics['preentry_cost']=cost
            if s.entry_capture_shaping:
                from .entry_grasp import capture_cost
                capture_penalty=capture_cost(self._t(self.attached),self.has_grasped,self.distance,
                    self._target_contact(self.fixed_contact).norm(dim=-1),
                    self._target_contact(self.moving_contact).norm(dim=-1),displacement,self.step_dt)
                reward-=capture_penalty
                self.last_diagnostics['entry_capture_cost']=capture_penalty
        if s.reward_version == 4 and s.task in ("pull", "harvest", "transport", "place"):
            retreat = self.pull_start_x-self._grasp_center(self._target_fruit())[:,0]
            reward, self.pull_best_retreat = pull_stage_shaping(reward, self.has_grasped,
                self._t(self.attached), self.grip, retreat, self.pull_best_retreat, self.step_dt)
        if s.reward_version in (5, 6, 7, 8) and s.task in ("pull", "harvest", "transport", "place"):
            reward = separation_stage_shaping(reward, self.has_grasped, self._t(self.attached), self.step_dt)
        if s.pull_progress_reward and s.task=='pull':
            target=self._target_fruit()
            tip=target.data.root_link_pos_w+quat_apply(target.data.root_link_quat_w,self.fruit_tips[self.target_index])
            axis=torch.tensor(s.tension_axis,device=self.device);axis=axis/axis.norm()
            extension=((tip-self._t(self.anchors))*axis).sum(-1)
            reward,self.pull_best_retreat=tensile_progress_reward(reward,self.has_grasped,
                self._t(self.attached),self.grip & (self.slip<s.max_slip),extension,
                self._t(self.load),self._t(self.threshold),self.pull_best_retreat,self.step_dt)
            timed_out=self._target_elapsed_steps()>=self.max_episode_length-1
            reward-=5*(timed_out & ~self.success & ~self.failure).float()
        if s.task == "pull" and s.pull_direction_shaping:
            target=self._target_fruit()
            tip=target.data.root_link_pos_w+quat_apply(target.data.root_link_quat_w,self.fruit_tips[self.target_index])
            cost=pull_direction_cost(tip-self._t(self.anchors),s.tension_axis,
                                     self.has_grasped,self._t(self.attached),self.step_dt)
            reward-=cost
            self.last_diagnostics["pull_direction_cost"]=cost
        if s.reward_version != 8:
            reward += 3*self.grasp_event.float()
        if s.task == "hold":
            reward += self.step_dt * (self.loaded_time > 0).float()
        if s.task in ("pull", "harvest", "transport", "place"):
            if s.reward_version != 8:
                reward += 5*self.detach_event.float()
            if s.task not in ("harvest","transport","place") or s.reward_version < 6:
                reward += self.step_dt * (self.detached_time > 0).float()
            if s.task in ("harvest","transport","place") and s.reward_version < 6:
                reward += self.valid_detach * (1.0-torch.tanh(5*box_dist)) * self.step_dt
            tip_pos = self._target_fruit().data.root_link_pos_w+quat_apply(self._target_fruit().data.root_link_quat_w,self.fruit_tips[self.target_index])
            pull = ((self._t(self.anchors)[:,0]-tip_pos[:,0])/s.break_distance).clamp(0,1)
            if s.reward_version < 4:
                reward += .5*self._t(self.attached)*self.grip*pull*self.step_dt
        if s.task in ("harvest","transport","place") and s.reward_version >= 6:
            distance = torch.linalg.vector_norm(fruit-placement_target(s,self.device),dim=-1)
            eligible = self.valid_detach & self.has_retained & self.grip & ~self._t(self.attached)
            placing, self.place_best_distance, self.release_paid, self.place_best_time = harvest_place_shaping(
                distance, self.place_best_distance, eligible, self.released_in_box,
                self.release_paid, self.place_time, self.place_best_time, self.step_dt, s.place_hold_s,
                progress_scale=0.0 if s.reward_version == 8 else 10.0)
            if s.reward_version == 8:
                first = eligible & ~self.transport_started
                self.transport_origin[first] = distance[first]
                self.transport_started |= eligible
                terminal = self.failure | self.success | self.collection_event | (self._target_elapsed_steps() >= self.max_episode_length-1)
                shaping,self.transport_potential = transport_potential_step(
                    distance,self.transport_origin,self.transport_potential,
                    self.transport_started & (eligible | self.valid_release),terminal)
                placing += shaping
            reward += placing - .2*self.step_dt*self.valid_detach
            if s.reward_version >= 7:
                best = torch.maximum(self.stop_best_time,self.stop_time.clamp(0,s.release_stop_s))
                reward += 2*(best-self.stop_best_time)/s.release_stop_s
                self.stop_best_time = best
        reward += 20*(self.success | self.collection_event).float()
        if s.reward_version == 8:
            timed_out = (self._target_elapsed_steps() >= self.max_episode_length-1) & ~(self.success | self.collection_event)
            reward += harvest_stage_bonus(self.grasp_event,self.detach_event,self.failure,timed_out)
        else:
            reward -= 5*self.failure.float()
        reward -= self.step_dt * self.has_grasped * self.grip * (self.slip/self.settings.max_slip).clamp(0,2)
        reward -= self.step_dt * self.arm_collision.float()
        reward -= self.step_dt*(.01*self.actions.square().sum(-1)
                              + .02*(self.actions-self.previous_actions).square().sum(-1) + .02)
        if s.task == "pull" and s.pull_recovery_shaping:
            terminal = self.success | self.failure | (self._target_elapsed_steps() >= self.max_episode_length-1)
            recovery,self.pull_recovery_potential = pull_recovery_step(
                self.pull_recovery_potential,self.distance,self.has_grasped,self._t(self.attached),terminal)
            reward += recovery
        self.extras["log"] = {"Perf/reset_wall_s":torch.tensor(0.,device=self.device), "Perf/reset_envs":torch.tensor(0.,device=self.device), "Task/grip": self.grip.float().mean(),
            "Task/distance": self.distance.mean(), "Task/attached": self._t(self.attached).float().mean(),
            "Task/slip_m": (self.slip*self.has_grasped).mean(),
            "Task/loaded_hold_s": self.loaded_time.mean(), "Task/detached_hold_s": self.detached_time.mean(),
            "Task/arm_collision": self.arm_collision.float().mean(),
            "Task/success_step": self.success.float().mean(), "Task/failure_step": self.failure.float().mean()}
        self.extras["log"].update({"Diagnostic/"+name: value.float().mean()
            for name, value in self.last_diagnostics.items()})
        if s.pull_progress_reward:
            self.extras["log"]["Task/pull_progress_best"] = self.pull_best_retreat.mean()
        if s.task == "pull":
            pulling = self.has_grasped & self._t(self.attached)
            self.extras["log"]["Task/pull_attached_contact_loss_rate"] = (pulling & ~self.grip).sum() / pulling.sum().clamp_min(1)
            self.extras["log"]["Task/pull_attached_envs"] = pulling.sum()
        if s.reward_version >= 7 and s.task in ('harvest','transport','place'):
            f=self._target_fruit();tcp,_=self._tcp()
            # previous_tcp was recorded before this control step.
            stop_masks={
                'zone':above_box(f.data.root_link_pos_w-self.scene.env_origins,f.data.root_link_quat_w,s),
                'fruit_slow':f.data.root_com_lin_vel_w.norm(dim=-1)<=s.release_speed,
                'tcp_slow':(tcp-self.previous_tcp).norm(dim=-1)/self.step_dt<=s.release_speed,
                'angular_slow':self.stop_angular_slow,
                'stable':self.grip & self.has_grasped & (self.slip<s.max_slip)}
            for key,value in stop_masks.items():self.extras['log']['Stop/'+key]=value.float().mean()
            self.extras['log']['Stop/all']=torch.stack(list(stop_masks.values())).all(0).float().mean()
        self.extras["log"].update(self.recent_episodes.metrics())
        total = max(1, self.episode_metrics["episodes"])
        self.extras["log"].update({f"Episode/{key}_rate": torch.tensor(self.episode_metrics[key]/total,device=self.device)
                                  for key in ("success","grasp","detach","failure")})
        return reward

    def proprio(self):
        q = self.robot.data.joint_pos[:, self.jids]
        qd = self.robot.data.joint_vel[:, self.jids]
        return torch.cat((2*(q-self.lower)/(self.upper-self.lower)-1, qd/1.5, self.actions), dim=-1)

    def _advance_target(self):
        if not self.settings.sequence or not hasattr(self,"pending_next"):
            return
        ids = self.pending_next.nonzero().flatten()
        if not len(ids):
            return
        tcp,_ = self._tcp()
        positions = torch.stack([f.data.root_link_pos_w for f in self.fruits],dim=1)
        target, _ = next_target(positions,tcp,self.ripe,self.collected)
        self.target_index[ids] = target[ids]
        self.target_start_step[ids] = self.episode_length_buf[ids]
        for name in ("entry_inside","transport_started","transport_origin","transport_potential","pending_detach_age","pending_detach_lost","pending_detach","pending_detach_time","pending_detach_relative","pending_detach_rejected","grip_time","place_time","loaded_time","detached_time","grasp_relative","slip",
                     "pull_start_x","pull_best_retreat","pull_recovery_potential","stop_time","stop_best_time","place_best_time",
                     "release_target_unloaded","release_intent","release_intent_age","release_intent_tcp","release_intent_arm","release_armed","valid_release","bad_release","release_paid","has_grasped",
                     "transport_preload_latched","transport_preload_origin","squeeze_active","valid_detach","has_retained","grip","raw_grip","grasp_event","detach_event"):
            getattr(self,name)[ids] = 0
        self.place_best_distance[ids] = float("inf")
        self.pending_next[ids] = False

    def cancel_target(self):
        """Latch cancellation; simulator stepping stops until explicit reset.

        This is not a real robot stop controller. A hardware adapter must hold
        the joints/gripper safely and acknowledge its own cancellation.
        """
        if self.settings.target_mode != "external" or self.assignment_status != "RUNNING":
            raise RuntimeError("Cancellation requires an active external assignment")
        self.assignment_status = "CANCELLED"

    def assign_target(self, fruit_index):
        """Single-env external slot API; caller maps persistent fruit IDs to slots.

        Does not move/reset bodies. FAILED/TIMED_OUT require reset/recovery.
        After SUCCEEDED caller must confirm shared-space clearance before assignment.
        """
        if self.settings.target_mode != "external":
            raise RuntimeError("assign_target requires external mode")
        if self.assignment_status not in ("WAIT_TARGET", "SUCCEEDED"):
            raise RuntimeError("Cannot replace an active/failed assignment; reset or recover first")
        if not isinstance(fruit_index,int) or not 0 <= fruit_index < self.settings.num_fruits:
            raise ValueError("Invalid fruit slot")
        if not bool(self.ripe[0,fruit_index] & ~self.collected[0,fruit_index] & self.attached[0,fruit_index]):
            raise ValueError("Target must be ripe, uncollected and attached")
        self.target_index[0] = fruit_index
        self.target_start_step[0] = self.episode_length_buf[0]
        for name in ("entry_inside","transport_started","transport_origin","transport_potential","pending_detach_age","pending_detach_lost","pending_detach","pending_detach_time","pending_detach_relative","pending_detach_rejected","grip_time","place_time","loaded_time","detached_time","grasp_relative","slip",
                     "pull_start_x","pull_best_retreat","pull_recovery_potential","stop_time","stop_best_time","place_best_time",
                     "release_target_unloaded","release_intent","release_intent_age","release_intent_tcp","release_intent_arm","release_armed","valid_release","bad_release","release_paid","has_grasped",
                     "transport_preload_latched","transport_preload_origin","squeeze_active","valid_detach","has_retained","grip","raw_grip","grasp_event","detach_event",
                     "success","failure","collection_event","pending_next"):
            if hasattr(self,name):
                getattr(self,name).zero_()
        self.place_best_distance.fill_(float("inf"))
        self.actions.zero_()
        self.previous_actions.zero_()
        self.assignment_status = "RUNNING"
        return self._get_observations()

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

    def student_observations(self):
        if not self.use_cameras:
            raise RuntimeError("Student requires --enable_cameras")
        # No target pose, attachment state, force, success flag or privileged state here.
        return self.camera.data.output["rgb"][..., :3], self.proprio()

    def _reset_idx(self, env_ids):
        started=time.perf_counter()
        self._reset_impl(env_ids)
        if getattr(self,"_initialized",False):
            log=self.extras.setdefault("log",{})
            log["Perf/reset_wall_s"]=torch.tensor(time.perf_counter()-started,device=self.device)
            log["Perf/reset_envs"]=torch.tensor(self.num_envs if env_ids is None else len(env_ids),device=self.device)

    def _reset_impl(self, env_ids):
        if env_ids is None:
            env_ids = self.robot._ALL_INDICES
        if not getattr(self, "_initialized", False):
            super()._reset_idx(env_ids)
            return
        self.applied_stem_force[env_ids] = 0
        self.applied_stem_torque[env_ids] = 0
        active = env_ids[self.episode_length_buf[env_ids] > 0]
        finished=active[(self.success | self.failure | self.reset_time_outs)[active]]
        self.recent_episodes.add(self.success[finished],self.failure[finished],self.transport_replay[finished])
        if self.bank_collector is not None:
            self.bank_collector.capture(self,active)
        self.episode_metrics["episodes"] += len(active)
        for name, values in (("success", self.success), ("grasp", self.has_grasped),
                             ("detach", self.valid_detach), ("failure", self.failure)):
            self.episode_metrics[name] += int(values[active].sum())
        for prefix, mask in (("easy", self.easy_episode[active]), ("home", ~self.easy_episode[active])):
            self.episode_metrics[prefix+"_episodes"] += int(mask.sum())
            self.episode_metrics[prefix+"_success"] += int((mask & self.success[active]).sum())
        super()._reset_idx(env_ids)
        n = len(env_ids)
        q = self.robot.data.default_joint_pos[env_ids].clone()
        q[:, self.jids] = self.home
        self.robot.write_joint_state_to_sim(q, torch.zeros_like(q), env_ids=env_ids)
        self.targets[env_ids] = self.home
        self.robot.set_joint_position_target(self.targets[env_ids], joint_ids=self.jids, env_ids=env_ids)
        for array in (self.break_evidence, self.actions, self.previous_actions, self.break_timer, self.break_duration, self.break_load, self.break_displacement, self.grip_time, self.place_time,
                      self.has_grasped, self.valid_detach, self.grip, self.success, self.failure, self.load,
                      self.loaded_time, self.detached_time, self.grasp_relative, self.slip, self.has_retained, self.squeeze_active,
                      self.pull_start_x, self.pull_best_retreat, self.pull_recovery_potential, self.place_best_time, self.release_paid, self.stop_time, self.stop_best_time, self.release_target_unloaded, self.release_intent, self.release_intent_age, self.release_intent_tcp, self.release_intent_arm, self.release_armed, self.valid_release, self.bad_release):
            array[env_ids] = 0
        self.place_best_distance[env_ids] = float("inf")
        self.assignment_status = "WAIT_TARGET"
        self.target_index[env_ids] = 0
        self.entry_inside[env_ids] = False
        self.transport_replay[env_ids] = False
        self.transport_preload_latched[env_ids] = False
        self.transport_preload_origin[env_ids] = 0
        self.transport_started[env_ids] = False
        self.transport_origin[env_ids] = 0
        self.transport_potential[env_ids] = 0
        self.pending_detach[env_ids] = False
        self.pending_detach_rejected[env_ids] = False
        self.pending_detach_age[env_ids] = 0
        self.pending_detach_lost[env_ids] = 0
        self.pending_detach_time[env_ids] = 0
        self.pending_detach_relative[env_ids] = 0
        self.target_start_step[env_ids] = 0
        self.collected[env_ids] = False
        self.pending_next[env_ids] = False
        self.collection_event[env_ids] = False
        self.attached[env_ids] = True
        self.threshold[env_ids] = self.settings.break_force * (.8+.4*torch.rand(n, self.settings.num_fruits, device=self.device))
        if self.start_bank is not None:
            self.start_bank.restore(self,env_ids)
            return
        # Cache immutable run geometry; key also supports explicit probe setting changes.
        key = (self.settings.diameter,self.settings.curriculum,tuple(self.settings.region_origin),
               tuple(self.settings.region_min),tuple(self.settings.region_max))
        if getattr(self,"_candidate_cache_key",None) != key:
            # Candidate bank is preserved; enforce this run's requested Cartesian bounds.
            # Curriculum keeps fruit at least 9 cm away from reset TCP to avoid spawning inside fingers.
            from .kinematics import ArmKinematics
            home_tcp = torch.tensor(ArmKinematics(CACHE / "harvest_training.urdf").grasp_fk(self.bank_np["home"], self.settings.diameter)[:3,3], device=self.device, dtype=torch.float32)
            distances = torch.linalg.vector_norm(self.points-home_tcp, dim=-1)
            lo = torch.tensor(self.settings.region_origin,device=self.device) + torch.tensor(self.settings.region_min,device=self.device)
            hi = torch.tensor(self.settings.region_origin,device=self.device) + torch.tensor(self.settings.region_max,device=self.device)
            inside = ((self.points >= lo) & (self.points <= hi)).all(-1)
            eligible = (inside & (distances > .09) & (distances < .18+.65*self.settings.curriculum)).nonzero().flatten()
            if eligible.numel() < 2:
                raise RuntimeError("No separated reset candidates")
            self._reset_home_tcp = home_tcp
            self._reset_candidates = self.points[eligible]
            self._candidate_cache_key = key
        home_tcp = self._reset_home_tcp
        # Close/hold curriculum: only at reset, around the open HOME grasp pocket.
        # Ordinary HOME-to-target episodes remain mixed in; no attachment to the hand.
        easy = torch.rand(n, device=self.device) < self.settings.pregrasp_fraction
        self.easy_episode[env_ids] = easy
        picked = []
        for i, fruit in enumerate(self.fruits):
            local = sample_separated(self._reset_candidates,n,picked,self.settings.diameter+.035)
            if i == 0 and self.settings.pregrasp_fraction:
                jitter = (torch.rand(n,3,device=self.device)-.5)*.004
                local = torch.where(easy[:,None], home_tcp+jitter, local)
            picked.append(local)
            state = fruit.data.default_root_state[env_ids].clone()
            state[:, :3] = local+self.scene.env_origins[env_ids]
            state[:, 3:7] = torch.tensor([1.,0.,0.,0.], device=self.device)
            self.rest_quat[env_ids,i] = state[:,3:7]
            state[:, 7:] = 0
            fruit.write_root_state_to_sim(state, env_ids=env_ids)
            fruit.reset(env_ids)
            self.anchors[env_ids, i] = state[:, :3]+torch.tensor(self.tips_np[i],device=self.device,dtype=torch.float32)
        if self.settings.sequence and self.settings.random_colors:
            self.color_ids[env_ids] = sample_color_ids(len(env_ids),self.settings.num_fruits,self.device)
            self.ripe[env_ids] = self.color_ids[env_ids] != 2
            from pxr import UsdGeom
            colors = self.color_ids[env_ids].cpu().tolist()
            for row,e in enumerate(env_ids.tolist()):
                for i,color in enumerate(colors[row]):
                    for code,name in enumerate(("Red","Yellow","Green")):
                        visual = UsdGeom.Imageable(self.sim.stage.GetPrimAtPath(f"/World/envs/env_{e}/Fruit_{i}/Visual_{name}"))
                        visual.GetVisibilityAttr().Set("inherited" if code == color else "invisible")
        if self.settings.sequence:
            tcp,_ = self._tcp()
            positions = torch.stack([f.data.root_link_pos_w for f in self.fruits],dim=1)
            target,_ = (random_target(self.ripe,self.collected) if self.settings.target_mode == "random"
                        else next_target(positions,tcp,self.ripe,self.collected))
            self.target_index[env_ids] = target[env_ids]
        if self.joint_attachments is not None:
            self.joint_attachments.reset(env_ids.tolist(),self.anchors[env_ids].cpu().tolist(),
                [v.tolist() for v in self.tips_np],(torch.full_like(self.threshold[env_ids],float("inf")) if self.settings.lock_attachment
                                                  else self.threshold[env_ids]).cpu().tolist())
        self._draw_stems()

    def _draw_stems(self):
        if not self.visual_updates:
            return
        anchors = (self.anchors-self.scene.env_origins[:,None]).reshape(-1,3)
        points = torch.tensor(self.stem_points_np, device=self.device, dtype=torch.float32)
        idx = torch.cdist(anchors, points).argmin(-1)
        begin = points[idx]+self.scene.env_origins[:,None,:].expand(-1,self.settings.num_fruits,-1).reshape(-1,3)
        tips = []
        for i, fruit in enumerate(self.fruits):
            tip = torch.as_tensor(self.tips_np[i],device=self.device,dtype=torch.float32).expand(self.num_envs,-1)
            tips.append(fruit.data.root_link_pos_w + quat_apply(fruit.data.root_link_quat_w,tip))
        tip_positions = torch.stack(tips,dim=1)
        # Broken connection retracts to its fixed anchor, never follows free fruit.
        end = torch.where(self.attached[...,None],tip_positions,self.anchors).reshape(-1,3)
        anchor = self.anchors.reshape(-1,3)
        midpoint = (anchor+end)/2
        midpoint[:,2] -= .004 * self.attached.reshape(-1).to(midpoint.dtype)
        begin,end = torch.cat((begin,anchor,midpoint)),torch.cat((anchor,midpoint,end))
        direction = end-begin
        length = torch.linalg.vector_norm(direction, dim=-1).clamp_min(1e-6)
        unit = direction/length[:,None]
        # quaternion rotating +Z into connector direction
        rot = torch.stack((1+unit[:,2], -unit[:,1], unit[:,0], torch.zeros_like(length)), dim=-1)
        fallback = torch.zeros_like(rot);fallback[:,1] = 1.
        rot = torch.where((unit[:,2] < -0.999999)[:,None],fallback,rot)
        rot = torch.nn.functional.normalize(rot, dim=-1)
        scale = torch.stack((torch.full_like(length,.002), torch.full_like(length,.002), length), dim=-1)
        self.stems.visualize((begin+end)/2, rot, scale,
                             marker_indices=torch.zeros(len(begin), dtype=torch.long, device=self.device))
