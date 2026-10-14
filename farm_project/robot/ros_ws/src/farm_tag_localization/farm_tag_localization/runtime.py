"""보정 입력/작업 수명 관리. 주행 명령이나 ROS 노드를 만들지 않는다."""
from pathlib import Path
from types import SimpleNamespace
import hashlib
import json
import math
import numpy as np
import yaml
from .observer import Camera, Landmark, Observer, QualityLimits
from .geometry import covariance


def resolve(root: Path, value: str) -> Path:
    """모든 자산 경로는 project_root 기준으로 해석한다."""
    p = Path(value).expanduser()
    return (p if p.is_absolute() else root / p).resolve()


def load_observation_model(root: Path, model_file: str) -> dict:
    """공통 관측모델 기본값에 프로파일의 명시적 설정값을 병합한다."""
    from farm_navigation.configuration import merge_mappings
    model = json.loads(resolve(root, model_file).read_text())
    if 'shared_model_file' not in model:
        return model  # 이전 실물 시험 자산과 보정 프로파일도 같은 관측기를 사용한다.
    shared = json.loads(resolve(root, model['shared_model_file']).read_text())
    if 'shared_model_file' in shared:
        raise ValueError('관측모델의 shared_model_file은 실제 기본값 파일을 참조해야 합니다.')
    overrides = model.get('overrides', {})
    if not isinstance(overrides, dict):
        raise ValueError('관측모델 overrides는 mapping이어야 합니다.')
    return merge_mappings(shared, overrides)


def load_observer(config_file: str, project_root: str, session_id: str) -> tuple:
    root = Path(project_root).expanduser().resolve()
    cfg = yaml.safe_load(resolve(root, config_file).read_text())
    if cfg.get('configured') is not True:
        raise ValueError('태그 등록 미완료: ' + str(cfg.get('setup_required',
            '실제 카메라 보정·태그 좌표 정합 후 configured=true로 지정하세요.')))
    if cfg.get('correction_transport', 'initialpose') not in ('initialpose', 'scan_sync'):
        raise ValueError('알 수 없는 correction_transport')
    assets = json.loads(resolve(root, cfg['assets_file']).read_text())
    model = load_observation_model(root, cfg['model_file'])
    context = SimpleNamespace(session_id=session_id, epoch=0,
        environment_id=cfg['map_id'], map_version=assets['map_version'],
        tag_map_version=assets['tag_map_version'], calibration_version=assets['calibration_version'],
        extrinsics_version=assets['extrinsics_version'], map_frame=cfg['map_frame'],
        base_frame=cfg['base_frame'], tag_source='capture_journal')
    camera = Camera.from_camera_info(assets['camera_info'], rectified=True,
        version=context.calibration_version, pose_solver='ippe_lm')
    if (camera.width, camera.height) != (1280, 720):
        raise ValueError('이번 이식본은 검증한 1280x720 영상/ROI를 사용합니다.')
    tag_cov = covariance(model['tag']['map_base_pose6_covariance_bound'], 6)
    def bound(observer: object, packet: dict, solution: dict, transform: object) -> np.ndarray:
        distance = float(np.linalg.norm(solution['t_camera_tag'][:3, 3]))
        lo, hi = model['tag']['distance_interval_m']
        if not 0 < lo <= distance <= hi:
            raise ValueError('outside_tag_distance')
        return tag_cov.copy()
    observer = Observer(context, camera,
        [Landmark(x['family'], x['tag_id'], x['edge_m'], x['t_map_tag'],
                  section_id=x.get('section_id')) for x in assets['tags']],
        assets['t_base_camera'], QualityLimits(**model['quality']),
        uncertainty_model=bound, covariance_model_id=model['model_ids']['tag'])
    return cfg, observer


