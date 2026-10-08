"""농장 공통 물리 설정을 Isaac 진입점에 연결한다. 정책·미션은 실행하지 않는다."""
import copy
import json
import math
from pathlib import Path
from typing import Any

import numpy as np

from .harvest_regions import HarvestRegions, RegionSettings


def load_physics_profile(project_root: Path, configs: list[dict]) -> dict | None:
    """장치들이 동일한 물리 프로파일과 시간 간격을 사용하는지 검사한다."""
    paths = {cfg['runtime'].get('robotarm_physics_config') for cfg in configs}
    if len(paths) != 1:
        raise ValueError('모든 장치는 같은 robotarm 물리 프로파일을 사용해야 합니다.')
    value = paths.pop()
    if value is None:
        return None
    path = (project_root / value).resolve()
    if not path.is_relative_to(project_root / 'sim'):
        raise ValueError('시뮬 물리 프로파일은 sim 안에 있어야 합니다.')
    profile = json.loads(path.read_text())
    if not profile.get('enabled', False):
        return None
    if profile.get('adaptive', {}).get('enabled', False):
        RegionSettings.from_mapping(profile['adaptive'], profile['render_hz'])
    for cfg in configs:
        for key in ('physics_hz', 'render_hz'):
            if cfg['runtime'][key] != profile[key]:
                raise ValueError(f'{cfg["robot_id"]}: {key}가 물리 프로파일과 다릅니다.')
    return profile


class PhysicsTicks:
    """물리 tick마다 힘을 갱신하고 렌더는 별도로 분주한다.

    서로 다른 dt에서 World.step(render=True)를 사용하면 렌더 한 번에 여러
    물리 tick이 진행될 수 있다. 줄기 외력 갱신이 빠지지 않도록 명시적으로 분리한다.
    """

    def __init__(self, physics_hz: float, render_hz: float) -> None:
        rates = (float(physics_hz), float(render_hz))
        if any(not math.isfinite(x) or x <= 0 for x in rates):
            raise ValueError('물리/렌더 주기는 유한한 양수여야 합니다.')
        ratio = rates[0] / rates[1]
        if not math.isclose(ratio, round(ratio)) or ratio < 1:
            raise ValueError('물리 주기는 렌더 주기의 정수 배여야 합니다.')
        self.dt = 1. / rates[0]
        self.render_every = round(ratio)
        self.tick = 0

    def step(self, world: Any, physics: Any = None) -> None:
        """외력→물리 한 tick→필요한 렌더 순서로 진행한다."""
        before = float(world.current_time)
        if physics is not None:
            physics.update(self.dt, before)
        world.step(render=False)
        now = float(world.current_time)
        if not math.isclose(now - before, self.dt, rel_tol=1e-5, abs_tol=1e-8):
            raise RuntimeError('Isaac 물리 tick이 설정 간격과 다릅니다. 실행을 재시작하세요.')
        self.tick += 1
        if self.tick % self.render_every == 0:
            world.render()
            if not math.isclose(float(world.current_time), now, rel_tol=0., abs_tol=1e-10):
                raise RuntimeError('렌더 중 물리 시간이 추가로 진행됐습니다.')


def initialize_arm_home(articulation: Any, report: dict) -> None:
    """초기화 또는 정지한 시험의 재배치에서 오른팔6축 pose·속도·drive를 HOME으로 맞춘다."""
    from isaacsim.core.utils.types import ArticulationAction
    home = report.get('home_positions_rad')
    if home is None:
        return
    indices = np.asarray([articulation.get_dof_index(n) for n in report['joint_names']], dtype=np.int32)
    if len(indices) != 6 or len(set(indices)) != 6 or np.any(indices < 0):
        raise RuntimeError('오른팔 6축 articulation 인덱스를 확인할 수 없습니다.')
    positions = np.asarray(home, dtype=np.float32)
    articulation.set_joint_positions(positions, joint_indices=indices)
    articulation.set_joint_velocities(np.zeros(6, dtype=np.float32), joint_indices=indices)
    articulation.apply_action(ArticulationAction(joint_positions=positions, joint_indices=indices))
    if not np.allclose(articulation.get_joint_positions(joint_indices=indices), positions, atol=1e-5):
        raise RuntimeError('오른팔 초기 HOME 배치가 적용되지 않았습니다.')


