"""독립 수확 시험 패널. UI 콜백은 요청만 넣고 변경은 렌더 프레임 경계에서 한다.

배치는 정지한 차체·적재 과실을 함께 옮기고 오른팔 HOME을 초기화한다.
수확은 기존 ArmSession/Teacher가 수행하며 재부착·성공 조작·World.reset은 하지 않는다.
"""
from __future__ import annotations

import json
import math
from pathlib import Path
import random
import time
from typing import Any
import uuid

import numpy as np

from farm_sim_devices.stem_physics import quaternion_matrix
from .harvest_test_placement import find_placements, footprint_is_clear

def load_clearance_check(project_root: Path, config: dict) -> Any:
    """기존 지도 자유 셀과 수확 Nav2 footprint를 읽어 차체 배치 여유를 검사한다."""
    import yaml
    from PIL import Image
    from farm_navigation.configuration import load_nav2_parameters
    config_root = project_root / 'sim/ros_ws/src/farm_sim_config'
    map_path = config_root / config['map_yaml']
    metadata = yaml.safe_load(map_path.read_text())
    nav = load_nav2_parameters(config_root / 'config/nav2_harvest.yaml', project_root)
    costmap = nav['local_costmap']['local_costmap']['ros__parameters']
    footprint = np.asarray(json.loads(costmap['footprint']), dtype=float)
    with Image.open(map_path.parent / metadata['image']) as source:
        grey = np.asarray(source.convert('L'), dtype=float) / 255.
    occupancy = grey if metadata.get('negate', 0) else 1.-grey
    free = np.flipud(occupancy < float(metadata['free_thresh'])).copy()

    def is_clear(pose: dict) -> bool:
        return footprint_is_clear(free, float(metadata['resolution']), metadata['origin'],
                                  footprint, [pose['x'], pose['y'], pose['yaw']],
                                  float(costmap.get('footprint_padding', 0.)))
    return is_clear


def base_transform(robot: dict) -> np.ndarray:
    """현재 articulation pose를 논리 base_footprint world 변환으로 바꾼다."""
    position, orientation = robot['base'].pose()
    transform = np.eye(4)
    transform[:3, :3] = quaternion_matrix(np.asarray(orientation, dtype=float))
    transform[:3, 3] = position
    return transform @ robot['T_asset_control']


