"""배치·수확 버튼이 있는 Isaac GUI를 격리된 시뮬 시험 설정으로 실행한다.

일반 Python으로 실행하며 ROS launch나 장치 노드를 시작하지 않는다.
원본 fleet의 수확 장치·Teacher·물리 설정을 재사용하고 포트·snapshot만 분리한다.
"""
from __future__ import annotations

import argparse
from contextlib import ExitStack
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import shlex
import socket
import subprocess
import tempfile
from typing import Mapping, Sequence


DEFAULT_FLEET = Path('sim/ros_ws/src/farm_sim_config/config/harvest_fleet.json')


def read_sim_config(project_root: Path, value: str | Path) -> dict:
    """프로젝트 sim 내부 JSON만 읽어 원본 참조 경계를 유지한다."""
    path = (project_root / value).resolve()
    if not path.is_relative_to(project_root / 'sim'):
        raise ValueError(f'시뮬 설정은 sim 안에 있어야 합니다: {path}')
    data = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(data, dict):
        raise ValueError(f'JSON 객체 설정이 필요합니다: {path}')
    return data


def validate_harvest_config(project_root: Path, device: dict) -> None:
    """시험이 요청한 대기 60Hz·수확 480Hz·렌더 60Hz인지 검사한다."""
    runtime = device['runtime']
    physics = read_sim_config(project_root, runtime['robotarm_physics_config'])
    adaptive = physics.get('adaptive', {})
    if (not physics.get('enabled') or not adaptive.get('enabled')
            or adaptive.get('idle_hz') != 60 or adaptive.get('harvest_hz') != 480
            or physics.get('physics_hz') != 480 or physics.get('render_hz') != 60
            or runtime.get('physics_hz') != 480 or runtime.get('render_hz') != 60):
        raise ValueError('수확 UI에는 adaptive idle 60Hz / harvest 480Hz / render 60Hz 설정이 필요합니다.')
    arm = runtime.get('harvest_arm', {})
    if not arm.get('enabled') or not runtime.get('harvest_activity', {}).get('enabled'):
        raise ValueError('수확 UI에는 harvest_arm 및 harvest_activity가 활성화되어야 합니다.')
    read_sim_config(project_root, arm['profile'])


def allocate_ports(count: int, excluded: set[int]) -> list[int]:
    """동시에 localhost UDP bind로 빈 포트를 고른 뒤 실행 직전에 해제한다."""
    ports: list[int] = []
    with ExitStack() as stack:
        for _ in range(count):
            for _attempt in range(100):
                candidate = stack.enter_context(socket.socket(socket.AF_INET, socket.SOCK_DGRAM))
                candidate.bind(('127.0.0.1', 0))
                port = candidate.getsockname()[1]
                if port not in excluded and port not in ports:
                    ports.append(port)
                    break
            else:
                raise RuntimeError('운영 설정과 겹치지 않는 시험 UDP 포트를 찾지 못했습니다.')
    return ports


