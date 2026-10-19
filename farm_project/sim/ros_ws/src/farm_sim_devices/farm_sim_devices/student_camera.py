"""농장 World 위의 D435 rig. 전달 보정/리맵과 실제 렌더 배열만 사용한다."""
import json
import numpy as np
from scipy.spatial.transform import Rotation


class FarmD435Rig:
    """60Hz physics 뒤 2tick마다 촬영하며 렌더로 물리 시간을 진행하지 않는다."""

    def __init__(self, world: object, device: object, kin: object, config: dict, robot_id: str) -> None:
        from isaacsim.sensors.camera import Camera
        import cv2
        cv2.setNumThreads(1)
        from harvest_sensors.deployment import validate_deployment
        from harvest_sensors.student60_eval_camera_cache import centred_render_spec
        validate_deployment(config)
        self.world, self.device, self.kin, self.config = world, device, kin, config
        self.active = False
        self.cameras = {}
        self.last = {}
        self.sequence = 0
        self.max_fk_error = 0.
        self.start_time = 0.
        self.world_from_robot = self.robot_transform()
        for name, view in config['views'].items():
            self.cameras[name] = {}
            for stream, spec in view['streams'].items():
                width, height, k, _, _ = centred_render_spec(spec)
                camera = Camera(prim_path=f'/World/StudentSensors/{robot_id}/{name}_{stream}',
                    name=f'{robot_id}_student_{name}_{stream}', frequency=30, resolution=(width, height))
                camera.initialize(attach_rgb_annotator=stream != 'depth')
                camera.set_focal_length(24.)
                camera.set_horizontal_aperture(width*24./k[0, 0])
                camera.set_vertical_aperture(height*24./k[1, 1])
                camera.set_clipping_range(config['render_near_m'], config['render_far_m'])
                if stream == 'depth':
                    camera.add_distance_to_image_plane_to_frame()
                if not np.allclose(camera.get_intrinsics_matrix(), k, atol=1e-3):
                    raise ValueError('Student 센서 render K 불일치')
                self.cameras[name][stream] = camera
        # 전달본의 카메라 포함 손목 외형만 연결한다. 기존 질량/충돌/drive는 보존한다.
        self.install_visuals()
        self.update_poses()
        before = float(world.current_time)
        for _ in range(8):
            world.render()
        for name, pair in self.cameras.items():
            for stream, camera in pair.items():
                array = camera.get_depth() if stream == 'depth' else camera.get_rgb()
                print('[student_camera] initial render:', name, stream, None if array is None else np.shape(array), flush=True)
                if array is None or not np.asarray(array).size:
                    raise RuntimeError('Student 초기 렌더 준비 실패: '+name+'/'+stream)
        if abs(float(world.current_time)-before) > 1e-9:
            raise RuntimeError('Student 초기 렌더가 물리 시간을 바꿨습니다.')
        self.set_active(False)

    def install_visuals(self) -> None:
        """전달 CAD와 외형을 현재 TeacherVisuals 구조에 연결한다. 물성은 바꾸지 않는다."""
        import sys
        import xml.etree.ElementTree as ET
        from pxr import Usd, UsdGeom, UsdShade, Sdf, Gf, Vt
        from harvest_rl.settings import ROOT, URDF
        sys.path.insert(0, str(ROOT/'src/smartfarm_description/scripts'))
        from model_geometry import visuals, fk
        stage = self.world.stage
        robot = stage.GetPrimAtPath(self.device.robot_path)
        def physics_properties() -> dict:
            return {str(a.GetPath()): str(a.Get()) for p in Usd.PrimRange(robot)
                if any(str(schema).startswith(('Physics', 'Physx')) for schema in p.GetAppliedSchemas())
                for a in p.GetAttributes() if a.GetName() != 'visibility'}
        before = physics_properties()
        path = self.device._fixed_path
        groups = [stage.GetPrimAtPath(path+'/'+name) for name in ('TeacherVisuals', 'visuals')]
        groups = [p for p in groups if p.IsValid() and p.IsActive()]
        if len(groups) != 1:
            raise ValueError('농장 오른손 visual 그룹을 고유하게 찾을 수 없습니다.')
        UsdGeom.Imageable(groups[0]).CreateVisibilityAttr().Set('invisible')
        material = UsdShade.Material.Define(stage, '/World/StudentSensors/ArmAppearance')
        shader = UsdShade.Shader.Define(stage, '/World/StudentSensors/ArmAppearance/Shader')
        shader.CreateIdAttr('UsdPreviewSurface')
        shader.CreateOutput('surface', Sdf.ValueTypeNames.Token)
        rgba = json.loads((ROOT/'src/harvest_robot/config/arm_appearance.json').read_text())['rgba']
        shader.CreateInput('diffuseColor', Sdf.ValueTypeNames.Color3f).Set(Gf.Vec3f(*rgba[:3]))
        shader.CreateInput('roughness', Sdf.ValueTypeNames.Float).Set(.65)
        material.CreateSurfaceOutput().ConnectToSource(shader.ConnectableAPI(), 'surface')
        for prim in Usd.PrimRange(robot):
            if prim.GetName() in ('TeacherVisuals', 'visuals') and prim.GetParent().GetName().startswith(('arm_1_', 'arm_2_')):
                UsdShade.MaterialBindingAPI.Apply(prim).Bind(material, bindingStrength=UsdShade.Tokens.strongerThanDescendants)
        root = ET.parse(URDF).getroot()
        poses = fk(root, {})
        reference = np.linalg.inv(self.kin.fk(np.zeros(6), 'arm_2/gripper_link'))
        allowed = {'arm_2/gripper_link', 'arm_2/gripper_frame_link', 'arm_2/tool0'}
        allowed |= {link.get('name') for link in root.findall('link') if link.get('name').startswith('arm_2/wrist_camera')}
        for link in list(root.findall('link')):
            if link.get('name') not in allowed:
                root.remove(link)
        group = UsdGeom.Xform.Define(stage, '/World/StudentSensors/WristVisuals')
        self.visual_transform = group.AddTransformOp()
        count = 0
        for name, triangles, colour in visuals(root, URDF, poses):
            points = triangles.reshape(-1, 3) @ reference[:3, :3].T + reference[:3, 3]
            mesh = UsdGeom.Mesh.Define(stage, str(group.GetPath())+f'/Mesh_{count}')
            mesh.CreatePointsAttr(Vt.Vec3fArray.FromNumpy(points.astype(np.float32)))
            mesh.CreateFaceVertexCountsAttr(Vt.IntArray.FromNumpy(np.full(len(triangles), 3, np.int32)))
            mesh.CreateFaceVertexIndicesAttr(Vt.IntArray.FromNumpy(np.arange(len(points), dtype=np.int32)))
            mesh.CreateSubdivisionSchemeAttr('none')
            mesh.CreateDoubleSidedAttr(True)
            mesh.CreateDisplayColorAttr([Gf.Vec3f(*(tuple(colour[:3]) if 'camera' in name else (.06, .06, .065)))])
            count += 1
        if not count or physics_properties() != before:
            raise ValueError('Student 외형 연결 실패 또는 농장 물성 변경')
        print('[student_camera] wrist CAD meshes:', count, 'physics attributes preserved:', len(before), flush=True)

    def robot_transform(self) -> np.ndarray:
        base = self.kin.fk(np.zeros(6), 'arm_2/base_link')
        return self.device.arm_world_transform() @ np.linalg.inv(base)

    def set_active(self, active: bool) -> None:
        self.active = active
        for pair in self.cameras.values():
            for camera in pair.values():
                (camera.resume if active else camera.pause)()
                camera._render_product.hydra_texture.set_updates_enabled(active)
        if active:
            self.sequence = 0
            self.start_time = float(self.world.current_time)
            self.last = {}
            self.max_fk_error = 0.
            self.acquire(self.start_time)

    def update_poses(self) -> tuple[np.ndarray, dict]:
        from harvest_sensors.profile import optical_poses
        from pxr import Gf
        q = self.device.joint_positions()
        self.world_from_robot = self.robot_transform()
        expected = optical_poses(self.kin, q, self.config, self.world_from_robot)
        wrist_fk = self.kin.fk(q, 'arm_2/gripper_link')
        positions, orientations = self.device._pose_view.get_world_poses()
        index = self.device._pose_indices[self.device._fixed_path]
        wrist = np.eye(4)
        wrist[:3, 3] = np.asarray(positions[index])
        wrist[:3, :3] = Rotation.from_quat(np.asarray(orientations[index])[[1, 2, 3, 0]]).as_matrix()
        # 손목 카메라는 실제 rigid body를 따라간다. FK로 실제 팔 pose를 대체하지 않는다.
        actual = {name: dict(pair) for name, pair in expected.items()}
        for stream in actual['right']:
            local = np.linalg.inv(self.world_from_robot @ wrist_fk) @ expected['right'][stream]
            actual['right'][stream] = wrist @ local
        for name, pair in self.cameras.items():
            for stream, camera in pair.items():
                transform = actual[name][stream]
                quat = Rotation.from_matrix(transform[:3, :3]).as_quat()[[3, 0, 1, 2]]
                camera.set_world_pose(transform[:3, 3], quat, camera_axes='ros')
        self.visual_transform.Set(Gf.Matrix4d(wrist.T))
        return q, expected

    def after_frame(self, now: float) -> None:
        if not self.active:
            from pxr import Gf
            positions, orientations = self.device._pose_view.get_world_poses()
            index = self.device._pose_indices[self.device._fixed_path]
            wrist = np.eye(4)
            wrist[:3, 3] = np.asarray(positions[index])
            wrist[:3, :3] = Rotation.from_quat(np.asarray(orientations[index])[[1, 2, 3, 0]]).as_matrix()
            self.visual_transform.Set(Gf.Matrix4d(wrist.T))
            return
        physics_steps = round((now-self.start_time)*60)
        if physics_steps % 2 or (self.last and self.last['rear']['stamp_s'] >= now-1e-8):
            return
        self.acquire(now)

    def acquire(self, now: float) -> None:
        """같은 물리 pose에서 전달본과 동일한 두 렌더 pass 뒤 센서 배열을 읽는다."""
        from harvest_sensors.profile import matrix
        from harvest_sensors.student60_eval_camera_cache import remap_render, centred_render_spec
        from harvest_rl.rgbd_geometry import valid_depth, align_depth_to_color
        q, expected = self.update_poses()
        before = float(self.world.current_time)
        self.world.render()
        self.world.render()
        if abs(float(self.world.current_time)-before) > 1e-9:
            raise RuntimeError('Student 촬영 중 물리 시간이 진행됐습니다.')
        result = {}
        for name, pair in self.cameras.items():
            images, poses, ks, checks = {}, {}, {}, {}
            error = 0.
            for stream, camera in pair.items():
                pos, quat = camera.get_world_pose(camera_axes='ros')
                transform = np.eye(4)
                transform[:3, 3] = np.asarray(pos)
                transform[:3, :3] = Rotation.from_quat(np.asarray(quat)[[1, 2, 3, 0]]).as_matrix()
                error = max(error, float(abs(transform-expected[name][stream]).max()))
                poses[stream] = transform
                spec = self.config['views'][name]['streams'][stream]
                ks[stream] = matrix(spec)
                width, height, expected_k, _, _ = centred_render_spec(spec)
                actual_k = np.asarray(camera.get_intrinsics_matrix())
                if not np.allclose(actual_k, expected_k, atol=1e-3):
                    raise RuntimeError('Student 촬영 중 실제 render K가 바뀌었습니다.')
                checks[stream] = dict(render_wh=[width, height], render_k=actual_k.tolist(), native_k=ks[stream].tolist())
                array = camera.get_depth() if stream == 'depth' else camera.get_rgb()
                if array is None or not np.asarray(array).size:
                    raise RuntimeError('Student 실제 센서 영상이 없습니다: '+name+'/'+stream)
                image = remap_render(np.asarray(array), spec, depth=stream == 'depth')
                if stream == 'ir_right':
                    image = np.rint(image.astype(float) @ [.299, .587, .114]).astype(np.uint8)
                images[stream] = image
            self.max_fk_error = max(self.max_fk_error, error)
            if error > 2e-4:
                raise RuntimeError(f'Student 센서 optical FK 불일치: {name}: {error}')
            raw = images['depth']
            depth, mask = valid_depth(raw, self.config['depth_min_m'], self.config['depth_max_m'])
            relative = np.linalg.inv(poses['rgb']) @ poses['depth']
            aligned = align_depth_to_color(depth, ks['depth'], ks['rgb'], relative, images['rgb'].shape[:2])
            view = self.config['views'][name]
            result[name] = dict(rgb=images['rgb'], ir={k: v for k, v in images.items() if k.startswith('ir_')},
                raw_depth_m=raw, depth_m=depth, depth_valid=mask, aligned_depth_m=aligned,
                world_from_optical=poses, intrinsics=ks, color_from_depth=relative, renderer_checks=checks,
                stamp_s=now, pose_stamp_s=now, frame_number=self.sequence,
                capture_joint_rad=q.tolist(), fk_max_error=error,
                acquisition_sequence=self.sequence, acquisition_time_s=now, acquisition_hz=30,
                clock_id='simulation', ir_model=self.config['sim_ir_model'],
                internal_calibration_verified=view['internal_calibration_verified'],
                mount_calibration_verified=view['mount_calibration_verified'])
        self.last = result
        self.sequence += 1

    def capture(self) -> dict:
        if not self.last:
            raise RuntimeError('Student 실제 카메라 최초 촬영 전입니다.')
        now = float(self.world.current_time)
        return {name: dict(data, image_age_s=now-data['stamp_s']) for name, data in self.last.items()}

    def close(self) -> None:
        self.set_active(False)
        for pair in self.cameras.values():
            for camera in pair.values():
                camera.destroy()
        self.cameras.clear()