class HarvestTestController:
    """버튼 허용 조건·시험 배치·기존 수확 요청·로그를 관리한다. ROS는 사용하지 않는다."""

    def __init__(self, robot: dict, physics: Any, task: dict, project_root: Path,
                 *, seed: int | None = None) -> None:
        self.robot, self.physics, self.task = robot, physics, task
        self.arm, self.device = robot['arm'], robot['arm_device']
        if self.arm is None or not physics.adaptive:
            raise ValueError('수확 시험 UI에는 Teacher와 adaptive 물리가 필요합니다.')
        settings = physics.regions.settings
        if (settings.idle_hz, settings.harvest_hz, physics.profile['render_hz']) != (60, 60, 30):
            raise ValueError('시험 UI는 대기60Hz/수확60Hz/렌더30Hz 설정을 요구합니다.')
        survey = json.loads((project_root / physics.profile['survey_config']).read_text())
        self.sections = survey['sections']
        self.registration = np.asarray(task['evaluation']['T_map_world'], dtype=float)
        self.base_arm = np.linalg.inv(base_transform(robot)) @ self.device.arm_world_transform()
        self.base_z_map = float((self.registration @ base_transform(robot))[2, 3])
        self.pose_is_clear = load_clearance_check(project_root, robot['cfg'])
        self.rng = random.Random(seed)
        self.pending = ''
        self.physics_only = False
        self.placement: dict | None = None
        self.ready = False
        self.stable_since: float | None = None
        self.candidates: list[dict] = []
        self.notice = 'Click Place robot to choose a reachable test position.'
        self._last_state: tuple | None = None
        self._show_terminal = False
        self.directory = Path(task['harvest_robot']['scene_snapshot_file']).parent
        self.directory.mkdir(parents=True, exist_ok=True)
        self.log = (self.directory / 'ui_events.jsonl').open('w')
        self._event('OPEN', seed=seed, session=self.arm.session,
                    physics_log=str(physics.directory), teacher_log=str(self.arm.log_root / self.arm.session))

    def _event(self, event: str, **data: Any) -> None:
        """배치 및 실제 관측 결과를 실행별 JSONL에 남긴다."""
        self.log.write(json.dumps(dict(event=event, **data), ensure_ascii=False) + '\n')
        self.log.flush()

    def request(self, action: str) -> None:
        """UI의 중복 클릭은 한 개 요청으로 합친다. 물리는 여기서 변경하지 않는다."""
        if action in ('place', 'harvest', 'cancel', 'physics') and not self.pending:
            self.pending = action

    def _stationary(self) -> bool:
        """측정 차체·관절 속도를 기존 Teacher 시작 허용값과 대조한다."""
        articulation = self.robot['base'].robot
        linear = np.asarray(articulation.get_linear_velocity(), float)
        angular = np.asarray(articulation.get_angular_velocity(), float)
        q, qd = self.device.joint_positions(), self.device.joint_velocities()
        config = self.robot['arm_profile']['session']
        return bool(all(np.isfinite(value).all() for value in (linear, angular, q, qd))
                    and np.linalg.norm(linear[:2]) < config['base_linear_limit_m_s']
                    and abs(angular[2]) < config['base_angular_limit_rad_s']
                    and np.max(abs(qd)) <= .5)

    def _stationary_home(self) -> bool:
        """수확 시작에는 정지 외에 실제 HOME 관절 위치도 요구한다."""
        return bool(self._stationary() and np.max(abs(self.device.joint_positions()-self.device.home)) <= .06)

    @property
    def can_place(self) -> bool:
        """정지가 확인된 시험만 다음 배치에서 HOME을 초기화할 수 있다."""
        return bool(not self.physics_only and not self.arm.busy and self.arm.state['safe_stopped']
                    and self._stationary())

    @property
    def can_harvest(self) -> bool:
        """적재 이력은 유지하며 실제 HOME에 있는 정지 팔만 새 수확을 시작한다."""
        return bool(self.can_place and self._stationary_home())

    def _send(self, op: str, **extra: Any) -> bool:
        """외부 Action과 같은 ArmSession 요청 계약을 로컬에서 사용한다."""
        now = time.monotonic()
        message = dict(kind='harvest_arm', op=op, session=self.arm.session,
                       robot_id=self.arm.robot_id, seq=time.monotonic_ns(), sent=now,
                       job_id=self.arm.state['job_id'])
        message.update(extra)
        return self.arm.accept(message, now=now)

    def _place(self, now: float) -> None:
        """다음 시험을 위해 차체·적재 과실을 함께 배치하고 오른팔 HOME을 초기화한다."""
        if not self.can_place:
            raise ValueError('Wait for confirmed base and arm stop before preparing the next test.')
        attachments = self.physics.attachments
        choices = find_placements(attachments.records, attachments.current_positions(),
                                  attachments.attached, self.arm.attempted_target_ids,
                                  self.sections, self.registration, self.base_arm,
                                  self.base_z_map, self.device.config, pose_is_clear=self.pose_is_clear)
        if self.placement is not None:
            alternatives = [p for p in choices if p['source_target_id'] != self.placement['source_target_id']]
            choices = alternatives or choices
        if not choices:
            self.ready, self.placement = False, None
            raise ValueError('No unattempted ripe fruit satisfies the route, reach and map clearance checks.')
        choice = self.rng.choice(choices)
        from pxr import Gf
        from .harvest_physics import initialize_arm_home
        transform = np.asarray(choice['T_world_base']) @ np.linalg.inv(self.robot['T_asset_control'])
        rotation = Gf.Matrix4d(*map(float, transform.T.reshape(-1))).ExtractRotationQuat()
        orientation = np.array([float(rotation.GetReal()), *map(float, rotation.GetImaginary())])
        deposited = sorted(self.arm.deposited_target_ids)
        indices = np.asarray([attachments.paths.index(path) for path in deposited], dtype=np.int32)
        if deposited:
            escaped = self.device.escaped_deposits(deposited)
            if escaped:
                raise ValueError(f'Previously deposited fruit left the basket: {escaped}. Restart this test scene.')
            # 시험 배치의 순간이동만 보상한다. 과실의 바구니 상대 pose·속도·분리 상태를 유지한다.
            delta = np.asarray(choice['T_world_base']) @ np.linalg.inv(base_transform(self.robot))
            positions, orientations = attachments.view.get_world_poses(indices=indices)
            positions = np.asarray(positions) @ delta[:3, :3].T + delta[:3, 3]
            rotations = delta[:3, :3] @ quaternion_matrix(np.asarray(orientations))
            quaternions = []
            for fruit_rotation in rotations:
                matrix = np.eye(4)
                matrix[:3, :3] = fruit_rotation
                quaternion = Gf.Matrix4d(*map(float, matrix.T.reshape(-1))).ExtractRotationQuat()
                quaternions.append([float(quaternion.GetReal()), *map(float, quaternion.GetImaginary())])
            velocities = np.asarray(attachments.view.get_velocities(indices=indices)).reshape(-1, 2, 3)
            velocities = (velocities @ delta[:3, :3].T).reshape(-1, 6)
        self.robot['gate'].stop()
        base = self.robot['base']
        base.command(0., 0.)
        base.robot.set_world_pose(position=transform[:3, 3], orientation=orientation)
        base.robot.set_linear_velocity(np.zeros(3))
        base.robot.set_angular_velocity(np.zeros(3))
        initialize_arm_home(base.robot, self.physics.arm_reports[self.device.robot_path])
        if deposited:
            attachments.view.set_world_poses(positions=positions, orientations=np.asarray(quaternions), indices=indices)
            attachments.view.set_velocities(velocities, indices=indices)
        self.robot['initial_z'] = float(transform[2, 3])
        self.placement, self.ready, self.stable_since = choice, False, None
        self._show_terminal = False
        self.notice = f"{choice['section_id']} placed. Checking measured stop, HOME and reachable fruit."
        self._event('PLACE', sim_time_s=now, placement=choice,
                    home_initialized=True, transported_deposit_ids=deposited)

    def before_frame(self, now: float, *, playing: bool) -> None:
        """World.step 전 요청을 처리하고 실행 중 lease를 갱신한다."""
        if self.arm.state['status'] == 'RUNNING':
            self._send('keepalive')
        action, self.pending = self.pending, ''
        if not playing:
            self.ready, self.stable_since = False, None
            if action:
                self.notice = 'Press Isaac Play before using the test buttons.'
            return
        try:
            if action == 'place':
                self._place(now)
            elif action == 'harvest':
                # 마지막 렌더 후 실제 후보가 바뀌었는지 시작 직전에 재검사한다.
                candidates = self.device.candidates(self.arm.attempted_target_ids)
                if not self.ready or not self.can_harvest or not candidates:
                    raise ValueError('Place the robot and wait for measured stop and reachable fruit.')
                placement = self.placement
                job = uuid.uuid4().hex
                accepted = self._send('start', job_id=job, map_id=self.arm.map_id,
                    task_id='harvest_test_ui_' + job, window_id=placement['section_id'],
                    expected_count=len(candidates),
                    goal_pose=dict(x=placement['x'], y=placement['y'], yaw=placement['yaw']))
                if not accepted:
                    raise RuntimeError('The arm rejected the harvest request.')
                self.ready = False
                self._show_terminal = True
                self.notice = 'Harvesting. Waiting for the physical result and arm return.'
                self._event('HARVEST', sim_time_s=now, job_id=job,
                            candidate_ids=[c['target_id'] for c in candidates])
            elif action == 'cancel' and self.arm.state['status'] == 'RUNNING':
                self._send('cancel')
                self.notice = 'Stop requested. Waiting for measured arm stop.'
                self._event('CANCEL', sim_time_s=now)
            elif action == 'physics':
                if self.physics_only:
                    self.physics.set_activity(self.arm.robot_id, False)
                    self.physics_only = False
                    self.notice = 'Physics-only OFF. Moving fruit stays dynamic until settled.'
                else:
                    if not self.can_place or self.placement is None:
                        raise ValueError('Place and stop the robot before enabling physics-only observation.')
                    self.physics.set_activity(self.arm.robot_id, True)
                    self.physics_only = True
                    self.ready = False
                    self._show_terminal = False
                    self.notice = (f'Physics-only ON: nearby fruit at {self.physics.regions.settings.harvest_hz}Hz; '
                                   'arm policy is idle.')
                self._event('PHYSICS_ONLY', sim_time_s=now, enabled=self.physics_only)
        except (ValueError, RuntimeError) as error:
            self.notice = str(error)
            self._event('REJECTED', sim_time_s=now, action=action, reason=str(error))

    def after_frame(self, now: float, physics_hz: float) -> None:
        """배치 후 측정과 결과를 갱신한다. 물리 주기 표시로 성공을 대신하지 않는다."""
        self.candidates = self.device.candidates(self.arm.attempted_target_ids)
        idle_ready = bool(self.placement is not None and self.can_harvest and self.candidates)
        if idle_ready:
            self.stable_since = now if self.stable_since is None else self.stable_since
        else:
            self.stable_since = None
        self.ready = bool(idle_ready and now-self.stable_since >= .5)
        state = self.arm.telemetry()
        signature = (state['job_id'], state['status'], state['stage'], state['event_seq'],
                     physics_hz, int(self.physics.attachments.active.sum()), self.ready)
        if signature != self._last_state:
            self._event('STATE', sim_time_s=now, physics_hz=physics_hz,
                        active_fruit_count=int(self.physics.attachments.active.sum()), ready=self.ready, arm=state)
            self._last_state = signature
        if self._show_terminal and state['job_id'] and state['status'] in ('SUCCESS', 'FAILED', 'CANCELED'):
            self.notice = (f"Job {state['status']} | Deposited {state['success_count']} / Failed {state['failed_count']}"
                           + (f" | {state['error_code']}: {state['error_message']}" if state['error_code'] else ''))
            if not state['safe_stopped']:
                self.notice += ' | Stop unconfirmed: restart the test.'
            elif not self._stationary_home():
                self.notice += ' | Click Place robot to initialize HOME for the next test.'
            else:
                self.notice += ' | Ready for another placement or remaining reachable fruit.'
        elif self.ready:
            self.notice = 'Placement and measured stop confirmed. Click Harvest.'

    def close(self) -> None:
        """이벤트 파일을 닫는다. World/정책 수명은 기존 런타임이 관리한다."""
        try:
            if self.physics_only:
                self.physics.set_activity(self.arm.robot_id, False)
        finally:
            self.log.close()


