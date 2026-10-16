"""담당자 회신용 읽기 전용 USD/PhysX 및 연속 20Hz 기록.

진단 플래그가 있을 때만 생성한다. 관절 명령·과실·접촉·정규화 통계를 쓰지 않는다.
제어 입력/출력은 기존 POLICY trace, 초기화와 복귀 구간은 이 연속 기록으로 연결한다.
"""
from __future__ import annotations

from dataclasses import asdict
import json
import math
from pathlib import Path
import time
from typing import Any

import numpy as np


def _json(value: Any) -> Any:
    """SDK 수치 컨테이너를 SI 단위 그대로 JSON으로 변환한다."""
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, Path):
        return str(value)
    try:
        return list(value)
    except TypeError:
        return str(value)


def portable_json(value: Any) -> Any:
    """USD 자동계산/무제한 기본값의 Inf만 문자열로 표시해 표준 JSON을 만든다."""
    if isinstance(value, dict):
        return {key: portable_json(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [portable_json(item) for item in value]
    if isinstance(value, float) and not math.isfinite(value):
        return 'NaN' if math.isnan(value) else 'Infinity' if value > 0 else '-Infinity'
    if value is None or isinstance(value, (str, bool, int, float)):
        return value
    return portable_json(_json(value))


class TeacherRuntimeRecorder:
    """실제 물리 handle의 값과 USD의 적용 속성을 출처별로 보존한다."""

    def __init__(self, robot: dict, directory: Path) -> None:
        self.robot = robot
        self.arm, self.device = robot['arm'], robot['arm_device']
        self.world = self.device.world
        self.directory = directory
        directory.mkdir(parents=True, exist_ok=True)
        self.trace = (directory/'continuous.jsonl').open('x')
        self.previous_time: float | None = None
        self.index = 0
        self.targets: set[str] = set()
        art = self.device.articulation
        ctl = art.get_articulation_controller()
        ids = self.device._joint_indices
        kp, kd = ctl.get_gains()
        attachments = self.device.attachments
        self._save('fruit_initial_states.json', dict(
            records=attachments.records, positions_world_m=attachments.current_positions(),
            orientations_wxyz=attachments._cached_orientations,
            T_world_arm=self.device.arm_world_transform()))
        view = art._articulation_view
        self._save('arm_physx_readback.json', dict(
            body_names=view.body_names, masses=view.get_body_masses(),
            inertias=view.get_body_inertias(), coms=view.get_body_coms(),
            joint_names=art.dof_names, dof_limits=view.get_dof_limits(),
            stiffness=kp, damping=kd, effort_limits=ctl.get_max_efforts(),
            velocity_limits=view.get_joint_max_velocities()))
        self._save('runtime_contract.json', dict(
            frame='policy coordinates = inverse(T_world_arm_at_selection) * world + policy_arm_position_m',
            quaternion_order='wxyz', units='m, s, rad, kg, N, Nm',
            joint_names=self.device.joint_names,
            joint_lower_rad=self.device.lower, joint_upper_rad=self.device.upper,
            home_rad=self.device.home, policy_arm_position_m=self.device._policy_arm,
            physx_effort_limits_Nm=np.asarray(ctl.get_max_efforts())[ids],
            physx_stiffness=np.asarray(kp)[ids], physx_damping=np.asarray(kd)[ids],
            gravity=self.world.get_physics_context().get_gravity(),
            initial_physics_dt_s=self.world.get_physics_dt(),
            rendering_dt_s=self.world.get_rendering_dt(),
            finger_sensor_paths=self.device._finger_paths,
            contact_filter_paths=self.device.paths,
            arm_contact_paths=self.device._arm_view.prim_paths,
            stem_settings=asdict(attachments.settings),
            box_policy_min_m=self.device.config['box_min'],
            box_policy_max_m=self.device.config['box_max'],
            physics_source_note='PhysX initialized masses/COM/inverse inertia; USD properties separately marked',
            usd_sentinel_note='USD Infinity/-Infinity/NaN defaults are strings; use fruit_physx for initialized COM/inertia',
            fruit_physx=[dict(path=p, mass_kg=attachments.masses[i],
                local_com_m=attachments.local_com[i],
                inverse_inertia_body_kg_m2_inverse=attachments.inverse_inertia[i])
                for i, p in enumerate(attachments.paths)],
            robot_usd=self._usd_tree(self.device.robot_path),
            physics_scene_usd=[self._usd_prim(p) for p in self.world.stage.Traverse()
                               if p.GetTypeName() == 'PhysicsScene']))

    def _save(self, name: str, value: dict) -> None:
        (self.directory/name).write_text(json.dumps(portable_json(value), ensure_ascii=False,
                                                  indent=2, allow_nan=False)+'\n')

    def _usd_prim(self, prim: Any) -> dict:
        """합성된 USD 속성을 읽고 큰 mesh 정점 배열은 범위와 개수로 저장한다."""
        from pxr import UsdGeom, UsdShade

        prefixes = ('physics:', 'physx', 'drive:', 'xformOp', 'material:')
        attrs = {a.GetName(): a.Get() for a in prim.GetAttributes()
                 if a.GetName().startswith(prefixes)}
        item = dict(path=str(prim.GetPath()), type=prim.GetTypeName(),
                    applied_schemas=prim.GetAppliedSchemas(), resolved_usd_attributes=attrs,
                    relationships={r.GetName(): [str(p) for p in r.GetTargets()]
                                   for r in prim.GetRelationships()})
        if prim.IsA(UsdGeom.Mesh):
            points = np.asarray(UsdGeom.Mesh(prim).GetPointsAttr().Get(), dtype=float)
            if len(points):
                item['mesh_local_bounds_m'] = [points.min(0), points.max(0)]
                item['mesh_vertex_count'] = len(points)
        material, _ = UsdShade.MaterialBindingAPI(prim).ComputeBoundMaterial('physics')
        if material:
            item['bound_physics_material'] = str(material.GetPath())
            item['material_resolved_attributes'] = {
                a.GetName(): a.Get() for a in material.GetPrim().GetAttributes()
                if a.GetName().startswith(('physics:', 'physx'))}
        return item

    def _usd_tree(self, path: str) -> list[dict]:
        from pxr import Usd

        return [self._usd_prim(p) for p in Usd.PrimRange(
            self.world.stage.GetPrimAtPath(path), Usd.TraverseInstanceProxies())]

    def sample(self, sim_s: float) -> None:
        """제어 직후 같은 시각의 측정값을 기록하며 분리 이벤트는 소비하지 않는다."""
        control_now = self.arm._last_tick
        if self.previous_time is not None:
            if sim_s-self.previous_time < .05-1e-8:
                return
            if self.arm.state['status'] == 'RUNNING' and (control_now is None or abs(control_now-sim_s) > 1e-7):
                return
        target = self.device._selected
        if target is not None and target not in self.targets:
            self.targets.add(target)
            i = self.device._path_indices[target]
            attachments = self.device.attachments
            self._save(f'target_{len(self.targets):03d}.json', dict(
                target_id=target, record=attachments.records[i],
                T_policy_world=self.device._policy_world,
                T_world_arm_at_selection=self.device._dock_world_arm,
                rest_orientation_world_wxyz=attachments.rest_orientation[i],
                tension_axis_world=attachments.axes[i], attachment_local_m=attachments.tips[i],
                anchor_world_m=attachments.anchors[i], threshold_N=attachments.thresholds[i],
                usd=self._usd_tree(target)))
        action = self.device.articulation.get_applied_action()
        record = dict(index=self.index, sim_s=sim_s, wall_unix_ns=time.time_ns(),
            physics_step=int(self.world.current_time_step_index),
            physics_dt_s=float(self.world.get_physics_dt()),
            recorded_interval_s=None if self.previous_time is None else sim_s-self.previous_time,
            control_tick_sim_s=control_now, state=self.arm.telemetry(),
            target_id=target, q_rad=self.device.joint_positions(),
            qd_rad_s=self.device.joint_velocities(),
            physx_joint_position_targets_rad=np.asarray(action.joint_positions)[self.device._joint_indices],
            base_root_world_pose=self.robot['base'].pose(),
            T_world_arm=self.device.arm_world_transform(),
            contacts=self.device.contacts_for_recovery())
        if target is not None:
            record['sample'] = {k:v for k,v in self.device._previous.items() if k != 'collision_vertices'}
            record['fruit_physics'] = self.device.attachments.diagnostic_state(target)
        self.trace.write(json.dumps(portable_json(record), ensure_ascii=False, allow_nan=False)+'\n')
        self.trace.flush()
        self.index += 1
        self.previous_time = sim_s

    def close(self) -> None:
        self.trace.close()
