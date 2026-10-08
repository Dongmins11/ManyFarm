"""시험용 충돌 표시와 실제 과실 물리 계측. 물성·결합·성공 기준은 수정하지 않는다."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np


def enable_physics_debug_ui() -> None:
    """World 초기화 후 공식 Colliders 메뉴를 등록하고 기존 USD 편집 대상을 보존한다."""
    import omni.kit.app
    import omni.usd
    stage = omni.usd.get_context().get_stage()
    edit_target = stage.GetEditTarget() if stage is not None else None
    manager = omni.kit.app.get_app().get_extension_manager()
    try:
        for extension in ('omni.kit.viewport.menubar.display', 'omni.physx.ui'):
            manager.set_extension_enabled_immediate(extension, True)
            if not manager.is_extension_enabled(extension):
                raise RuntimeError('물리 시각화 확장을 활성화하지 못했습니다: '+extension)
    finally:
        # layers UI 초기화는 편집 대상을 root로 바꿀 수 있다. 세션의 물리 설정이
        # 더 강하므로 이 상태로 dt를 쓰면 실제 주기는 바뀌지 않는다.
        if stage is not None:
            changed = stage.GetEditTarget().GetLayer() != edit_target.GetLayer()
            stage.SetEditTarget(edit_target)
            if changed:
                print('[physics_debug_ui] restored simulation edit target after UI initialization', flush=True)


def collision_display(mode: int | None = None) -> int:
    """공식 메뉴와 같은 설정. 0=해제, 1=선택, 2=전체이며 충돌 계산 여부와는 별개다."""
    import carb.settings
    from omni.physx.bindings._physx import SETTING_DISPLAY_COLLIDERS
    settings = carb.settings.get_settings()
    if mode is not None:
        if mode not in (0, 1, 2):
            raise ValueError('충돌 표시는 None/Selected/All만 지원합니다.')
        settings.set_int(SETTING_DISPLAY_COLLIDERS, mode)
    return settings.get_as_int(SETTING_DISPLAY_COLLIDERS)


def diagnostic_summary(sample: dict) -> str:
    """계측 항목의 단위와 고정/동적 상태를 사람이 읽을 수 있게 구분한다."""
    mode = 'DYNAMIC' if sample['active'] and not sample['kinematic'] else 'FROZEN'
    gravity = 'ON' if sample['gravity_enabled'] else 'OFF'
    force = sample['stem_force_N']
    return (f"{Path(sample['prim_path']).name}\n"
            f"{mode} | gravity {gravity} | mass {sample['mass_kg']*1000:.1f} g\n"
            f"Colliders enabled {sample['enabled_collider_count']}/{sample['collider_count']} | "
            f"attached {sample['attached']}\n"
            f"Root dz {sample['root_z_change_mm']:+.3f} mm | tip offset {sample['tip_displacement_mm']:.3f} mm\n"
            f"Rotation from initial {sample['rest_rotation_change_deg']:.2f} deg\n"
            f"COM-to-tip tilt from up {sample['com_tip_tilt_deg']:.2f} deg\n"
            f"Gravity Fz {sample['gravity_force_N'][2]:+.4f} N | stem Fz {force[2]:+.4f} N\n"
            f"Finger -> fruit contact: {sample['finger_contact_N'][0]:.4f} / {sample['finger_contact_N'][1]:.4f} N\n"
            f"Speed {np.linalg.norm(sample['velocity_world'][:3])*1000:.3f} mm/s | "
            f"arm contact max {sample['arm_contact_max_N']:.4f} N\n"
            'Stem = world-anchor spring + initial-pose torque\n'
            'Not a freely swinging connector joint.')


class FruitPhysicsInspector:
    """UI 선택 과실(없으면 배치 대상)을 PhysX와 USD 양쪽에서 검사한다."""

    def __init__(self, controller: Any) -> None:
        self.controller = controller
        self.attachments = controller.physics.attachments
        self.stage = controller.physics.stage
        self.sample: dict | None = None
        self.show_connection = True
        self._last_key = None
        self._last_log_time = -float('inf')
        self._previous_colliders = collision_display()
        self.log = (controller.directory/'physics_inspection.jsonl').open('w')
        self.error = ''

    def select_target(self) -> None:
        """배치 과실과 수확 로봇을 함께 선택해 Selected 충돌 표시로 양쪽 접촉 형상을 본다."""
        import omni.usd
        if self.controller.placement is not None:
            paths = [self.controller.placement['source_target_id'], self.controller.robot['path']]
            omni.usd.get_context().get_selection().set_selected_prim_paths(paths, False)

    def _path(self) -> str | None:
        import omni.usd
        for selected in omni.usd.get_context().get_selection().get_selected_prim_paths():
            for path in self.attachments.paths:
                if selected == path or selected.startswith(path+'/'):
                    return path
        placement = self.controller.placement
        return placement['source_target_id'] if placement else None

    def update(self, now: float, physics_hz: float) -> None:
        """최대5Hz 계측한다. USD flag만으로 실제 중력 반응을 판정하지 않는다."""
        from pxr import PhysxSchema, Usd, UsdPhysics
        path = self._path()
        key = (path, physics_hz, self.controller.physics_only)
        if path is None:
            self.sample = None
            return
        if key == self._last_key and now-self._last_log_time < .2:
            return
        self._last_key, self._last_log_time = key, now
        try:
            sample = self.attachments.diagnostic_state(path)
            prim = self.stage.GetPrimAtPath(path)
            rigid = UsdPhysics.RigidBodyAPI(prim)
            colliders = [p for p in Usd.PrimRange(prim, Usd.TraverseInstanceProxies())
                         if p.HasAPI(UsdPhysics.CollisionAPI)]
            direction, magnitude = self.attachments.world.get_physics_context().get_gravity()
            direction = np.asarray(direction, dtype=float)
            if magnitude < 0 or not np.isfinite(magnitude) or np.linalg.norm(direction) < 1e-10:
                raise RuntimeError('PhysicsScene 중력의 실제 방향/크기를 확인할 수 없습니다.')
            gravity_enabled = (bool(rigid.GetRigidBodyEnabledAttr().Get())
                               and not bool(PhysxSchema.PhysxRigidBodyAPI(prim).GetDisableGravityAttr().Get()))
            kinematic = bool(rigid.GetKinematicEnabledAttr().Get())
            effective = gravity_enabled and not kinematic and sample['active']
            gravity = direction/np.linalg.norm(direction)*magnitude
            sample.update(sim_time_s=now, physics_hz=physics_hz, physics_only=self.controller.physics_only,
                kinematic=kinematic, gravity_enabled=gravity_enabled,
                gravity_acceleration_m_s2=gravity.tolist(),
                gravity_force_N=(gravity*sample['mass_kg'] if effective else np.zeros(3)).tolist(),
                collider_count=len(colliders),
                enabled_collider_count=sum(bool(UsdPhysics.CollisionAPI(p).GetCollisionEnabledAttr().Get()) for p in colliders),
                colliders=[dict(path=str(p.GetPath()),
                    enabled=bool(UsdPhysics.CollisionAPI(p).GetCollisionEnabledAttr().Get()),
                    approximation=UsdPhysics.MeshCollisionAPI(p).GetApproximationAttr().Get()
                        if p.HasAPI(UsdPhysics.MeshCollisionAPI) else p.GetTypeName()) for p in colliders],
                arm_contact_max_N=self.controller.device.contacts_for_recovery()['max_force_N'],
                finger_contact_N=np.linalg.norm(self.controller.device.finger_contact_forces_world(path), axis=1).tolist())
            self.sample, self.error = sample, ''
            self.log.write(json.dumps(sample, ensure_ascii=False)+'\n')
            self.log.flush()
        except Exception as error:
            self.sample, self.error = None, str(error)
            self.log.write(json.dumps(dict(sim_time_s=now, error=self.error))+'\n')
            self.log.flush()

    def draw(self) -> None:
        """매 렌더 전 1프레임 표시: 노랑 앵커, 초록 꼭지, 청록 COM, 빨강 중력 화살표."""
        if not self.show_connection or self.sample is None:
            return
        from omni.debugdraw import get_debug_draw_interface
        draw = get_debug_draw_interface()
        sample = self.sample
        anchor, tip, com = (tuple(sample[key]) for key in ('anchor_world_m','tip_world_m','com_world_m'))
        # 선은 실제 좌표다. 힘 화살표만 1m/N로 확대한다. 물리 prim/constraint가 아니다.
        draw.draw_point(anchor, 0xFF00FFFF, 12.)
        draw.draw_point(tip, 0xFF00FF00, 8.)
        draw.draw_point(com, 0xFFFFFF00, 8.)
        draw.draw_line(anchor, 0xFF00FFFF, 3., tip, 0xFF00FF00, 3.)
        draw.draw_line(tip, 0xFFFFFF00, 2., com, 0xFFFFFF00, 2.)
        end = np.asarray(com)+np.asarray(sample['gravity_force_N'])
        draw.draw_line(com, 0xFF0000FF, 3., tuple(end), 0xFF0000FF, 3.)
        if np.linalg.norm(sample['gravity_force_N']) > 0:
            axis = np.asarray(sample['gravity_force_N'])
            axis /= np.linalg.norm(axis)
            side = np.cross(axis, [1., 0., 0.])
            if np.linalg.norm(side) < 1e-8:
                side = np.cross(axis, [0., 1., 0.])
            side /= np.linalg.norm(side)
            for sign in (-1, 1):
                wing = end-.018*axis+sign*.008*side
                draw.draw_line(tuple(end), 0xFF0000FF, tuple(wing), 0xFF0000FF)

    def close(self) -> None:
        """사용자 원래 표시 설정으로 복원하고 진단 파일만 닫는다."""
        try:
            collision_display(self._previous_colliders)
        finally:
            self.log.close()