def validate_binding(config: dict, environment: dict, root: Path) -> None:
    """새 맵에 예전 좌표 설정을 무심코 연결하지 않도록 파일 식별자를 비교한다."""
    if config.get('configured') is not True:
        raise ValueError('태그 등록 미완료: ' + str(config.get('setup_required',
            '실제 카메라 보정·태그 좌표 정합 후 configured=true로 지정하세요.')))
    for key in ('robot_id', 'map_id'):
        if config[key] != environment[key]:
            raise ValueError('태그/주행 환경 불일치: ' + key)
    map_path = resolve(root, environment['map_yaml'])
    map_data = yaml.safe_load(map_path.read_text())
    image_path = Path(map_data['image'])
    if not image_path.is_absolute():
        image_path = map_path.parent / image_path
    for path, key in ((map_path, 'map_yaml_sha256'), (image_path, 'map_image_sha256')):
        if hashlib.sha256(path.read_bytes()).hexdigest() != config[key]:
            raise ValueError('태그 등록 지도와 현재 지도 불일치: ' + key)


class Lease:
    """작업별 짧은 사용 허가. 유실/프로세스 종료는 보정만 해제한다."""
    def __init__(self, robot_id: str, map_id: str) -> None:
        self.robot_id, self.map_id = robot_id, map_id
        self.token = ''
        self.deadline = 0.0
        self.sequence = {}
        self.closed = set()
        self.begin_ns = 0
        self.section_id = None

    def update(self, data: dict, ros_ns: int, mono: float) -> None:
        if data['robot_id'] != self.robot_id or data['map_id'] != self.map_id:
            return
        token, seq = data['token'], data['sequence']
        if not isinstance(token, str) or not token or type(seq) is not int:
            return
        if token in self.closed or seq <= self.sequence.get(token, -1):
            return
        age = (ros_ns - int(data['stamp_ns'])) / 1e9
        if not 0 <= age <= 2.0:
            return
        if self.active(mono) and token != self.token:
            return
        if data['enabled'] is not True:
            self.sequence[token] = seq
            self.closed.add(token)
            if self.token == token:
                self.deadline = 0.0
            return
        section_id = data.get('section_id')
        if section_id is not None and (not isinstance(section_id, str) or not section_id):
            return
        # 계산 중인 관측이 다른 구간으로 재해석되지 않도록 구간 전환은 새 토큰으로 한다.
        if token == self.token and section_id != self.section_id:
            return
        self.sequence[token] = seq
        begin_ns = int(data['begin_ns'])
        if not 0 < begin_ns <= int(data['stamp_ns']):
            return
        self.token, self.begin_ns, self.section_id = token, begin_ns, section_id
        self.deadline = mono + 2.0

    def active(self, mono: float) -> bool:
        return bool(self.token) and mono < self.deadline

    def accepts(self, token: str, stamp_ns: int, mono: float) -> bool:
        return self.active(mono) and token == self.token and stamp_ns >= self.begin_ns


class Journal:
    """기존 촬영 기록의 추가 행을 읽는다. 시작 전 기록은 제외하고 최신 완성 행을 반환한다."""
    def __init__(self, folder: Path, calibration_version: str) -> None:
        settings = json.loads((folder / 'settings.json').read_text())
        if settings['calibration_sha256'] != calibration_version.split(':')[-1]:
            raise ValueError('calibration_mismatch')
        self.file = (folder / 'detections.jsonl').open()
        self.file.seek(0, 2)

    def latest(self) -> dict | None:
        last = None
        for _ in range(256):
            pos = self.file.tell()
            line = self.file.readline()
            if not line:
                break
            if not line.endswith('\n'):
                self.file.seek(pos)
                break
            try:
                last = json.loads(line)
            except ValueError:
                continue
        return last

    def close(self) -> None:
        self.file.close()


def time_valid(image_ns: int, pose_ns: int, now_ns: int) -> bool:
    return (image_ns <= pose_ns <= now_ns and
            0 <= now_ns - image_ns <= 1_000_000_000 and
            0 <= now_ns - pose_ns <= 500_000_000)
