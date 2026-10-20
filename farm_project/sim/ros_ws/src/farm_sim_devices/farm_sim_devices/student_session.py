"""기존 팔 UDP/정차 계약에 전달 D435 Student mission을 연결한다.

영상 관측만 정책에 전달한다. 성공량은 평행 세 빔의 익명 통과로 센다.
시뮬 과실 ID/접촉은 목표 대응·안전 감시에만 쓰며 레이저가 ID를 식별했다고 주장하지 않는다.
World.step/reset 또는 관절·과실 teleport를 호출하지 않는다.
"""
import hashlib
import json
from pathlib import Path
import sys
from types import SimpleNamespace
import numpy as np
import torch
from .arm_session import ArmSession


def map_outcomes(targets: list, candidates: list, gate: float, ambiguity: float) -> dict:
    """확정된 영상 목록 이후 평가 ID만 매칭한다. 정책 위치/순서를 바꾸지 않는다."""
    result = {}
    for target in targets:
        distances = sorted((float(np.linalg.norm(np.asarray(c['root_arm_m'])-target.anchor_arm_m)), c['target_id'])
            for c in candidates if c['color'].capitalize() == target.label)
        if (not distances or distances[0][0] > gate or
                (len(distances) > 1 and distances[1][0]-distances[0][0] < ambiguity)):
            raise ValueError('Student 평가 ID 대응이 없거나 모호합니다: '+target.target_id)
        result[target.target_id] = distances[0][1]
    if len(set(result.values())) != len(result):
        raise ValueError('Student 평가 ID가 중복됩니다.')
    return result


def mission_session(camera: object, world_from_arm: np.ndarray) -> SimpleNamespace:
    """목표 정렬만 실제 중력 world Z를 쓴다. 정책의 학습 박스 좌표는 보존한다."""
    contract = dict(camera.contract, box_from_arm=np.asarray(world_from_arm, float).tolist())
    return SimpleNamespace(contract=contract, start=camera.start, step=camera.step, acknowledge=camera.acknowledge)


class StudentRuntime:
    """전달 가중치·카메라 제어를 로드하며 Teacher actor는 로드하지 않는다."""

    def __init__(self, root: Path, settings: dict, world: object, device: object, physical_task: dict) -> None:
        self.profile = settings
        # 전달 D435 실행기의 CPU 영상 전처리 설정을 유지한다.
        torch.set_num_threads(4)
        release = (root/settings['release']).resolve()
        if not release.is_relative_to(root/'sim'):
            raise ValueError('Student 자산은 sim 안에 있어야 합니다.')
        sys.path.insert(0, str(release/'src/harvest_robot'))
        self.release = release
        manifest = json.loads((release/'handoff/MISSION_RELEASE.json').read_text())
        self.artifact_manifest = {}
        for row in manifest['models'].values():
            path = (release/row['path']).resolve()
            if not path.is_relative_to(release):
                raise ValueError('Student 모델 경로가 전달 폴더 밖입니다.')
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            if digest != row['sha256']:
                raise ValueError('Student 모델 SHA 불일치: '+str(path))
            self.artifact_manifest[str(path.relative_to(root))] = digest
        sources = [release/'handoff/MISSION_RELEASE.json', release/'handoff/MISSION_MANIFEST.json',
                   release/manifest['config'], Path(__file__), Path(__file__).with_name('student_camera.py'),
                   Path(__file__).with_name('basket_laser.py')]
        for package in ('harvest_runtime', 'harvest_rl', 'harvest_sensors', 'harvest_vision'):
            sources.extend((release/'src/harvest_robot'/package).rglob('*.py'))
        for path in sources:
            self.artifact_manifest[str(path.relative_to(root))] = hashlib.sha256(path.read_bytes()).hexdigest()
        from harvest_rl.kinematics import ArmKinematics
        from harvest_runtime.student60_mission_session import MissionCameraSession
        from harvest_vision.client import Detector
        from .student_camera import FarmD435Rig
        self.contract = torch.load(release/manifest['models']['d435']['path'], map_location='cpu', weights_only=True)['contract']
        # 농장 scene 배치 seed는 고정 물성/제어 계약의 일부가 아니다.
        if {k: v for k, v in physical_task.items() if k != 'seed'} != self.contract['task']:
            raise ValueError('농장 물리 task와 Student 고정 계약 불일치')
        if settings['camera'] != 'd435':
            raise ValueError('현재 농장 어댑터는 검증 대상 D435만 지원합니다.')
        if not np.allclose(device.config['policy_arm_position_m'], np.asarray(self.contract['box_from_arm'])[:3, 3], atol=1e-9):
            raise ValueError('농장 박스 판정 좌표와 Student 학습 좌표 불일치')
        if not np.allclose(device.lower, self.contract['lower_rad'], atol=1e-6) or not np.allclose(device.upper, self.contract['upper_rad'], atol=1e-6):
            raise ValueError('실제 농장 관절 한계와 Student 계약 불일치')
        from harvest_rl.settings import URDF
        for source, field in ((URDF, 'sensor_mount_reference_urdf_sha256'),
                (release/'src/harvest_robot/config/arm_appearance.json', 'deployment_arm_appearance_sha256')):
            digest = hashlib.sha256(source.read_bytes()).hexdigest()
            if digest != self.contract[field]:
                raise ValueError('Student 센서/외형 기준 SHA 불일치: '+str(source))
            self.artifact_manifest[str(source.relative_to(root))] = digest
        self.kin = ArmKinematics()
        self.config = json.loads((release/manifest['config']).read_text())
        # 농장에서 검증된 양팔 주행 접힘을 유지한다. 학습 HOME은 변경하지 않는다.
        if device.travel is not None:
            self.config['stow_rad'] = device.travel.tolist()
        if not np.allclose(device.home, self.config['home_rad'], atol=1e-6):
            raise ValueError('실제 농장 HOME과 Student 학습 HOME 불일치')
        self.detector = Detector(settings['vision_python'], release/manifest['models']['detector']['path'], device=settings['device'])
        try:
            self.rig = FarmD435Rig(world, device, self.kin, self.contract['camera_config'], device.robot_id)
            self.camera = MissionCameraSession(release/manifest['models']['d435']['path'], self.contract,
                self.detector, self.kin, self.rig.world_from_robot, camera_kind='d435',
                center_checkpoint=release/manifest['models']['center']['path'], device=settings['device'])
            from .basket_laser import BasketLaserSensor
            self.basket_sensor = BasketLaserSensor(world, device, settings['basket_lasers'])
        except Exception:
            self.detector.close()
            raise
        self.cancelled = False

    def cancel(self) -> None:
        self.cancelled = True

    def close(self) -> None:
        self.rig.close()
        self.detector.close()