def prepare_run(project_root: Path, source_fleet: Path = DEFAULT_FLEET) -> Path:
    """원본을 수정하지 않고 단일 수확 장치용 fleet 경로를 반환한다."""
    root = project_root.expanduser().resolve()
    fleet = read_sim_config(root, source_fleet)
    evaluation = read_sim_config(root, fleet['evaluation_config'])
    stations = read_sim_config(root, fleet['station_config'])
    devices = [read_sim_config(root, value) for value in fleet['device_configs']]
    selected = [device for device in devices if device['robot_id'] == evaluation['robot_id']]
    if len(selected) != 1:
        raise ValueError('fleet 평가 대상에 해당하는 수확 장치가 정확히 하나 필요합니다.')
    device = selected[0]
    if device['map_id'] != evaluation['map_id'] or device['map_id'] != stations['map_id']:
        raise ValueError('수확 장치·평가·station의 map_id가 일치해야 합니다.')
    station = stations['stations'][device['robot_id']]
    if station.get('yaw_rad') is None or station.get('status') == 'DESIGN_PROPOSAL':
        raise ValueError('수확 로봇의 확정된 station이 필요합니다.')
    validate_harvest_config(root, device)

    excluded = set(fleet['clock'].values())
    for source_device in devices:
        excluded.update(source_device['runtime'][key] for key in ('command_port', 'telemetry_port'))
    command, telemetry, clock_command, clock_telemetry = allocate_ports(4, excluded)
    output_parent = (root / 'sim/runs/harvest_test_ui').resolve()
    if not output_parent.is_relative_to(root / 'sim/runs'):
        raise ValueError('수확 UI 결과는 프로젝트 sim/runs 안에 저장해야 합니다.')
    output_parent.mkdir(parents=True, exist_ok=True)
    prefix = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S_')
    directory = Path(tempfile.mkdtemp(prefix=prefix, dir=output_parent))
    device['runtime'].update(command_port=command, telemetry_port=telemetry)
    device['camera']['enabled'] = False
    device['lidar']['enabled'] = False
    device['publish_clock'] = False
    evaluation['evaluation']['snapshot_file'] = str(directory / 'harvest_scene.json')
    evaluation['output_dir'] = str(directory)
    fleet.update(device_configs=[str(directory / 'harvest.json')],
                 evaluation_config=str(directory / 'evaluation.json'),
                 station_config=str(directory / 'stations.json'),
                 clock=dict(command_port=clock_command, telemetry_port=clock_telemetry))
    for name, data in (('harvest.json', device), ('evaluation.json', evaluation),
                       ('stations.json', stations), ('fleet.json', fleet)):
        (directory / name).write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return directory / 'fleet.json'


def build_command(isaac_python: Path, project_root: Path, fleet_config: Path,
                  seed: int | None = None, duration_s: float | None = None) -> list[str]:
    """venv Python 링크를 보존하고 소스 패키지 경로를 명시한 GUI 명령을 만든다."""
    root = project_root.expanduser().resolve()
    runner = root / 'sim/ros_ws/src/farm_sim_runtime/farm_sim_runtime/run_fleet.py'
    command = [str(isaac_python.expanduser().absolute()), str(runner), '--project-root', str(root),
               '--fleet-config', str(fleet_config), '--assets-root', str(root / 'sim/assets'),
               '--harvest-test-ui']
    for package in ('robot/ros_ws/src/farm_common', 'sim/ros_ws/src/farm_sim_devices',
                    'sim/ros_ws/src/farm_sim_runtime'):
        command.extend(('--module-path', str(root / package)))
    if seed is not None:
        command.extend(('--harvest-test-seed', str(seed)))
    if duration_s is not None:
        if not math.isfinite(duration_s) or duration_s <= 0:
            raise ValueError('--duration-s는 유한한 양수여야 합니다.')
        command.extend(('--duration-s', str(duration_s)))
    return command


