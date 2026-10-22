"""농장 World 위의 D435 rig. 전달 보정/리맵과 실제 렌더 배열만 사용한다."""
import json
import time
import numpy as np
from scipy.spatial.transform import Rotation


def align_depth_to_color(depth: np.ndarray, kd: np.ndarray, kc: np.ndarray,
                         color_from_depth: np.ndarray, color_shape: tuple) -> np.ndarray:
    """기존 optical-Z 전방 투영/최근접 z-buffer를 큰 행렬곱 없이 계산한다.

    좌표 계산은 원본과 같은 float64, 출력은 float32다. 보간·구멍 채우기나
    측정 캐시를 사용하지 않으며, 정렬 충돌에서는 가장 가까운 깊이를 남긴다.
    """
    h, w = color_shape
    y, x = np.nonzero(np.isfinite(depth) & (depth > 0))
    z = depth[y, x].astype(np.float64)
    xx = (x-kd[0, 2])*z/kd[0, 0]
    yy = (y-kd[1, 2])*z/kd[1, 1]
    t = color_from_depth
    px = xx*t[0, 0] + yy*t[0, 1] + z*t[0, 2] + t[0, 3]
    py = xx*t[1, 0] + yy*t[1, 1] + z*t[1, 2] + t[1, 3]
    pz = xx*t[2, 0] + yy*t[2, 1] + z*t[2, 2] + t[2, 3]
    keep = pz > 0
    px, py, pz = px[keep], py[keep], pz[keep]
    u = np.rint(px/pz*kc[0, 0] + kc[0, 2]).astype(np.int64)
    v = np.rint(py/pz*kc[1, 1] + kc[1, 2]).astype(np.int64)
    keep = (u >= 0) & (u < w) & (v >= 0) & (v < h)
    out = np.full(h*w, np.inf, dtype=np.float32)
    np.minimum.at(out, v[keep]*w+u[keep], pz[keep])
    return np.where(np.isfinite(out), out, 0).reshape(h, w)


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
        self.frame_timings = {}
        self._prepared_capture = None
        self.align_depth = align_depth_to_color
        self.native_processor = None
        try:
            from harvest_sensors.student60_low_latency import (
                align_depth_to_color as compiled_align, process_native, warmup)
        except ImportError:
            # 기존 환경에 선택적 가속기가 없으면 NumPy 경로를 유지한다.
            print('[student_camera] geometry backend: numpy', flush=True)
        else:
            # JIT 최초 컴파일은 제어/촬영 deadline이 시작되기 전에 끝낸다.
            warmup()
            self.align_depth = compiled_align
            self.native_processor = process_native
            print('[student_camera] geometry backend: compiled_cpu', flush=True)
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

    def set_active(self, active: bool, *, reset_capture: bool = True) -> None:
        self.active = active
        self._prepared_capture = None
        for pair in self.cameras.values():
            for camera in pair.values():
                (camera.resume if active else camera.pause)()
                camera._render_product.hydra_texture.set_updates_enabled(active)
        if active:
            now = float(self.world.current_time)
            if reset_capture:
                self.sequence = 0
                self.start_time = now
                self.max_fk_error = 0.
            self.last = {}
            self.acquire(now)

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

    def capture_due(self, now: float) -> bool:
        """기존30Hz 촬영 시각만 판정하며 영상/물리를 진행하지 않는다."""
        physics_steps = round((now-self.start_time)*60)
        return (self.active and physics_steps % 2 == 0
                and (not self.last or self.last['rear']['stamp_s'] < now-1e-8))

    def prepare_capture(self, now: float) -> None:
        """물리 직후 일반 렌더가 예정된 경우 현재 카메라 pose를 먼저 맞춘다."""
        self._prepared_capture = None
        if self.capture_due(now):
            started = time.perf_counter()
            q, expected = self.update_poses()
            self._prepared_capture = (now, q, expected, time.perf_counter()-started)

    def after_frame(self, now: float) -> None:
        self.frame_timings = {}
        if not self.active:
            from pxr import Gf
            positions, orientations = self.device._pose_view.get_world_poses()
            index = self.device._pose_indices[self.device._fixed_path]
            wrist = np.eye(4)
            wrist[:3, 3] = np.asarray(positions[index])
            wrist[:3, :3] = Rotation.from_quat(np.asarray(orientations[index])[[1, 2, 3, 0]]).as_matrix()
            self.visual_transform.Set(Gf.Matrix4d(wrist.T))
            return
        if not self.capture_due(now):
            return
        self.acquire(now)

    def acquire(self, now: float) -> None:
        """같은 물리 pose에서 전달본과 동일한 두 렌더 pass 뒤 센서 배열을 읽는다."""
        from harvest_sensors.profile import matrix
        from harvest_sensors.student60_eval_camera_cache import remap_render, centred_render_spec
        from harvest_rl.rgbd_geometry import valid_depth
        started = time.perf_counter()
        prepared, self._prepared_capture = self._prepared_capture, None
        reused = prepared is not None and abs(prepared[0]-now) < 1e-9
        if reused:
            _, q, expected, pose_s = prepared
        else:
            q, expected = self.update_poses()
            pose_s = time.perf_counter()-started
        timings = dict(camera_pose_s=pose_s, camera_reused_render_passes=int(reused))
        before = float(self.world.current_time)
        # 같은 물리 tick의 일반 렌더도 현재 pose라면 첫 pass로 쓴다.
        # 촬영/일반 렌더 위상이 다르면 원래 두 pass를 그대로 실행한다.
        for index in range(int(reused), 2):
            mark = time.perf_counter()
            self.world.render()
            timings[f'camera_render_{index+1}_s'] = time.perf_counter()-mark
        if abs(float(self.world.current_time)-before) > 1e-9:
            raise RuntimeError('Student 촬영 중 물리 시간이 진행됐습니다.')
        result = {}
        for name, pair in self.cameras.items():
            images, poses, ks, checks = {}, {}, {}, {}
            error = 0.
            for stream, camera in pair.items():
                mark = time.perf_counter()
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
                timings['camera_metadata_s'] = timings.get('camera_metadata_s', 0.) + time.perf_counter()-mark
                mark = time.perf_counter()
                array = camera.get_depth() if stream == 'depth' else camera.get_rgba()
                timings['camera_readback_s'] = timings.get('camera_readback_s', 0.) + time.perf_counter()-mark
                if array is None or not np.asarray(array).size:
                    raise RuntimeError('Student 실제 센서 영상이 없습니다: '+name+'/'+stream)
                mark = time.perf_counter()
                image = remap_render(np.asarray(array), spec, depth=stream == 'depth')
                if stream != 'depth':
                    # SDK RGB는 RGBA의 비연속 view다. RGBA로 리맵 후 RGB를 추출하면
                    # OpenCV의 큰 입력 영상 암묵 복사를 피하며 RGB 보간값은 같다.
                    image = np.ascontiguousarray(image[:, :, :3])
                timings['camera_remap_s'] = timings.get('camera_remap_s', 0.) + time.perf_counter()-mark
                if stream == 'ir_right':
                    mark = time.perf_counter()
                    image = np.rint(image.astype(float) @ [.299, .587, .114]).astype(np.uint8)
                    timings['camera_ir_s'] = time.perf_counter()-mark
                images[stream] = image
            self.max_fk_error = max(self.max_fk_error, error)
            if error > 2e-4:
                raise RuntimeError(f'Student 센서 optical FK 불일치: {name}: {error}')
            raw = images['depth']
            mark = time.perf_counter()
            depth, mask = valid_depth(raw, self.config['depth_min_m'], self.config['depth_max_m'])
            relative = np.linalg.inv(poses['rgb']) @ poses['depth']
            aligned = self.align_depth(depth, ks['depth'], ks['rgb'], relative, images['rgb'].shape[:2])
            timings[f'camera_align_{name}_s'] = time.perf_counter()-mark
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
        timings['camera_acquire_s'] = time.perf_counter()-started + (pose_s if reused else 0.)
        self.frame_timings = timings

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
