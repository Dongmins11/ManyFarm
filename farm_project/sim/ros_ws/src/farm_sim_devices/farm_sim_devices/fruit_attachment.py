"""Isaac Core rigid body들을 초기 꼭지 앵커에 물리적으로 연결합니다.

world.reset 전 생성 → reset 후 initialize → 매 world.step 전 update(dt) 순서입니다.
정책·ROS 목표·파지 성공과 독립적입니다. 활성 영역의 비목표 과실에도 동일한
물리 이탈 조건을 적용하며, 선택 모드의 비활성 부착 과실은 고정합니다.
"""
from dataclasses import fields
from typing import Any, Mapping, Sequence

import numpy as np

from .stem_physics import StemSettings, StemStep, quaternion_matrix, stem_step


class FruitAttachments:
    """과실별 힘을 world COM에 적용하는 배치 어댑터. 위치 m, quaternion wxyz."""

    def __init__(self, world: Any, fruits: Sequence[Mapping], settings: Mapping,
                 name: str = 'harvest_fruit_attachment', *, selective: bool = False) -> None:
        from isaacsim.core.prims import RigidPrim

        self.settings = StemSettings.from_mapping(settings)
        self.world, self.selective, self._name = world, bool(selective), name
        records = {str(item['prim_path']): dict(item) for item in fruits}
        if not records or len(records) != len(fruits):
            raise ValueError('중복되지 않은 과실 rigid prim 목록이 필요합니다.')
        self.view = world.scene.add(RigidPrim(prim_paths_expr=list(records), name=name,
            reset_xform_properties=False, prepare_contact_sensors=False))
        self.paths = list(self.view.prim_paths)
        if len(self.paths) != len(records) or set(self.paths) != set(records):
            raise ValueError('과실 prim 조회 결과가 요청 목록과 다릅니다.')
        self.records = [records[path] for path in self.paths]
        self.tips = np.asarray([item['attachment_local_m'] for item in self.records], dtype=float)
        self.axes = np.asarray([item['tension_axis_world'] for item in self.records], dtype=float)
        self.thresholds = np.asarray([item.get('break_force_N', settings.get('break_force', 2.5))
                                      for item in self.records], dtype=float)
        n = len(self.paths)
        if (self.tips.shape != (n, 3) or self.axes.shape != (n, 3)
                or not np.isfinite(self.tips).all() or not np.isfinite(self.axes).all()
                or np.any(np.linalg.norm(self.axes, axis=-1) < 1e-12)
                or not np.isfinite(self.thresholds).all() or np.any(self.thresholds <= 0)):
            raise ValueError('과실 연결점/인장축/분리힘 설정이 잘못됐습니다.')
        # 초기 stage 배치가 기준입니다. 물리 reset 중 첫 중력 tick의 처짐을 앵커로 삼지 않습니다.
        position, orientation = self.view.get_world_poses()
        self.rest_orientation = np.asarray(orientation, dtype=float).copy()
        self.anchors = np.asarray(position, dtype=float) + self._rotate(self.rest_orientation, self.tips)
        self._ready = False
        self.attached = np.ones(n, dtype=bool)
        self.active = np.ones(n, dtype=bool)
        self.timer = np.zeros(n)
        self.last_step = None
        self._cached_positions = np.asarray(position, dtype=float).copy()
        self._cached_orientations = self.rest_orientation.copy()
        self._active_indices = np.arange(n, dtype=np.int32)
        self._active_view = self.view
        self._view_revision = 0
        self._original_ccd: dict[int, bool] = {}

    @staticmethod
    def _rotate(orientation: np.ndarray, vectors: np.ndarray) -> np.ndarray:
        return (quaternion_matrix(orientation) @ vectors[..., None])[..., 0]

    def initialize(self) -> None:
        """world.reset 후 실제 PhysX 질량·관성·COM을 읽고 물리 handle을 확인합니다."""
        self.view.initialize()
        if not self.view.is_physics_handle_valid():
            raise RuntimeError('과실 PhysX handle이 준비되지 않았습니다.')
        masses = np.asarray(self.view.get_masses(), dtype=float)
        self.masses = masses.reshape(-1).copy()
        if not np.allclose(masses, self.settings.mass, rtol=1e-5, atol=1e-8):
            raise ValueError('과실 PhysX 질량과 줄기 설정 질량이 다릅니다.')
        local_com, _ = self.view.get_coms()
        self.local_com = np.asarray(local_com, dtype=float).reshape(-1, 3)
        # SDK가 반환하는 관성은 COM에 대한 body-prim frame 텐서입니다.
        self.inverse_inertia = np.asarray(self.view.get_inv_inertias(), dtype=float).reshape(-1, 3, 3)
        if (not np.isfinite(self.local_com).all() or not np.isfinite(self.inverse_inertia).all()
                or not np.allclose(self.inverse_inertia, self.inverse_inertia.transpose(0, 2, 1))
                or np.any(np.linalg.eigvalsh(self.inverse_inertia) <= 0)):
            raise ValueError('유한한 COM과 양의 정부호 과실 관성이 필요합니다.')
        self._ready = True
        self.reset()
        position, orientation = self.view.get_world_poses()
        self._cached_positions[:] = position
        self._cached_orientations[:] = orientation
        if self.selective:
            # 초기 관성은 dynamic 상태에서 읽는다. 앵커는 reset 전 기준을 유지한다.
            self._set_kinematic(np.arange(len(self.paths), dtype=np.int32), True)
            self.active.fill(False)
            self._rebuild_active_view()

    def _set_kinematic(self, indices: np.ndarray, enabled: bool) -> None:
        """전환 경계에서만 세션 USD를 갱신한다. 현재 pose를 같은 값으로 보존한다."""
        from pxr import PhysxSchema, Usd, UsdGeom, UsdPhysics
        from .fruit_pose import set_rigid_local_pose

        if not len(indices):
            return
        stage = self.world.stage
        cache = UsdGeom.XformCache()
        with Usd.EditContext(stage, stage.GetSessionLayer()):
            # PhysX는 kinematic+CCD 조합을 허용하지 않는다. 먼저 호환되는 중간
            # 상태를 flush하고 나서 다음 flag를 변경해야 live USD 처리 순서도 안전하다.
            for index in indices:
                index = int(index)
                prim = stage.GetPrimAtPath(self.paths[index])
                rigid = UsdPhysics.RigidBodyAPI(prim)
                physx = PhysxSchema.PhysxRigidBodyAPI(prim)
                if index not in self._original_ccd:
                    self._original_ccd[index] = bool(physx.GetEnableCCDAttr().Get())
                if enabled:
                    physx.CreateEnableCCDAttr(False)
                else:
                    rigid.CreateKinematicEnabledAttr(False)
            self._flush_physics_changes()
            for index in indices:
                prim = stage.GetPrimAtPath(self.paths[int(index)])
                if enabled:
                    # Fabric/PhysX pose가 USD보다 최신일 수 있다. 초기 pose로 되돌리지 않는다.
                    world_pose = np.eye(4)
                    world_pose[:3, :3] = quaternion_matrix(self._cached_orientations[index])
                    world_pose[:3, 3] = self._cached_positions[index]
                    parent = np.asarray(cache.GetLocalToWorldTransform(prim.GetParent())).T
                    local = np.linalg.inv(parent) @ world_pose
                    set_rigid_local_pose(prim, local)
                    UsdPhysics.RigidBodyAPI(prim).CreateKinematicEnabledAttr(True)
                else:
                    PhysxSchema.PhysxRigidBodyAPI(prim).CreateEnableCCDAttr(self._original_ccd[int(index)])
            self._flush_physics_changes()

    @staticmethod
    def _flush_physics_changes() -> None:
        """공개 PhysX 인터페이스로 USD 변경을 다음 force/view 접근 전에 반영한다."""
        from omni.physx import get_physx_simulation_interface

        get_physx_simulation_interface().flush_changes()

    def _rebuild_active_view(self) -> None:
        """활성 집합이 바뀔 때만 작은 PhysX view를 교체한다. scene에 누적 등록하지 않는다."""
        from isaacsim.core.prims import RigidPrim

        indices = np.flatnonzero(self.active).astype(np.int32)
        if not len(indices):
            self._active_view = None
            self._active_indices = indices
            return
        if len(indices) == len(self.paths):
            self._active_view = self.view
            self._active_indices = np.arange(len(self.paths), dtype=np.int32)
            return
        self._view_revision += 1
        view = RigidPrim(prim_paths_expr=[self.paths[i] for i in indices],
            name=f'{self._name}_active_{self._view_revision}',
            reset_xform_properties=False, prepare_contact_sensors=False)
        view.initialize(self.world.physics_sim_view)
        lookup = {path: i for i, path in enumerate(self.paths)}
        resolved = np.asarray([lookup[path] for path in view.prim_paths], dtype=np.int32)
        if len(resolved) != len(indices) or set(resolved) != set(indices):
            raise RuntimeError('활성 과실 view의 전역 인덱스 mapping이 다릅니다.')
        self._active_view, self._active_indices = view, resolved

    def _read_active_poses(self) -> tuple[np.ndarray, np.ndarray]:
        """활성 view만 조회하여 전역 위치 캐시를 최신 상태로 유지한다."""
        if self._active_view is None:
            return np.empty((0, 3)), np.empty((0, 4))
        position, orientation = self._active_view.get_world_poses()
        position, orientation = np.asarray(position, dtype=float), np.asarray(orientation, dtype=float)
        self._cached_positions[self._active_indices] = position
        self._cached_orientations[self._active_indices] = orientation
        return position, orientation

    def current_positions(self) -> np.ndarray:
        """비활성 pose 캐시와 활성 PhysX pose를 합친 전역 (N,3) 배열이다."""
        self._read_active_poses()
        return self._cached_positions.copy()

    def current_velocities(self) -> np.ndarray:
        """활성 view 속도와 비활성 0을 합친 전역 (N,6) 배열이다."""
        result = np.zeros((len(self.paths), 6))
        if self._active_view is not None:
            result[self._active_indices] = np.asarray(self._active_view.get_velocities(), dtype=float)
        return result

    def diagnostic_state(self, path: str) -> dict:
        """선택 과실의 실제 PhysX pose/속도와 마지막 tick 외력을 읽는다. 상태를 바꾸지 않는다."""
        if not self._ready:
            raise RuntimeError('FruitAttachments.initialize가 필요합니다.')
        index = self.paths.index(path)
        position = self.current_positions()[index]
        orientation = self._cached_orientations[index].copy()
        rotation = quaternion_matrix(orientation)
        tip = position + rotation @ self.tips[index]
        com = position + rotation @ self.local_com[index]
        rest = self.rest_orientation[index]
        cosine = abs(float(orientation @ rest) / (np.linalg.norm(orientation)*np.linalg.norm(rest)))
        lever = tip-com
        tilt = np.degrees(np.arccos(np.clip(lever[2]/max(np.linalg.norm(lever), 1e-12), -1., 1.)))
        initial = np.asarray(self.records[index]['initial_position_world_m'], dtype=float)
        step = self.last_step
        return dict(prim_path=path, active=bool(self.active[index]), attached=bool(self.attached[index]),
            mass_kg=float(self.masses[index]), position_world_m=position.tolist(),
            orientation_wxyz=orientation.tolist(), com_world_m=com.tolist(), tip_world_m=tip.tolist(),
            anchor_world_m=self.anchors[index].tolist(),
            root_z_change_mm=float(1000*(position[2]-initial[2])),
            tip_displacement_mm=float(1000*np.linalg.norm(tip-self.anchors[index])),
            rest_rotation_change_deg=float(np.degrees(2*np.arccos(np.clip(cosine, 0., 1.)))),
            com_tip_tilt_deg=float(tilt), velocity_world=self.current_velocities()[index].tolist(),
            stem_force_N=(step.force[index].tolist() if step is not None else [0., 0., 0.]),
            stem_torque_Nm=(step.torque[index].tolist() if step is not None else [0., 0., 0.]),
            angular_restoring_k_Nm_rad=float(self.settings.angular_k),
            attachment_model='world_anchor_spring_and_initial_orientation_torque')

    def set_active(self, indices: Sequence[int]) -> None:
        """요청 과실과 분리 과실은 dynamic으로 유지하고, 정지한 부착 과실만 freeze한다.

        타이머 진행 중이거나 선속도 0.01m/s·각속도 0.1rad/s를 넘으면 다음 호출까지
        freeze를 유예한다. 앵커·기준 자세·분리 여부와 timer를 초기화하지 않는다.
        """
        if not self._ready:
            raise RuntimeError('활성 집합은 initialize 이후에 변경해야 합니다.')
        values = np.asarray(indices)
        if (values.ndim != 1 or (values.size and values.dtype.kind not in 'iu')
                or np.any(values < 0) or np.any(values >= len(self.paths))):
            raise ValueError('과실 전역 정수 인덱스 범위를 확인하세요.')
        if not self.selective:
            return
        requested = np.zeros(len(self.paths), dtype=bool)
        requested[values.astype(np.int32)] = True
        requested |= ~self.attached
        if np.array_equal(requested, self.active):
            return
        self._read_active_poses()
        velocities = self.current_velocities()
        keep_moving = (np.linalg.norm(velocities[:, :3], axis=-1) > .01)
        keep_moving |= np.linalg.norm(velocities[:, 3:], axis=-1) > .1
        requested |= self.active & ((self.timer > 0) | keep_moving)
        freeze = np.flatnonzero(self.active & ~requested).astype(np.int32)
        activate = np.flatnonzero(~self.active & requested).astype(np.int32)
        if not len(freeze) and not len(activate):
            return
        self._set_kinematic(freeze, True)
        self._set_kinematic(activate, False)
        self.active[:] = requested
        self._rebuild_active_view()

    def reset(self, *, reanchor: bool = False) -> None:
        """명시적 장면 reset 때 호출합니다. 자동 재부착이나 과실 순간이동은 없습니다."""
        if reanchor:
            position, orientation = self.view.get_world_poses()
            self.rest_orientation = np.asarray(orientation, dtype=float).copy()
            self.anchors = np.asarray(position, dtype=float) + self._rotate(self.rest_orientation, self.tips)
        self.attached.fill(True)
        self.timer.fill(0.)
        self.last_step = None

    def update(self, dt_s: float, sim_time_s: float | None = None) -> list[dict]:
        """다음 물리 step의 외력을 적용하고 이번 tick에서 발생한 이탈만 반환합니다."""
        if not self._ready or not self.view.is_physics_handle_valid():
            raise RuntimeError('FruitAttachments.initialize()와 활성 물리 handle이 필요합니다.')
        if not np.isfinite(dt_s) or dt_s <= 0:
            raise ValueError('물리 dt는 유한한 양수여야 합니다.')
        positions, orientations = self._read_active_poses()
        view = self._active_view
        view_indices = self._active_indices
        local = (np.flatnonzero(self.attached[view_indices]) if self.selective
                 else np.arange(len(view_indices)))
        if not len(local):
            self.last_step = self._empty_step()
            return []
        indices = view_indices[local]
        positions, orientations = positions[local], orientations[local]
        rotations = quaternion_matrix(orientations)
        velocities = np.asarray(view.get_velocities(), dtype=float)[local]
        tips_world = positions + (rotations @ self.tips[indices, ..., None])[..., 0]
        com_world = positions + (rotations @ self.local_com[indices, ..., None])[..., 0]
        lever = tips_world-com_world
        tip_velocity = velocities[:, :3]+np.cross(velocities[:, 3:], lever)
        inverse_world = rotations @ self.inverse_inertia[indices] @ rotations.transpose(0, 2, 1)
        result = stem_step(self.settings, displacement=tips_world-self.anchors[indices], tip_velocity=tip_velocity,
            lever=lever, inverse_inertia_world=inverse_world, tension_axis_world=self.axes[indices],
            orientation_wxyz=orientations, rest_orientation_wxyz=self.rest_orientation[indices],
            angular_velocity=velocities[:, 3:], attached=self.attached[indices], timer=self.timer[indices],
            thresholds=self.thresholds[indices], dt_s=dt_s)
        global_result = self._empty_step()
        for field in fields(StemStep):
            getattr(global_result, field.name)[indices] = getattr(result, field.name)
        broke = self.attached & ~global_result.attached
        # 명시한 COM 위치로 적용: lever×F는 이미 토크에 포함되어 있어 중복 적용하지 않습니다.
        view.apply_forces_and_torques_at_pos(forces=result.force.astype(np.float32),
            torques=result.torque.astype(np.float32), positions=com_world.astype(np.float32),
            indices=local.astype(np.int32), is_global=True)
        result = global_result
        self.attached, self.timer, self.last_step = result.attached, result.timer, result
        return [dict(prim_path=self.paths[i], event='PHYSICAL_DETACH', sim_time_s=sim_time_s,
                     sustained_s=float(result.timer[i]), tension_N=float(result.tension[i]),
                     raw_tension_N=float(result.raw_tension[i]),
                     criteria=[name for name, flag in (
                         ('force_and_min_pull', result.force_exceeded[i]),
                         ('hook_opening', result.hook_opened[i]),
                         ('max_extension', result.max_extension_exceeded[i])) if flag],
                     threshold_N=float(self.thresholds[i]), extension_m=float(result.extension[i]),
                     displacement_m=float(result.displacement[i])) for i in np.flatnonzero(broke)]

    def _empty_step(self) -> StemStep:
        """비활성/분리 과실의 힘은 0으로 두고 전역 상태를 보존한다."""
        n = len(self.paths)
        return StemStep(force=np.zeros((n, 3)), torque=np.zeros((n, 3)),
            attached=self.attached.copy(), timer=self.timer.copy(), tension=np.zeros(n),
            extension=np.zeros(n), displacement=np.zeros(n), raw_tension=np.zeros(n),
            force_exceeded=np.zeros(n, dtype=bool), hook_opened=np.zeros(n, dtype=bool),
            max_extension_exceeded=np.zeros(n, dtype=bool))

    def summary(self) -> dict:
        """로그용 물리 상태. 실제 수확 성공 개수와 구분합니다."""
        return dict(fruit_count=len(self.paths), attached_count=int(self.attached.sum()),
                    detached_count=int((~self.attached).sum()), gravity_compensation=False,
                    attachment_version=4, stem_response_version=5,
                    active_count=int(self.active.sum()), frozen_count=int((~self.active).sum()))