def configure_run_harvest_hz(project_root: Path, fleet_config: Path, harvest_hz: int) -> None:
    """격리 시험 설정에 물리 프로파일을 복사하고 선택한 수확 주기를 기록한다."""
    if type(harvest_hz) is not int or harvest_hz <= 0 or harvest_hz % 60 != 0:
        raise ValueError('--harvest-hz는 60Hz의 양의 정수 배여야 합니다.')
    root = project_root.expanduser().resolve()
    path = fleet_config.resolve()
    if not path.is_relative_to(root / 'sim/runs/harvest_test_ui'):
        raise ValueError('수확 주기는 sim/runs/harvest_test_ui의 격리 시험 설정에서만 변경할 수 있습니다.')
    fleet = read_sim_config(root, path)
    if len(fleet['device_configs']) != 1:
        raise ValueError('수확 주기 시험에는 단일 장치 fleet 설정이 필요합니다.')
    device_path = (root / fleet['device_configs'][0]).resolve()
    if device_path.parent != path.parent:
        raise ValueError('수확 장치 설정은 격리 시험 fleet과 같은 디렉터리에 있어야 합니다.')
    device = read_sim_config(root, device_path)
    physics = read_sim_config(root, device['runtime']['robotarm_physics_config'])
    physics['adaptive']['harvest_hz'] = harvest_hz
    physics_path = path.parent / 'physics.json'
    device['runtime']['robotarm_physics_config'] = str(physics_path)
    physics_path.write_text(json.dumps(physics, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    device_path.write_text(json.dumps(device, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def launch_environment(isaac_python: Path, source: Mapping[str, str] | None = None) -> dict[str, str]:
    """ROS 셸의 Python/공유 라이브러리 경로를 제외하고 GUI 환경은 보존한다."""
    environment = dict(os.environ if source is None else source)
    for key in ('PYTHONPATH', 'PYTHONHOME', 'LD_LIBRARY_PATH', 'AMENT_PREFIX_PATH',
                'CMAKE_PREFIX_PATH', 'COLCON_PREFIX_PATH'):
        environment.pop(key, None)
    environment.update(VIRTUAL_ENV=str(isaac_python.expanduser().absolute().parent.parent),
                       PYTHONUNBUFFERED='1')
    return environment


def main(argv: Sequence[str] | None = None) -> int:
    """설정을 준비하고 GUI를 실행하거나 --prepare-only 명령만 출력한다."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project-root', type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument('--isaac-python', type=Path,
                        default=Path(os.environ.get('FARM_ISAAC_PYTHON') or '~/isaac/env_isaaclab/bin/python'))
    parser.add_argument('--seed', type=int, help='무작위 배치 순서 재현용 seed')
    parser.add_argument('--duration-s', type=float, help='시험용 실행 시간(시뮬레이션 초)')
    parser.add_argument('--harvest-hz', type=int, default=480, help='수확 물리 주기: 60Hz의 양의 정수 배')
    parser.add_argument('--prepare-only', action='store_true', help='격리 설정과 GUI 실행 명령만 생성')
    args = parser.parse_args(argv)
    if args.duration_s is not None and (not math.isfinite(args.duration_s) or args.duration_s <= 0):
        parser.error('--duration-s는 유한한 양수여야 합니다.')
    if args.harvest_hz <= 0 or args.harvest_hz % 60 != 0:
        parser.error('--harvest-hz는 60Hz의 양의 정수 배여야 합니다.')
    executable = args.isaac_python.expanduser().absolute()
    if not args.prepare_only and (not executable.is_file() or not os.access(executable, os.X_OK)):
        parser.error('Isaac Python을 찾지 못했습니다. --isaac-python 또는 FARM_ISAAC_PYTHON을 지정하세요.')
    try:
        fleet_config = prepare_run(args.project_root)
        configure_run_harvest_hz(args.project_root, fleet_config, args.harvest_hz)
        command = build_command(executable, args.project_root, fleet_config, args.seed, args.duration_s)
    except (KeyError, ValueError, OSError) as error:
        parser.error(str(error))
    (fleet_config.parent / 'launch.json').write_text(json.dumps(dict(
        command=command, seed=args.seed, duration_s=args.duration_s, harvest_hz=args.harvest_hz),
        ensure_ascii=False, indent=2) + '\n',
        encoding='utf-8')
    print(f'수확 UI 시험 설정: {fleet_config}', flush=True)
    print(f'대기 물리 60Hz / 수확 물리 {args.harvest_hz}Hz / 렌더 60Hz · 배치 → 수확', flush=True)
    print(shlex.join(command), flush=True)
    if args.prepare_only:
        return 0
    try:
        return subprocess.run(command, cwd=args.project_root.expanduser().resolve(),
                              env=launch_environment(executable), check=False).returncode
    except KeyboardInterrupt:
        return 130
    except OSError as error:
        parser.error(f'Isaac GUI 실행 실패: {error}')
    return 1


if __name__ == '__main__':
    raise SystemExit(main())
