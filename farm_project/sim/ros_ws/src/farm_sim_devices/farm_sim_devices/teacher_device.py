"""기존 농장 World의 물리 상태를 Teacher 좌표계로 읽는 시뮬 장치다.

reset 전 생성, reset 후 initialize, 선택 후 매 physics step 직후
observe_physics_tick 순서다. World의 시간·reset·관절 위치를 직접 바꾸지 않는다.
접촉은 PhysX의 대상별 impulse를 실제 physics dt로 나눈 힘(N)만 사용한다.
"""
from copy import deepcopy
import math
from typing import Any, Mapping, Sequence

import numpy as np

from .stem_physics import quaternion_matrix


def _array(value: Any, shape: tuple[int, ...], name: str) -> np.ndarray:
    """유한한 고정 크기 SI 배열을 복사한다."""
    result = np.asarray(value, dtype=float)
    if result.shape != shape or not np.isfinite(result).all():
        raise ValueError(f'{name}: 유한한 {shape} 배열이 필요합니다.')
    return result.copy()


def _quaternion(rotation: np.ndarray) -> np.ndarray:
    """회전행렬을 단위 wxyz quaternion으로 변환한다."""
    r = _array(rotation, (3, 3), 'rotation')
    k = np.array([[r[0, 0]-r[1, 1]-r[2, 2], r[0, 1]+r[1, 0], r[0, 2]+r[2, 0], r[2, 1]-r[1, 2]],
                  [r[0, 1]+r[1, 0], r[1, 1]-r[0, 0]-r[2, 2], r[1, 2]+r[2, 1], r[0, 2]-r[2, 0]],
                  [r[0, 2]+r[2, 0], r[1, 2]+r[2, 1], r[2, 2]-r[0, 0]-r[1, 1], r[1, 0]-r[0, 1]],
                  [r[2, 1]-r[1, 2], r[0, 2]-r[2, 0], r[1, 0]-r[0, 1], np.trace(r)]]) / 3.
    q = np.linalg.eigh(k)[1][:, -1][[3, 0, 1, 2]]
    return q if q[0] >= 0 else -q


def continuous_near_mask(points_arm: np.ndarray, config: Mapping) -> np.ndarray:
    """전달 region/HOME 거리 필터다. 이산18점 일치나 IK/충돌 성공을 뜻하지 않는다."""
    points = np.asarray(points_arm, dtype=float)
    if points.ndim != 2 or points.shape[1] != 3 or not np.isfinite(points).all():
        raise ValueError('과실 arm 좌표는 유한한 (N,3) 배열이어야 합니다.')
    lo = _array(config['workspace_arm_min_m'], (3,), 'workspace min')
    hi = _array(config['workspace_arm_max_m'], (3,), 'workspace max')
    home = _array(config['home_tcp_arm_m'], (3,), 'HOME TCP')
    near, far = float(config['near_home_min_m']), float(config['near_home_max_m'])
    if np.any(lo >= hi) or not math.isfinite(near+far) or not 0 <= near < far:
        raise ValueError('Teacher 근거리 영역 설정을 확인하세요.')
    distance = np.linalg.norm(points-home, axis=-1)
    return ((points >= lo) & (points <= hi)).all(-1) & (distance > near) & (distance < far)