class HarvestPhysics:
    """세션 USD, 과실 외력, 물리 로그의 수명을 관리한다. 정답은 제어로 보내지 않는다."""

    def __init__(self, stage: Any, project_root: Path, profile: dict) -> None:
        from farm_sim_runtime.fruit_asset_setup import configure_farm_fruits
        self.profile = copy.deepcopy(profile)
        self.project_root = project_root
        survey = json.loads((project_root / profile['survey_config']).read_text())
        self.fruits = configure_farm_fruits(stage, project_root, profile['fruit'], survey)
        self.stage = stage
        self.attachments = None
        self.arm_reports: dict[str, dict] = {}
        self.log = None
        self.directory: Path | None = None
        self.adaptive = bool(profile.get('adaptive', {}).get('enabled', False))
        self.regions = (HarvestRegions(RegionSettings.from_mapping(profile['adaptive'], profile['render_hz']))
                        if self.adaptive else None)
        self.harvesters: dict[str, dict] = {}
        self.activity_gates: dict[str, Any] = {}
        self.direct_activity: dict[str, bool] = {}
        self.activity_log = None
        self.last_runtime_state = None
        self.frame_count = 0
        self.rate_frames: dict[int, int] = {}

    def configure_robot(self, robot_path: str, *, robot_id: str | None = None,
                        activity_config: dict | None = None) -> dict:
        """수확 로봇의 오른팔 학습 물리와 drive, 박스 바닥을 세션에 적용한다."""
        from farm_sim_runtime.robotarm_asset_setup import configure_harvest_arm
        config = copy.deepcopy(self.profile)
        config['box_floor']['asset_path'] = str((self.project_root / config['box_floor']['asset_path']).resolve())
        if config.get('teacher_alignment', {}).get('enabled', False):
            config['teacher_alignment']['asset_path'] = str(
                (self.project_root / config['teacher_alignment']['asset_path']).resolve())
        report = configure_harvest_arm(self.stage, robot_path, config)
        self.arm_reports[robot_path] = report
        if robot_id is not None:
            if robot_id in self.harvesters:
                raise ValueError('중복 수확 로봇 ID: '+robot_id)
            joint = self.stage.GetPrimAtPath(report['joint_paths'][0])
            mounts = joint.GetRelationship('physics:body0').GetTargets()
            if len(mounts) != 1 or not self.stage.GetPrimAtPath(mounts[0]).IsValid():
                raise ValueError('오른팔 장착 body를 찾을 수 없습니다: '+robot_id)
            self.harvesters[robot_id] = dict(robot_path=robot_path, mount_path=str(mounts[0]),
                                           activity_config=copy.deepcopy(activity_config or {}))
            self.direct_activity[robot_id] = False
        return report

    def register(self, world: Any, session: str) -> None:
        """world.reset 전에 과실 view와 실행별 물리 로그를 생성한다."""
        from farm_sim_devices.fruit_attachment import FruitAttachments
        if self.profile.get('teacher_alignment', {}).get('enabled', False):
            from farm_sim_runtime.teacher_arm_alignment import align_teacher_scene
            align_teacher_scene(world)
        self.attachments = FruitAttachments(world, self.fruits, self.profile['stem'], selective=self.adaptive)
        if self.adaptive:
            from farm_sim_devices.harvest_activity import ActivityGate
            for robot_id, entry in self.harvesters.items():
                config = entry['activity_config']
                if config.get('enabled', False):
                    self.activity_gates[robot_id] = ActivityGate(session, robot_id, config.get('lease_s', 2.))
        self.directory = self.project_root / 'sim/runs/robotarm/physics' / session
        self.directory.mkdir(parents=True, exist_ok=True)
        self.log = (self.directory / 'detach_events.jsonl').open('w')
        self.activity_log = (self.directory / 'activity.jsonl').open('w')
        (self.directory / 'setup.json').write_text(json.dumps(dict(
            profile=self.profile, fruits=self.fruits, arms=self.arm_reports, harvesters=self.harvesters,
            policy_execution=False), ensure_ascii=False, indent=2) + '\n')

    def initialize(self) -> None:
        """world.reset 이후 질량과 관성 및 물리 view를 검사한다."""
        self.attachments.initialize()
        print('[harvest_physics] ' + json.dumps(self.attachments.summary()), flush=True)

    def accept_activity(self, robot_id: str, message: dict) -> bool:
        """해당 로봇의 장치 채널에서 온 sim 활동만 받는다. 이동 성공을 수확으로 추정하지 않는다."""
        gate = self.activity_gates.get(robot_id)
        return gate.accept(message) if gate is not None else False

    def set_activity(self, robot_id: str, active: bool) -> None:
        """향후 Isaac 팔 제어기의 시작/종료 연결점. 목표·과실 성공 상태는 변경하지 않는다."""
        if robot_id not in self.direct_activity or type(active) is not bool:
            raise ValueError('등록된 수확 로봇 ID와 bool 활동 상태가 필요합니다.')
        self.direct_activity[robot_id] = active

    def set_harvest_hz(self, rate: int) -> None:
        """수확 활동이 없는 프레임 경계에서 세션의 수확 물리 주기를 변경한다."""
        if type(rate) is not int or rate <= 0 or rate % 60 != 0:
            raise ValueError('수확 물리 주기는 60Hz의 양의 정수 배여야 합니다.')
        if not self.adaptive or self.regions is None:
            raise RuntimeError('수확 물리 주기를 변경하려면 adaptive 물리가 활성화되어야 합니다.')
        if any(self.direct_activity.values()) or any(gate.value() for gate in self.activity_gates.values()):
            raise RuntimeError('수확 또는 물리 관찰을 정지한 뒤 물리 주기를 변경하세요.')
        adaptive: dict = dict(self.profile['adaptive'], harvest_hz=rate)
        settings = RegionSettings.from_mapping(adaptive, self.profile['render_hz'])
        self.regions.settings = settings
        self.profile = dict(self.profile, adaptive=adaptive)

    def prepare_frame(self, sim_time_s: float) -> int:
        """60Hz 프레임 경계에서 영역 합집합·물리 모드·공유 주기를 결정한다."""
        if not self.adaptive:
            return int(self.profile['physics_hz'])
        from pxr import UsdGeom
        cache = UsdGeom.XformCache()
        centers = {}
        for robot_id, entry in self.harvesters.items():
            gate = self.activity_gates.get(robot_id)
            if self.direct_activity[robot_id] or (gate is not None and gate.value()):
                prim = self.stage.GetPrimAtPath(entry['mount_path'])
                centers[robot_id] = np.asarray(cache.GetLocalToWorldTransform(prim).ExtractTranslation(), dtype=float)
        positions = self.attachments.current_positions()
        selected = self.regions.select(positions, centers, self.attachments.active)
        self.attachments.set_active(selected)
        detached = ~self.attachments.attached
        velocity = (self.attachments.current_velocities()[detached] if detached.any() else np.empty((0, 6)))
        hz = self.regions.required_hz(sim_time_s, requested=bool(centers),
            attached_active=bool(np.any(self.attachments.attached & self.attachments.active)),
            detached_velocities=velocity)
        self.frame_count += 1
        self.rate_frames[hz] = self.rate_frames.get(hz, 0)+1
        state = (hz, tuple(sorted(centers)), tuple(np.flatnonzero(self.attachments.active).tolist()))
        if state != self.last_runtime_state:
            record = dict(event='PHYSICS_ACTIVITY', sim_time_s=sim_time_s, physics_hz=hz,
                          active_robot_ids=sorted(centers), active_fruit_count=int(self.attachments.active.sum()),
                          active_fruit_paths=[self.attachments.paths[i] for i in np.flatnonzero(self.attachments.active)],
                          detached_count=int(detached.sum()))
            self.activity_log.write(json.dumps(record, ensure_ascii=False)+'\n')
            self.activity_log.flush()
            print('[harvest_physics] '+json.dumps(record, ensure_ascii=False), flush=True)
            self.last_runtime_state = state
        return hz

    def update(self, dt_s: float, sim_time_s: float) -> None:
        """물리적으로 발생한 분리만 기록한다. 수확 성공으로 간주하지 않는다."""
        events = self.attachments.update(dt_s, sim_time_s)
        for event in events:
            self.log.write(json.dumps(event, ensure_ascii=False) + '\n')
        if events:
            self.log.flush()

    def close(self) -> None:
        """종료 시 마지막 결합 상태를 기록하고 파일을 닫는다."""
        if self.directory is not None and self.attachments is not None:
            (self.directory / 'summary.json').write_text(json.dumps(
                dict(self.attachments.summary(), adaptive=self.adaptive, frame_count=self.frame_count,
                     rate_frames=self.rate_frames), ensure_ascii=False, indent=2) + '\n')
        if self.log is not None:
            self.log.close()
        if self.activity_log is not None:
            self.activity_log.close()
