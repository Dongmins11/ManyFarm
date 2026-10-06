"""Isaac Core rigid body들을 초기 꼭지 앵커에 물리적으로 연결합니다.

world.reset 전 생성 → reset 후 initialize → 매 world.step 전 update(dt) 순서입니다.
정책·ROS 목표·파지 성공과 독립적이며 비목표 과실도 같은 물리 이탈 조건을 따릅니다.
"""
from typing import Any, Mapping, Sequence

import numpy as np

from .stem_physics import StemSettings, quaternion_matrix, stem_step


class FruitAttachments:
    """과실별 힘을 world COM에 적용하는 배치 어댑터. 위치 m, quaternion wxyz."""

    def __init__(self, world: Any, fruits: Sequence[Mapping], settings: Mapping,
                 name: str = 'harvest_fruit_attachment') -> None:
        from isaacsim.core.prims import RigidPrim

        self.settings = StemSettings.from_mapping(settings)
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
        self.timer = np.zeros(n)
        self.last_step = None

    @staticmethod
    def _rotate(orientation: np.ndarray, vectors: np.ndarray) -> np.ndarray:
        return (quaternion_matrix(orientation) @ vectors[..., None])[..., 0]

    def initialize(self) -> None:
        """world.reset 후 실제 PhysX 질량·관성·COM을 읽고 물리 handle을 확인합니다."""
        self.view.initialize()
        if not self.view.is_physics_handle_valid():
            raise RuntimeError('과실 PhysX handle이 준비되지 않았습니다.')
        masses = np.asarray(self.view.get_masses(), dtype=float)
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
        positions, orientations = self.view.get_world_poses()
        positions = np.asarray(positions, dtype=float)
        orientations = np.asarray(orientations, dtype=float)
        rotations = quaternion_matrix(orientations)
        velocities = np.asarray(self.view.get_velocities(), dtype=float)
        tips_world = positions + (rotations @ self.tips[..., None])[..., 0]
        com_world = positions + (rotations @ self.local_com[..., None])[..., 0]
        lever = tips_world-com_world
        tip_velocity = velocities[:, :3]+np.cross(velocities[:, 3:], lever)
        inverse_world = rotations @ self.inverse_inertia @ rotations.transpose(0, 2, 1)
        result = stem_step(self.settings, displacement=tips_world-self.anchors, tip_velocity=tip_velocity,
            lever=lever, inverse_inertia_world=inverse_world, tension_axis_world=self.axes,
            orientation_wxyz=orientations, rest_orientation_wxyz=self.rest_orientation,
            angular_velocity=velocities[:, 3:], attached=self.attached, timer=self.timer,
            thresholds=self.thresholds, dt_s=dt_s)
        broke = self.attached & ~result.attached
        # 명시한 COM 위치로 적용: lever×F는 이미 토크에 포함되어 있어 중복 적용하지 않습니다.
        self.view.apply_forces_and_torques_at_pos(forces=result.force.astype(np.float32),
            torques=result.torque.astype(np.float32), positions=com_world.astype(np.float32), is_global=True)
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

    def summary(self) -> dict:
        """로그용 물리 상태. 실제 수확 성공 개수와 구분합니다."""
        return dict(fruit_count=len(self.paths), attached_count=int(self.attached.sum()),
                    detached_count=int((~self.attached).sum()), gravity_compensation=False,
                    attachment_version=4, stem_response_version=5)