class HarvestTestPanel:
    """Isaac 뷰포트 옆 두 시험 버튼과 측정 상태를 표시한다."""

    def __init__(self, controller: HarvestTestController) -> None:
        import omni.ui as ui
        self.controller = controller
        from .harvest_physics_inspector import FruitPhysicsInspector, collision_display
        self.inspector = FruitPhysicsInspector(controller)
        collision_display(1)
        self._last_update = -math.inf
        self._last_placement = None
        self.pending_hz: int | None = None
        self._fps_start = time.monotonic()
        self._fps_frames = 0
        self.fps = 0.
        self.window = ui.Window('Harvest test', width=420, height=765,
                                position_x=1010, position_y=65, flags=ui.WINDOW_FLAGS_NO_CLOSE)
        style = {'font_size': 16}
        self.window.frame.style = {'Label': style, 'Button': style}
        with self.window.frame:
            with ui.VStack(spacing=8):
                ui.Label('ROBOT ARM HARVEST TEST', height=28)
                ui.Label('Random placement > Measured stop > Harvest', height=24)
                with ui.HStack(height=30, spacing=8):
                    ui.Label('Harvest physics Hz', width=155)
                    self.hz_input = ui.IntField(identifier='harvest_physics_hz')
                    self.hz_input.model.set_value(60)
                    self.hz_input.enabled = False
                    self.hz_apply = ui.Button('Apply', width=70, identifier='apply_harvest_hz',
                                             clicked_fn=self.request_hz, enabled=False)
                self.hz_feedback = ui.Label('60 Hz fixed / Teacher60 response6',
                                            height=32, word_wrap=True)
                with ui.HStack(height=46, spacing=10):
                    self.place = ui.Button('1. Place robot', identifier='place_robot', clicked_fn=lambda: controller.request('place'))
                    self.harvest = ui.Button('2. Harvest', identifier='start_harvest', clicked_fn=lambda: controller.request('harvest'))
                self.cancel = ui.Button('Stop harvest', identifier='stop_harvest', height=30, clicked_fn=lambda: controller.request('cancel'))
                self.physics_button = ui.Button('Physics only: OFF', height=32,
                                                clicked_fn=lambda: controller.request('physics'))
                ui.Label('Collision display (does not change physics)', height=22)
                with ui.HStack(height=28, spacing=5):
                    ui.Button('Hide', clicked_fn=lambda: collision_display(0))
                    ui.Button('Selected', clicked_fn=lambda: collision_display(1))
                    ui.Button('All', clicked_fn=lambda: collision_display(2))
                ui.Button('Select test fruit + robot', height=27, clicked_fn=self.inspector.select_target)
                self.rate = ui.Label('', height=44, word_wrap=True)
                self.location = ui.Label('', height=44, word_wrap=True)
                self.target = ui.Label('', height=48, word_wrap=True)
                self.result = ui.Label('', height=35, word_wrap=True)
                self.notice = ui.Label(controller.notice, height=65, word_wrap=True)
                self.timing = ui.Label('', height=44, word_wrap=True)
        self.harvest.enabled, self.cancel.enabled = False, False
        self.inspection_window = ui.Window('Fruit physics inspector', width=940, height=255,
                                           position_x=60, position_y=620, flags=ui.WINDOW_FLAGS_NO_CLOSE)
        with self.inspection_window.frame:
            with ui.HStack(spacing=10):
                self.inspection_text = ui.Label('Place a robot or select a fruit in the Stage.',
                    width=570, word_wrap=True, style={'font_size': 15})
                with ui.VStack(spacing=6):
                    ui.Label('Markers: yellow anchor, green tip, cyan COM\nRed: gravity force (1m/N display scale)',
                             height=50, word_wrap=True)
                    self.connection = ui.CheckBox()
                    self.connection.model.set_value(True)
                    self.connection.model.add_value_changed_fn(
                        lambda model: setattr(self.inspector, 'show_connection', model.get_value_as_bool()))
                    ui.Label('Show virtual stem / gravity\n\nPhysics-only ON lets fruit move without policy.\nSelect a fruit to inspect its actual state.',
                             word_wrap=True)

    def request_hz(self) -> None:
        """입력값은 다음 프레임 경계에서 적용한다."""
        self.pending_hz = self.hz_input.model.get_value_as_int()

    def apply_hz(self, now: float) -> None:
        """정지한 시험에서 다음 수확에 사용할 주기를 변경한다."""
        if self.pending_hz is None:
            return
        rate, self.pending_hz = self.pending_hz, None
        try:
            if not self.controller.can_place:
                raise ValueError('Stop the test and wait for measured stop before changing Hz.')
            self.controller.physics.set_harvest_hz(rate)
        except (ValueError, RuntimeError) as error:
            self.hz_feedback.text = str(error)
            self.controller._event('REJECTED', sim_time_s=now, action='set_harvest_hz', reason=str(error))
            return
        self.hz_feedback.text = f'Applied {rate} Hz. Policy 20 Hz / render 30 Hz.'
        self.controller._event('HARVEST_HZ', sim_time_s=now, harvest_hz=rate)

    def before_render(self, now: float, physics_hz: float) -> None:
        """동일 프레임의 진단과 표식을 갱신한다. 팔/과실에 외력은 추가하지 않는다."""
        self.inspector.update(now, physics_hz)
        self.inspector.draw()

    def update(self, now: float, physics_hz: float, *, playing: bool = True) -> None:
        """UI 갱신은 wall 10Hz로 제한하고 배치할 때 카메라를 작업 팔 쪽으로 맞춘다."""
        controller = self.controller
        if controller.placement is not self._last_placement and controller.placement is not None:
            self._last_placement = controller.placement
            self.inspector.select_target()
            from isaacsim.core.utils.viewports import set_camera_view
            from omni.kit.viewport.utility import get_active_viewport
            transform = np.asarray(controller.placement['T_world_base'])
            target = np.asarray(controller.placement['target_world_m'])
            center = (target + transform[:3, 3]) / 2
            center[2] = target[2] - .1
            # 작업 반대편 통로 위에서 팔과 과실, 바구니가 함께 보이도록 한다.
            eye = center + transform[:3, :3] @ np.array([-1.6, -1.8, 1.4])
            viewport = get_active_viewport()
            if viewport is not None:
                viewport.camera_path = '/OmniverseKit_Persp'
                set_camera_view(eye=eye, target=center, viewport_api=viewport)
        wall = time.monotonic()
        self._fps_frames += 1
        if wall-self._fps_start >= 1.:
            self.fps = self._fps_frames/(wall-self._fps_start)
            self._fps_start, self._fps_frames = wall, 0
        if wall-self._last_update < .1:
            return
        self._last_update = wall
        self.place.enabled = bool(playing and controller.can_place)
        self.hz_apply.enabled = bool(playing and controller.can_place)
        self.hz_input.enabled = self.hz_apply.enabled
        self.harvest.text = f'2. Harvest ({controller.physics.regions.settings.harvest_hz} Hz)'
        self.harvest.enabled = bool(playing and controller.ready)
        self.cancel.enabled = bool(playing and controller.arm.state['status'] == 'RUNNING')
        self.physics_button.enabled = bool(playing and (controller.physics_only
            or (controller.can_place and controller.placement is not None)))
        self.physics_button.text = 'Physics only: '+('ON (click to stop)' if controller.physics_only else 'OFF')
        from .harvest_physics_inspector import diagnostic_summary
        self.inspection_text.text = (diagnostic_summary(self.inspector.sample) if self.inspector.sample
            else self.inspector.error or 'Place a robot or select a fruit in the Stage.')
        attachments = controller.physics.attachments
        self.rate.text = (f'Physics {physics_hz:g} Hz | Active fruit {int(attachments.active.sum())}/{len(attachments.paths)}'
                          f'\nFPS {self.fps:.1f} | sim {now:.1f}s')
        self.timing.text = (f'Physics dt {1000/physics_hz:.3f}ms | Policy 20Hz | Render target 30Hz\n'
                            'Place prepares HOME for the next test. Teacher physics is fixed at 60 Hz.')
        p = controller.placement
        self.location.text = (f"{p['section_id']} | map ({p['x']:.3f}, {p['y']:.3f}) m | yaw {p['yaw']:.3f} rad"
                              if p else 'Position: click Place robot')
        names = [c['target_id'].rsplit('/', 1)[-1] for c in controller.candidates]
        self.target.text = f"Unattempted reachable fruit ({len(names)}): " + ', '.join(names)
        state = controller.arm.state
        self.result.text = (f"{state['status']} / {state['stage']} | Deposited {state['success_count']}"
                            f" | Failed {state['failed_count']}")
        self.notice.text = controller.notice

    def close(self) -> None:
        """Kit 종료 전에 패널을 해제한다."""
        try:
            self.inspector.close()
        finally:
            self.inspection_window.destroy()
            self.window.destroy()