class TeacherDevice:
    """측정과 오른팔6축 목표만 담당한다. 목표 순서·정책·성공 판정은 외부 책임이다."""

    def __init__(self, world: Any, articulation: Any, robot_path: str,
                 physics: Any, robot_id: str, config: Mapping) -> None:
        from isaacsim.core.prims import RigidPrim
        from pxr import Usd, UsdGeom, UsdPhysics

        self.world, self.articulation, self.physics = world, articulation, physics
        self.robot_path, self.robot_id, self.config = robot_path, robot_id, dict(config)
        self.attachments = physics.attachments
        if self.attachments is None:
            raise ValueError('HarvestPhysics.register 다음에 TeacherDevice를 생성해야 합니다.')
        self.paths = list(self.attachments.paths)
        self._path_indices = {path: index for index, path in enumerate(self.paths)}
        report = physics.arm_reports[robot_path]
        self.joint_names = list(report['joint_names'])
        self.home = _array(report['home_positions_rad'], (6,), 'HOME')
        self.travel = (None if report.get('travel_pose') is None else
                       _array(report['travel_pose']['positions_rad'][6:], (6,), 'right travel'))
        self._travel_report = report.get('travel_pose')
        self._policy_arm = _array(config['policy_arm_position_m'], (3,), 'policy arm mount')
        self._tcp_offset = _array(config['tcp_offset_gripper_m'], (3,), 'TCP offset')
        continuous_near_mask(np.empty((0, 3)), config)
        self._ready, self._selected = False, None
        self._completed: set[str] = set()
        self._previous: dict | None = None
        self._events: list[dict] = []
        self._last_physics_dt = float(world.get_physics_context().get_physics_dt())
        stage = world.stage
        robot = stage.GetPrimAtPath(robot_path)
        prims = list(Usd.PrimRange(robot))

        def named(name: str) -> Any:
            matches = [p for p in prims if p.GetName() == name]
            if len(matches) != 1:
                raise ValueError(f'{robot_path}: {name} 프림이 {len(matches)}개입니다.')
            return matches[0]

        mount = stage.GetPrimAtPath(physics.harvesters[robot_id]['mount_path'])
        fixed, moving = named('arm_2_gripper_link'), named('arm_2_moving_jaw_so101_v1_link')
        self._mount_path, self._fixed_path = str(mount.GetPath()), str(fixed.GetPath())
        self._finger_paths = [str(fixed.GetPath()), str(moving.GetPath())]
        arm_paths = [str(p.GetPath()) for p in prims if p.GetName().startswith('arm_2_')
                     and p.HasAPI(UsdPhysics.RigidBodyAPI) and str(p.GetPath()) not in self._finger_paths
                     and any(c.HasAPI(UsdPhysics.CollisionAPI)
                             for c in Usd.PrimRange(p, Usd.TraverseInstanceProxies()))]
        if physics.profile.get('teacher_alignment', {}).get('enabled', False):
            # 학습의 arm contact sensor는 합쳐진 차체/집게를 제외한 네 링크다.
            contact_links = {'arm_2_shoulder_link', 'arm_2_upper_arm_link',
                             'arm_2_lower_arm_link', 'arm_2_wrist_link'}
            arm_paths = [path for path in arm_paths if path.rsplit('/', 1)[-1] in contact_links]
        if not arm_paths:
            raise ValueError('오른팔 접촉 측정 body가 없습니다.')
        # reporter threshold만0으로 만들며 global solver/stabilization은 변경하지 않는다.
        with Usd.EditContext(stage, stage.GetSessionLayer()):
            self._pose_view = world.scene.add(RigidPrim(
                prim_paths_expr=[self._mount_path, self._fixed_path], name=robot_id+'_teacher_poses',
                reset_xform_properties=False, prepare_contact_sensors=False))
            self._finger_view = world.scene.add(RigidPrim(
                prim_paths_expr=self._finger_paths, name=robot_id+'_teacher_fingers',
                reset_xform_properties=False, track_contact_forces=True, prepare_contact_sensors=True,
                disable_stablization=False, contact_filter_prim_paths_expr=[list(self.paths), list(self.paths)],
                max_contact_count=4096))
            self._arm_view = world.scene.add(RigidPrim(
                prim_paths_expr=arm_paths, name=robot_id+'_teacher_arm_contacts',
                reset_xform_properties=False, track_contact_forces=True, prepare_contact_sensors=True,
                contact_filter_prim_paths_expr=[[] for _ in arm_paths], disable_stablization=False))
        self._pose_indices = {path: i for i, path in enumerate(self._pose_view.prim_paths)}
        self._finger_indices = [self._finger_view.prim_paths.index(path) for path in self._finger_paths]
        joints = [stage.GetPrimAtPath(path) for path in report['joint_paths']]
        self.lower = np.radians([p.GetAttribute('physics:lowerLimit').Get() for p in joints])
        self.upper = np.radians([p.GetAttribute('physics:upperLimit').Get() for p in joints])
        # collider points는 초기 과실root local에 보관한다. 시각 mesh/중심 AABB로 대체하지 않는다.
        self._vertices: dict[str, np.ndarray] = {}
        self._color_vertices: dict[str, np.ndarray] = {}
        cache = UsdGeom.XformCache()
        for record in self.attachments.records:
            path, color = record['prim_path'], record['color']
            if color not in self._color_vertices:
                fruit = stage.GetPrimAtPath(path)
                inverse = np.linalg.inv(np.asarray(cache.GetLocalToWorldTransform(fruit)).T)
                arrays = []
                for p in Usd.PrimRange(fruit, Usd.TraverseInstanceProxies()):
                    if p.IsA(UsdGeom.Mesh) and p.HasAPI(UsdPhysics.CollisionAPI):
                        matrix = inverse @ np.asarray(cache.GetLocalToWorldTransform(p)).T
                        points = np.asarray(UsdGeom.Mesh(p).GetPointsAttr().Get(), dtype=float)
                        arrays.append(points @ matrix[:3, :3].T + matrix[:3, 3])
                if not arrays:
                    raise ValueError('과실 collider vertices가 없습니다: '+path)
                self._color_vertices[color] = np.concatenate(arrays)
            self._vertices[path] = self._color_vertices[color]

    def initialize(self) -> None:
        """reset 후 기존 articulation과 PhysX 접촉 handle을 확인한다."""
        self._joint_indices = np.asarray([self.articulation.get_dof_index(n) for n in self.joint_names], dtype=np.int32)
        if len(self._joint_indices) != 6 or len(set(self._joint_indices)) != 6 or np.any(self._joint_indices < 0):
            raise RuntimeError('오른팔6축 joint mapping이 다릅니다.')
        for view in (self._pose_view, self._finger_view, self._arm_view):
            view.initialize(self.world.physics_sim_view)
            if not view.is_physics_handle_valid():
                raise RuntimeError('Teacher PhysX view가 준비되지 않았습니다.')
        self._ready = True
        self._frame()
        self.contacts_for_recovery()

    def travel_ready(self) -> bool:
        """양팔의 실제 주행 자세와 정지 상태를 확인한다. 오른팔 HOME은 별도 계약이다."""
        if self._travel_report is None:
            return True
        indices = np.asarray([self.articulation.get_dof_index(n)
                              for n in self._travel_report['joint_names']], dtype=np.int32)
        q = np.asarray(self.articulation.get_joint_positions(joint_indices=indices))
        qd = np.asarray(self.articulation.get_joint_velocities(joint_indices=indices))
        target = np.asarray(self._travel_report['positions_rad'])
        return bool(np.isfinite(q).all() and np.isfinite(qd).all()
                    and np.max(abs(q-target)) < .1 and np.max(abs(qd)) < .5)

    def _frame(self) -> tuple[np.ndarray, np.ndarray]:
        """현재 실제 오른팔 장착점의 world pose를 읽는다."""
        positions, orientations = self._pose_view.get_world_poses()
        index = self._pose_indices[self._mount_path]
        rotation = quaternion_matrix(np.asarray(orientations[index], dtype=float))
        transform = np.eye(4)
        transform[:3, :3], transform[:3, 3] = rotation, positions[index]
        return transform, np.asarray(positions[index], dtype=float)

    def candidates(self, completed_ids: Sequence[str] = ()) -> list[dict]:
        """현재 TF·빨강/노랑·부착 상태·연속 근거리 조건으로 persistent ID를 찾는다."""
        if not self._ready:
            raise RuntimeError('TeacherDevice.initialize가 필요합니다.')
        transform, _ = self._frame()
        positions = self.attachments.current_positions()
        arm = (positions-transform[:3, 3]) @ transform[:3, :3]
        eligible = continuous_near_mask(arm, self.config) & self.attachments.attached
        completed = set(completed_ids)
        return [dict(prim_path=path, target_id=path, color=self.attachments.records[i]['color'],
                     root_arm_m=arm[i].tolist(), root_world_m=positions[i].tolist(),
                     home_distance_m=float(np.linalg.norm(arm[i]-self.config['home_tcp_arm_m'])))
                for i, path in enumerate(self.paths) if eligible[i] and path not in completed
                and self.attachments.records[i]['color'] in ('red', 'yellow')]

    def arm_world_transform(self) -> np.ndarray:
        """시험 배치 기하에 사용할 실제 오른팔 장착점의 world 변환을 복사한다."""
        if not self._ready:
            raise RuntimeError('TeacherDevice.initialize가 필요합니다.')
        return self._frame()[0].copy()

    def candidate_ids(self, completed_ids: Sequence[str] = ()) -> list[str]:
        """candidates와 같은 조건의 원래 과실 prim ID 목록이다."""
        return [item['target_id'] for item in self.candidates(completed_ids)]

    def escaped_deposits(self, target_ids: Sequence[str]) -> list[str]:
        """이전 적재 성공 과실이 현재 로봇 박스를 벗어났는지 실제 외곽으로 검사한다.

        전달 still_in_box와 같이 재정착 속도/접촉/dwell을 요구하지 않는다.
        창 사이 주행에도 박스는 로봇과 함께 움직이므로 선택 시 고정한 TF 대신
        현재 장착 TF를 사용한다. 호출자는 성공한 ID만 전달한다.
        """
        if not self._ready:
            raise RuntimeError('TeacherDevice.initialize가 필요합니다.')
        ids = list(dict.fromkeys(target_ids))
        if not ids:
            return []
        if any(path not in self._path_indices for path in ids):
            raise ValueError('적재 상태를 조회할 과실 ID가 없습니다.')
        lo = _array(self.config['box_min'], (3,), 'box min')
        hi = _array(self.config['box_max'], (3,), 'box max')
        contact = float(self.config['box_contact_tolerance'])
        bottom = float(self.config['box_bottom_contact_tolerance'])
        if np.any(lo >= hi) or not np.isfinite([contact, bottom]).all() or min(contact, bottom) < 0:
            raise ValueError('Teacher 박스 범위/접촉 허용값을 확인하세요.')
        tolerance = np.array([contact, contact, max(contact, bottom, .005 if self.config.get('sequence', False) else 0.)])
        current_arm, _ = self._frame()
        transform = np.linalg.inv(current_arm)
        transform[:3, 3] += self._policy_arm
        rotation, translation = transform[:3, :3], transform[:3, 3]
        positions = self.attachments.current_positions()
        escaped = []
        for path in ids:
            index = self._path_indices[path]
            orientation = self.attachments._cached_orientations[index]
            body_rotation = rotation @ quaternion_matrix(orientation)
            vertices = self._vertices[path] @ body_rotation.T + rotation @ positions[index] + translation
            if (not np.isfinite(vertices).all() or not np.all(vertices.min(0) >= lo-tolerance)
                    or not np.all(vertices.max(0) <= hi+contact)):
                escaped.append(path)
        return escaped

    def select_target(self, target_id: str, completed_ids: Sequence[str] = ()) -> None:
        """새 목표의 고정 policy TF와 분리 전 물리 snapshot을 초기화한다."""
        if target_id not in self.candidate_ids(completed_ids):
            raise ValueError('현재 부착된 Teacher 근거리 빨강/노랑 후보가 아닙니다: '+target_id)
        if not self.attachments.active[self._path_indices[target_id]]:
            raise RuntimeError('목표 과실 물리를 먼저 활성화해야 합니다.')
        self._selected, self._completed = target_id, set(completed_ids)
        self._dock_world_arm, _ = self._frame()
        self._policy_world = np.linalg.inv(self._dock_world_arm)
        self._policy_world[:3, 3] += self._policy_arm
        self._events = []
        self._previous = self._read_sample(float(self.world.current_time), self._last_physics_dt)

    def clear_target(self) -> None:
        """관절이나 과실 상태를 바꾸지 않고 현재 측정 대상만 해제한다."""
        self._selected, self._previous, self._events = None, None, []

    def joint_positions(self) -> np.ndarray:
        """기존 articulation의 오른팔6축 실제 각도(rad)다."""
        return _array(self.articulation.get_joint_positions(joint_indices=self._joint_indices), (6,), 'q')

    def joint_velocities(self) -> np.ndarray:
        """목표가 선택되지 않은 정지/복귀 중에도 실제 오른팔 속도(rad/s)를 읽는다."""
        return _array(self.articulation.get_joint_velocities(joint_indices=self._joint_indices), (6,), 'qd')

    def command(self, targets: Sequence[float]) -> None:
        """오른팔6축 drive 목표(rad)만 적용한다. joint state teleport는 하지 않는다."""
        from isaacsim.core.utils.types import ArticulationAction

        values = _array(targets, (6,), 'joint targets')
        if not self._ready or np.any(values < self.lower-1e-6) or np.any(values > self.upper+1e-6):
            raise ValueError('준비된 오른팔 관절 한계 안의 목표가 필요합니다.')
        self.articulation.apply_action(ArticulationAction(
            joint_positions=np.clip(values, self.lower, self.upper).astype(np.float32),
            joint_indices=self._joint_indices))

    def configure_actuator(self, settings: Mapping) -> None:
        """원본 단계 제어의 drive gain/실제 속도 한도를 PhysX에 적용한다."""
        gain = _array(settings['stiffness'], (6,), 'stiffness')
        limit = _array(settings['velocity_limits'], (6,), 'velocity limits')
        if np.any(gain <= 0) or np.any(limit <= 0):
            raise ValueError('양의 drive gain/속도 한도가 필요합니다.')
        view = self.articulation._articulation_view
        view.set_gains(kps=gain[None].astype(np.float32), joint_indices=self._joint_indices)
        view.set_max_joint_velocities(limit[None].astype(np.float32), joint_indices=self._joint_indices)

    def restore_actuator(self) -> None:
        """실제 복귀 전 조임 단계의 임시 gain/속도 한도를 해제한다."""
        self.configure_actuator(dict(stiffness=[25.]*5+[8.], velocity_limits=[1.2]*5+[1.5]))

    def contacts_for_recovery(self) -> dict:
        """실제 손가락·팔 net contact 힘과 최대값을 반환한다. 단위는 N이다."""
        dt = self._last_physics_dt
        fingers = np.asarray(self._finger_view.get_net_contact_forces(dt=dt), dtype=float)[self._finger_indices]
        arm = np.asarray(self._arm_view.get_net_contact_forces(dt=dt), dtype=float).reshape(-1, 3)
        if fingers.shape != (2, 3) or not np.isfinite(fingers).all() or not np.isfinite(arm).all():
            raise RuntimeError('PhysX contact force 조회가 유효하지 않습니다.')
        return dict(finger_net_forces_world=fingers, arm_forces_world=arm,
                    max_force_N=float(max(np.linalg.norm(fingers, axis=1).max(), np.linalg.norm(arm, axis=1).max())))

    def finger_contact_forces_world(self, target_id: str) -> np.ndarray:
        """선택 과실에 대한 두 손가락의 실제 접촉력(N)을 읽는다. 다른 물체 접촉은 제외한다."""
        index = self._path_indices[target_id]
        matrix = np.asarray(self._finger_view.get_contact_force_matrix(dt=self._last_physics_dt), dtype=float)
        if matrix.shape != (2, len(self.paths), 3) or not np.isfinite(matrix).all():
            raise RuntimeError(f'PhysX 대상별 손가락 접촉 shape가 다릅니다: {matrix.shape}')
        return matrix[self._finger_indices, index].copy()

    def _read_sample(self, sim_s: float, dt: float) -> dict:
        """선택 과실의 실제 상태를 고정 legacy policy frame으로 읽는다."""
        if self._selected is None:
            raise RuntimeError('Teacher 측정 목표를 먼저 선택해야 합니다.')
        index = self._path_indices[self._selected]
        positions = self.attachments.current_positions()
        orientation = np.asarray(self.attachments._cached_orientations[index], dtype=float)
        velocity = self.attachments.current_velocities()[index]
        root = positions[index]
        com = root + quaternion_matrix(orientation) @ self.attachments.local_com[index]
        body_positions, body_orientations = self._pose_view.get_world_poses()
        fixed = self._pose_indices[self._fixed_path]
        gripper_quat = np.asarray(body_orientations[fixed], dtype=float)
        tcp = body_positions[fixed] + quaternion_matrix(gripper_quat) @ self._tcp_offset
        rotation, translation = self._policy_world[:3, :3], self._policy_world[:3, 3]

        def point(value: np.ndarray) -> np.ndarray:
            return rotation @ value + translation

        matrix = np.asarray(self._finger_view.get_contact_force_matrix(dt=dt), dtype=float)
        if matrix.shape != (2, len(self.paths), 3) or not np.isfinite(matrix).all():
            raise RuntimeError(f'PhysX 대상별 손가락 접촉 shape가 다릅니다: {matrix.shape}')
        contacts = self.contacts_for_recovery()
        forces = matrix[self._finger_indices, index]
        step = self.attachments.last_step
        attached = bool(self.attachments.attached[index])
        load = float(step.tension[index]) if step is not None and attached else 0.
        other_detached = any(not self.attachments.attached[i] and path != self._selected and path not in self._completed
                             for i, path in enumerate(self.paths))
        return dict(time_s=float(sim_s), target_id=self._selected, q=self.joint_positions(),
                    qd=self.joint_velocities(),
                    tcp_position=point(tcp), tcp_quaternion=_quaternion(rotation @ quaternion_matrix(gripper_quat)),
                    fruit_position=point(root), fruit_quaternion=_quaternion(rotation @ quaternion_matrix(orientation)),
                    fruit_com_position=point(com), fruit_linear_velocity=rotation @ velocity[:3],
                    fruit_angular_velocity=rotation @ velocity[3:], fixed_force=rotation @ forces[0],
                    moving_force=rotation @ forces[1], fixed_net_force=rotation @ contacts['finger_net_forces_world'][0],
                    moving_net_force=rotation @ contacts['finger_net_forces_world'][1],
                    arm_forces=contacts['arm_forces_world'] @ rotation.T, attached=attached,
                    anchor=point(self.attachments.anchors[index]), load_N=load,
                    break_timer_s=float(self.attachments.timer[index]), break_threshold_N=float(self.attachments.thresholds[index]),
                    attachment_local=self.attachments.tips[index].copy(),
                    collision_vertices=self._vertices[self._selected], other_detached=bool(other_detached),
                    dock_displacement_m=float(np.linalg.norm(body_positions[self._pose_indices[self._mount_path]]-self._dock_world_arm[:3, 3])),
                    dock_rotation_delta_rad=float(np.arccos(np.clip((np.trace(
                        quaternion_matrix(np.asarray(body_orientations[self._pose_indices[self._mount_path]], dtype=float))
                        @ self._dock_world_arm[:3, :3].T)-1.)/2., -1., 1.))))

    def observe_physics_tick(self, dt: float, sim_s: float) -> None:
        """World.step 직후 호출한다. 분리는 직전 integration 전 pose/contact로 기록한다."""
        if not math.isfinite(dt) or dt <= 0 or not math.isfinite(sim_s):
            raise ValueError('유한한 physics dt와 sim 시간이 필요합니다.')
        self._last_physics_dt = float(dt)
        if self._selected is None:
            return
        previous = self._previous
        index = self._path_indices[self._selected]
        if previous is not None and previous['attached'] and not self.attachments.attached[index]:
            event = {key: deepcopy(previous[key]) for key in ('fruit_position', 'fruit_quaternion',
                     'tcp_position', 'tcp_quaternion', 'fixed_force', 'moving_force', 'time_s')}
            event['tip_displacement'] = (previous['fruit_position']
                + quaternion_matrix(previous['fruit_quaternion']) @ self.attachments.tips[index] - previous['anchor'])
            event['break_timer_s'] = float(self.attachments.timer[index])
            if self.attachments.last_step is not None:
                event['load_N'] = float(self.attachments.last_step.tension[index])
            self._events.append(event)
        self._previous = self._read_sample(sim_s, dt)

    def sample(self, target_id: str | None = None) -> dict:
        """20Hz 제어가 사용할 snapshot과 해당 구간의 물리 분리 사건을 한 번 소비한다."""
        if target_id is not None and target_id != self._selected:
            raise ValueError('sample은 select_target으로 고정한 ID만 조회할 수 있습니다.')
        if self._previous is None:
            raise RuntimeError('선택된 Teacher 목표가 없습니다.')
        result = dict(self._previous)
        result['detach_events'], self._events = self._events, []
        return result
