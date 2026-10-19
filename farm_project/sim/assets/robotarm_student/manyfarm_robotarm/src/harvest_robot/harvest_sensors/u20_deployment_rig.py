"""Separate U20 RGB / rear D435 rig. Existing D435 sources are unchanged."""
import numpy as np
from .isaac_rig import StudentD435Rig
from .deployment import PhysicsCaptureClock, expected_poses
from .u20_deployment import validate_u20


class U20DeploymentRig(StudentD435Rig):
    def __init__(self, kin, config, world_from_robot=None, frozen_urdf=None):
        super().__init__(kin, validate_u20(config), world_from_robot)
        self.config = config
        self.kin = kin; self.world_from_robot = world_from_robot; self.frozen_urdf = frozen_urdf
        self.active = False; self.recorder = None; self.clock = None

    def install_physics_hook(self, env):
        if env.num_envs != 1:
            raise ValueError('High resolution Student capture requires one environment')
        self.env = env
        self._install_wrist_visuals()
        self.clock = PhysicsCaptureClock(env.physics_dt, env.step_dt, self.config['fps'])
        original = env.scene.update
        def update(dt):
            original(dt)
            if self.active and self.clock.advance(dt):
                self._acquire()
        # Installed only on this camera-evaluation scene; Teacher class untouched.
        env.scene.update = update

    def _install_wrist_visuals(self):
        from .u20_visuals import install
        from .u20_deployment import reference_urdf
        if self.frozen_urdf is None:
            raise ValueError('Frozen URDF required for both-wrist display replacement')
        self.visual_transforms, self.static_wrist_poses, self.visual_audit = install(
            self.env.sim.stage, reference_urdf(self.config), self.frozen_urdf,
            self.config['wrist_visual_arms'])
        self.visual_transform = self.visual_transforms[2]
        self.visual_mesh_count = self.visual_audit['meshes']
        self.physics_properties_checked = self.visual_audit['physics_properties_checked']

    def follow_wrist(self, position_w, quat_wxyz):
        super().follow_wrist(position_w,quat_wxyz)
        if hasattr(self,'visual_transform'):
            from pxr import Gf
            from scipy.spatial.transform import Rotation
            def cpu(x):return x.detach().cpu().numpy() if hasattr(x,'detach') else np.asarray(x)
            wrist=np.eye(4);wrist[:3,3]=cpu(position_w)
            wrist[:3,:3]=Rotation.from_quat(cpu(quat_wxyz)[[1,2,3,0]]).as_matrix()
            self.visual_transform.Set(Gf.Matrix4d(wrist.T))
            # Left arm is fixed in the frozen Teacher asset; its surviving USD
            # wrist prim supplies the actual pose. It is not an Articulation body.
            for arm,pose in self.static_wrist_poses.items():
                self.visual_transforms[arm].Set(Gf.Matrix4d(pose.T))

    def reset(self):
        self.active = False; self._last.clear(); self.recorder = None
        if self.clock is not None: self.clock.reset()

    def begin_episode(self, recorder):
        self.reset(); self.recorder = recorder; self.active = True
        self._acquire()

    def _acquire(self):
        env = self.env
        q = env.robot.data.joint_pos[0, env.jids].cpu().numpy().copy()
        self.follow_wrist(env.robot.data.body_link_pos_w[0, env.tcp_body],
                          env.robot.data.body_link_quat_w[0, env.tcp_body])
        env.sim.forward()
        # Two render passes propagate a changed Fabric/world sensor pose on the
        # installed Isaac build. Neither advances simulation time/physics.
        env.sim.render(); env.sim.render()
        expected = expected_poses(self.kin, q, self.config, self.world_from_robot)
        for name, pair in self.cameras.items():
            for camera in pair.values(): camera.update(0., force_recompute=True)
            data = self._capture_view(name)
            error = max(float(np.abs(t-expected[name][s]).max()) for s,t in data['world_from_optical'].items())
            if error > 2e-4: raise RuntimeError(f'Acquisition FK mismatch {name}: {error}')
            data.update(frame_number=self.clock.sequence, stamp_s=self.clock.stamp,
                pose_stamp_s=self.clock.stamp, capture_joint_rad=q.tolist(), fk_max_error=error)
            self._last[name] = data
        if self.recorder is not None: self.recorder.append(self._last)

    def update(self, dt):
        if self.active:
            raise RuntimeError('Deployment frames are acquired by the physical-step hook')
        # Static preview only, with its own explicit capture clock.
        super().update(dt)

    def capture(self):
        if not self.active: return super().capture()
        if not self._last: raise RuntimeError('No frame in this episode')
        return {name: dict(data, image_age_s=self.clock.time-data['stamp_s'],
            acquisition_time_s=data['stamp_s'], acquisition_sequence=data['frame_number'],
            clock_id='simulation', acquisition_hz=self.config['fps']) for name,data in self._last.items()}

    def _capture_view(self, name):
        if name != 'right': return super()._capture_view(name)
        from scipy.spatial.transform import Rotation
        from .profile import centred_render_spec, matrix, remap_render
        view=self.config['views'][name];camera=self.cameras[name]['rgb'];spec=view['streams']['rgb']
        data=camera.data;w,h,expected,_,_=centred_render_spec(spec)
        actual=data.intrinsic_matrices[0].cpu().numpy()
        if not np.allclose(actual,expected,atol=1e-3):raise ValueError('U20 renderer K changed')
        pose=np.eye(4);pose[:3,3]=data.pos_w[0].cpu().numpy()
        pose[:3,:3]=Rotation.from_quat(data.quat_w_ros[0].cpu().numpy()[[1,2,3,0]]).as_matrix()
        rgb=remap_render(data.output['rgb'][0,...,:3].cpu().numpy().astype(np.uint8),spec)
        return dict(rgb=rgb,ir={},depth_available=False,aligned_depth_m=np.zeros(rgb.shape[:2],np.float32),
            world_from_optical={'rgb':pose},intrinsics={'rgb':matrix(spec)},color_from_depth=None,
            renderer_checks={'rgb':dict(render_wh=[w,h],render_k=actual.tolist(),native_k=matrix(spec).tolist())},
            internal_calibration_verified=False,mount_calibration_verified=False,ir_model='not_available')