class StudentArmSession(ArmSession):
    """기존 요청 검증·중복 방지·lease·측정 정지를 재사용한다."""

    def __init__(self, *args: object, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)
        self.mission = None
        self._physical_target = None
        self._box_evidence = None
        self._laser_armed = False
        self._laser_last = None
        self._confirmed_targets = 0
        self._fault = ''
        self._inventory_start = 0.

    def _stop(self, now: float, status: str, code: str, reason: str) -> None:
        self.controller.basket_sensor.counter.disarm()
        self._laser_armed = False
        super()._stop(now, status, code, reason)
        self.controller.rig.set_active(False)

    def lost_deposits(self) -> list[str]:
        """입구 통과는 안착 유지 검사가 아니다. 좌표 검사로 통과 수량을 취소하지 않는다."""
        return []

    def _finish(self, now: float, status: str, code: str = '', reason: str = '', *, safe: bool = True) -> None:
        if status == 'FAILED' and self._physical_target is not None and self._physical_target not in self._successful_ids:
            record = dict(target_id=self._physical_target, success=False, reason=reason or code, time_s=now)
            self._attempts.append(record)
            self.state['failed_count'] += 1
            self.state['event_seq'] += 1
            self._log('ATTEMPT_RESULT', **record)
        if self.mission is not None and self._directory is not None:
            report = self.mission.report()
            report['controller_mission_complete'] = report['mission_complete']
            report['mission_complete'] = bool(report['mission_complete'] and status == 'SUCCESS' and safe)
            report.update(session_status=status, session_error_code=code, session_error_message=reason,
                safe_stopped=safe, camera_acquisitions=self.controller.rig.sequence,
                max_sensor_fk_error=self.controller.rig.max_fk_error, teacher_actors_loaded=False,
                mission_config=self.controller.config, success_criterion='basket_parallel_lasers',
                object_identity_confirmed=False, physical_retention_confirmed=False)
            (self._directory/'student_mission.json').write_text(json.dumps(report, indent=2)+'\n')
        self.controller.rig.set_active(False)
        super()._finish(now, status, code, reason, safe=safe)

    def _tick(self, now: float, stationary: bool, wall_now: float) -> None:
        if self.state['stage'] == 'STOPPING':
            super()._tick(now, stationary, wall_now)
            return
        if self.state['stage'] == 'PREPARE':
            self._open_log(now)
            self.physics.set_activity(self.robot_id, True)
            self.mission = None
            self._physical_target = None
            self._box_evidence, self._fault = None, ''
            self._laser_armed, self._laser_last, self._confirmed_targets = False, None, 0
            self.controller.basket_sensor.counter.disarm()
            self._initial_attached = self.device.attachments.attached.copy()
            self._dock_arm = self.device.arm_world_transform()
            self.controller.cancelled = False
            if not stationary:
                self._stop(now, 'FAILED', 'BASE_MOVING', 'base_not_stationary_at_start')
                return
            if not self.travel_ready:
                self._stop(now, 'FAILED', 'ARM_NOT_STOWED', 'initial_measured_stow_required')
                return
            self.controller.rig.set_active(True)
            camera = self.controller.camera
            base = self.controller.kin.fk(np.zeros(6), 'arm_2/base_link')
            camera.arm_from_world = np.linalg.inv(self.controller.rig.robot_transform() @ base)
            camera.target = None
            self._inventory_start = now
            self.state['stage'] = 'CAMERA_INVENTORY'
            return
        fault = self._fault
        if self._pending_cancel:
            self._stop(now, 'CANCELED', '', 'operator_cancel')
            return
        if wall_now-self._lease > self.config['lease_s']:
            self._stop(now, 'FAILED', 'ARM_LEASE_EXPIRED', 'sim_arm_request_heartbeat_lost')
            return
        if not stationary:
            fault = 'base_moved_during_harvest'
        current_arm = self.device.arm_world_transform()
        if np.linalg.norm(current_arm[:3, 3]-self._dock_arm[:3, 3]) > self.config['base_drift_limit_m']:
            fault = 'right_arm_mount_moved_from_dock'
        rotation_delta = np.arccos(np.clip((np.trace(current_arm[:3, :3] @ self._dock_arm[:3, :3].T)-1.)/2., -1., 1.))
        if rotation_delta > self.config['base_yaw_drift_limit_rad']:
            fault = 'right_arm_mount_rotated_from_dock'
        if fault:
            self._stop(now, 'FAILED', 'STUDENT_SUPERVISOR_FAULT', fault)
            return
        if self.state['stage'] == 'CAMERA_INVENTORY':
            self._inventory(now)
            return
        mission = self.mission
        command, note = mission.tick(now, self.device.joint_positions(), self.device.joint_velocities(), now,
            self.controller.rig.capture(), box_evidence=self._box_evidence)
        self._box_evidence = None
        if mission.state in ('HARVEST', 'WAIT_BOX') and self._physical_target is None:
            path = self._outcomes[mission.target.target_id]
            self.device.select_target(path, self._successful_ids)
            self._physical_target = path
            self._all_attempted.add(path)
            self._log('TARGET', time_s=now, target_id=path, role='Student', camera_target_id=mission.target.target_id)
        # 전달 제어기의 실제 배출 열기 허용 이후에만 통과를 받는다.
        # 일반 release_latched는 관측 억제 신호이므로 배출 허가로 사용하지 않는다.
        servo_note = (note.get('policy_note') or {}).get('visual_servo') or {}
        if (not self._laser_armed and self._physical_target is not None
                and servo_note.get('observed_tray_release_latched')):
            self.controller.basket_sensor.counter.arm()
            self._laser_armed = True
            self._log('BASKET_LASER_ARMED', time_s=now, association='active_attempt_only')
        if note.get('policy_note') is not None:
            self._log('POLICY', time_s=now, target_id=self._physical_target, role='Student', input_sources='camera_joint_feedback')
        from harvest_runtime.student60 import decode_command, encode_command
        goals, servo = decode_command(command, mission.lower, mission.upper)
        self.device.configure_actuator(dict(stiffness=[25.]*5+[float(servo[0])], velocity_limits=[1.2]*5+[float(servo[1])]))
        self.device.command(goals)
        # 추론 제안을 재사용하지 않고 PhysX가 보관한 실제 목표/gain/속도를 읽어 ack한다.
        written = self.device.applied_command()
        if np.max(abs(written['joint_targets']-goals)) > 1e-6:
            raise RuntimeError('Student 최종 명령과 실제 drive 목표 불일치')
        actual = encode_command(written['joint_targets'], [written['stiffness'][-1], written['velocity_limits'][-1]],
                                mission.lower, mission.upper)
        mission.acknowledge(actual)
        if len(mission.harvested) > self._confirmed_targets:
            self._confirmed_targets = len(mission.harvested)
            self.controller.basket_sensor.counter.disarm()
            self._laser_armed = False
            self.device.clear_target()
            self._physical_target = None
        self.state['stage'] = mission.state
        self._log('STUDENT_CONTROL', time_s=now, q=self.device.joint_positions(), qd=self.device.joint_velocities(),
            final_joint_targets=written['joint_targets'], applied_actuator=written, command=actual, note=note,
            camera_stamps={k: d['stamp_s'] for k, d in self.controller.rig.capture().items()})
        if mission.state == 'DONE':
            self._stop(now, 'SUCCESS', '', 'student_laser_passages_confirmed_arms_stowed')
        elif mission.state in ('STOPPING', 'FAILED'):
            # ArmSession의 정지 측정 상태를 사용한다. vendor STOPPING 표시는 먼저 되돌린다.
            self.state['stage'] = 'STUDENT_FAILED'
            self._stop(now, 'FAILED', 'STUDENT_MISSION_FAILED', str(mission.failure))

    def _inventory(self, now: float) -> None:
        from harvest_vision.student60_tracking import AssignedFruitTracker
        from harvest_runtime.student60_mission import HarvestTarget, StudentHarvestMission
        from harvest_runtime.student60_mission_session import lifted_return_path
        runtime = self.controller
        if not runtime.rig.last:
            return
        capture = runtime.rig.capture()
        if self._directory is not None and not (self._directory/'rear_initial.png').exists():
            from PIL import Image
            for name, data in capture.items():
                Image.fromarray(data['rgb']).save(self._directory/f'{name}_initial.png')
            np.savez_compressed(self._directory/'camera_initial.npz',
                **{f'{name}_{key}': data[key] for name, data in capture.items()
                   for key in ('rgb', 'raw_depth_m', 'aligned_depth_m')}, right_ir=capture['right']['ir']['ir_right'])
            (self._directory/'camera_initial_metadata.json').write_text(json.dumps(
                {name: {k: data[k] for k in ('intrinsics', 'world_from_optical', 'stamp_s', 'pose_stamp_s', 'capture_joint_rad', 'fk_max_error', 'renderer_checks')}
                 for name, data in capture.items()}, default=lambda x: np.asarray(x).tolist(), indent=2)+'\n')
        _, detections = runtime.camera.observe(capture, now)
        tracker = AssignedFruitTracker(runtime.camera.roi)
        tracker.update(detections, now)
        targets = [HarvestTarget(key, item['label'], tuple(item['position_m']))
            for key, item in tracker.snapshot(now).items() if item['valid'] and item['label'] in ('Red', 'Yellow')]
        # 제공 tracker의 측정 여유 영역은 인접 창까지 포함할 수 있다.
        # 현재 농장 작업의 기존 고정 근거리 범위를 영상 관측에만 적용한다.
        from .teacher_device import continuous_near_mask
        observed_targets = targets
        points = np.asarray([t.anchor_arm_m for t in targets], dtype=float).reshape(-1, 3)
        eligible = continuous_near_mask(points, self.device.config)
        targets = [t for t, allowed in zip(targets, eligible) if allowed]
        self._log('CAMERA_INVENTORY', time_s=now, expected_count=self.job['expected_count'],
            visible_ripe_count=len(observed_targets), task_workspace_min_m=self.device.config['workspace_arm_min_m'],
            task_workspace_max_m=self.device.config['workspace_arm_max_m'],
            targets=[dict(target_id=t.target_id, label=t.label, anchor_arm_m=t.anchor_arm_m) for t in targets],
            detections=[{k: d.get(k) for k in ('label', 'confidence', 'candidate_valid', 'candidate_reason', 'grasp_estimate_arm_m', 'bbox')} for d in detections])
        # 예찰 예상량은 참고값이다. 관측 시간을 확보한 뒤 팔 카메라에서 확인한
        # 작업 가능 목록만 확정하며, 예상량과의 차이로 작업을 거부하지 않는다.
        if now-self._inventory_start < runtime.profile['inventory_timeout_s']:
            return
        if not targets:
            self._stop(now, 'SUCCESS', '', 'student_no_reachable_targets_arms_stowed')
            return
        # 영상 목표 목록 확정 뒤 outcome만 실제 prim에 대응한다. truth로 빈 목록을 채우지 않는다.
        candidates = self.device.candidates(self._all_attempted)
        self._outcomes = map_outcomes(targets, candidates, runtime.profile['assignment_gate_m'], runtime.profile['assignment_ambiguity_m'])
        self.mission = StudentHarvestMission(mission_session(runtime.camera, self._dock_arm), targets, runtime.config,
            lambda q, home: lifted_return_path(runtime.kin, runtime.contract, runtime.config, q, home), task_list_complete=True)
        self._candidates = [dict(target_id=self._outcomes[t.target_id], camera_target_id=t.target_id) for t in self.mission.targets]
        self._log('CANDIDATES', time_s=now, role='Student', candidates=self._candidates)
        self.state['stage'] = 'STOW_WAIT'
        self._log('STUDENT_ASSIGNED', time_s=now, outcome_only_mapping=self._outcomes, mission=self.mission.report())

    def observe_physics_tick(self, dt_s: float, sim_time_s: float) -> None:
        if self.state['status'] != 'RUNNING' or self._blocked:
            return
        try:
            self.device.observe_physics_tick(dt_s, sim_time_s)
            contacts = self.device.contacts_for_recovery()
            fingers = np.linalg.norm(contacts['finger_net_forces_world'], axis=1)
            if np.linalg.norm(contacts['arm_forces_world'], axis=1).max() > 12.:
                self._fault = 'arm_collision'
            if self._physical_target is None and fingers.max() > 2.:
                self._fault = 'motion_finger_collision'
            allowed = self._successful_ids | ({self._physical_target} if self._physical_target else set())
            if any(self._initial_attached[i] and not self.device.attachments.attached[i] and path not in allowed
                   for i, path in enumerate(self.device.paths)):
                self._fault = 'unassigned_fruit_detached'
            if self._physical_target is not None:
                self._update_box(dt_s, sim_time_s)
            event = self.controller.basket_sensor.sample(sim_time_s)
            sample = self.controller.basket_sensor.last
            key = (tuple(sample['blocked']), sample['state'])
            if key != self._laser_last:
                self._log('BASKET_LASER', **sample)
                self._laser_last = key
            if event is not None:
                self._record_laser_passage(event)
        except Exception as error:
            self._handle_error(sim_time_s, error)

    def _update_box(self, dt: float, now: float) -> None:
        """기존 접촉·낙하 안전을 검사한다. 위치·속도·안착 시간은 성공 입력이 아니다."""
        sample = self.device.sample()
        target_force = max(np.linalg.norm(sample['fixed_force']), np.linalg.norm(sample['moving_force']))
        unwanted = max(np.linalg.norm(sample['fixed_net_force']-sample['fixed_force']),
                       np.linalg.norm(sample['moving_net_force']-sample['moving_force']))
        if target_force > self.controller.contract['task']['max_contact_force']:
            self._fault = 'finger_high_force'
        if unwanted > 12.:
            self._fault = 'unwanted_finger_collision'
        # 미집계 시도의 기존 낙하/이탈 안전 감시는 유지한다. 성공 근거로는 쓰지 않는다.
        if self._physical_target not in self._successful_ids:
            if sample['fruit_position'][2] < .48:
                self._fault = 'target_dropped_below_box'
            if np.linalg.norm(sample['fruit_position'][:2]) > 1.5:
                self._fault = 'target_stray'

    def _record_laser_passage(self, event: dict) -> None:
        """익명 통과 한 건을 현재 순차 시도에 연결한다. 정지 실패/취소에도 개수는 보존한다."""
        path = self._physical_target
        if not self._laser_armed or path is None or path in self._successful_ids:
            raise RuntimeError('활성 배출 시도 없는 레이저 통과')
        self._successful_ids.add(path)
        record = dict(target_id=path, camera_target_id=self.mission.target.target_id,
            success=True, reason='basket_laser_passage', time_s=event['stamp_s'],
            success_source='basket_parallel_lasers', identity_confirmed=False,
            association='active_attempt_only', passage=dict(event))
        self._attempts.append(record)
        self.state['success_count'] += 1
        self.state['event_seq'] += 1
        self._log('ATTEMPT_RESULT', **record)
        # 원본 mission의 외부 완료 신호 슬롯 이름은 settled다. 여기서는 안착이 아닌
        # 승인된 통과 완료를 매핑한다. 출력 로그에 physical_in_box/안착 성공을 만들지 않는다.
        self._box_evidence = dict(target_id=self.mission.target.target_id, settled=True,
            stamp_s=event['stamp_s'], source='basket_parallel_lasers', identity_confirmed=False)

    def after_frame(self, now: float) -> None:
        try:
            self.controller.rig.after_frame(now)
        except Exception as error:
            if self.state['status'] != 'RUNNING':
                raise
            self._handle_error(now, error)

    def close(self) -> None:
        super().close()
        self.controller.close()
