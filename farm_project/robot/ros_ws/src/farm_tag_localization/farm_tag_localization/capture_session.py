"""성공한 실물 캡처와 태그 어댑터를 함께 관리한다. 주행/TF 소유권은 변경하지 않는다."""
from __future__ import annotations
import argparse
from datetime import datetime
import json
import math
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
import yaml


def resolve(root: Path, value: str) -> Path:
    """실물 설정 경로는 사용자 홈 또는 project_root 기준이다."""
    path = Path(value).expanduser()
    return (path if path.is_absolute() else root / path).resolve()


def capture_environment(environment: dict[str, str]) -> dict[str, str]:
    """카메라 자식에만 전용 DDS 설정을 허용한다. Nav2/어댑터 환경은 유지한다."""
    result = dict(environment)
    for key in ('ROS_LOCALHOST_ONLY', 'ROS_STATIC_PEERS', 'ROS_DISCOVERY_SERVER',
                'FASTRTPS_DEFAULT_PROFILES_FILE', 'FASTDDS_DEFAULT_PROFILES_FILE', 'CYCLONEDDS_URI'):
        result.pop(key, None)
    return result


def capture_command(root: Path, config: dict, session: Path) -> list[str]:
    """현장 실행본은 수정하지 않고 그 CLI를 호출한다."""
    script = resolve(root, config['script'])
    workspace = resolve(root, config['workspace'])
    if not script.is_file():
        raise FileNotFoundError(f'기존 성공 캡처 실행본 없음: {script}; capture config의 script를 지정하세요.')
    if not workspace.is_dir():
        raise FileNotFoundError(f'캘리브레이션 작업공간 없음: {workspace}')
    return [sys.executable, '-u', str(script), '--workspace', str(workspace),
            '--device', config['device'], '--trial-label', config['trial_label'],
            '--output-root', str(session)]


def capture_directory(session: Path) -> Path | None:
    """이 실행에만 할당한 폴더에서 찾는다. 이전 실행의 latest 폴더를 재사용하지 않는다."""
    ready = [p.parent for p in session.glob('*/settings.json')
             if (p.parent / 'detections.jsonl').is_file()]
    if len(ready) > 1:
        raise RuntimeError('현재 세션에 캡처 폴더가 두 개 이상입니다.')
    return ready[0] if ready else None


def adapter_command(root: Path, config: Path, folder: Path, robot_id: str) -> list[str]:
    return ['ros2', 'run', 'farm_tag_localization', 'tag_amcl_adapter', '--ros-args',
            '-r', '__ns:=/' + robot_id, '-r', '/tf:=/' + robot_id + '/tf',
            '-r', '/tf_static:=/' + robot_id + '/tf_static',
            '-p', 'project_root:=' + str(root), '-p', 'config_file:=' + str(config),
            '-p', 'capture_directory:=' + str(folder), '-p', 'use_sim_time:=false']


def stop_owned(process: subprocess.Popen | None, grace_s: float) -> int | None:
    """본 프로세스가 만든 자식 그룹만 종료한다. 이름 기반 pkill을 사용하지 않는다."""
    if process is None:
        return None
    for sig, timeout in ((signal.SIGINT, grace_s), (signal.SIGTERM, 3.), (signal.SIGKILL, 2.)):
        if process.poll() is not None:
            return process.returncode
        try:
            os.killpg(process.pid, sig)
        except ProcessLookupError:
            return process.wait()
        try:
            return process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            pass
    return process.poll()


def main(args: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project-root', type=Path, required=True)
    parser.add_argument('--capture-config', type=Path, required=True)
    parser.add_argument('--robot-id', required=True)
    parser.add_argument('--correction-config', type=Path)
    options, ros_args = parser.parse_known_args(args)
    # launch_ros가 덧붙이는 --ros-args만 허용한다. 이 부모는 ROS Node가 아니다.
    if ros_args and ros_args[0] != '--ros-args':
        parser.error('알 수 없는 인자: ' + ' '.join(ros_args))
    root = options.project_root.expanduser().resolve()
    config = yaml.safe_load(resolve(root, str(options.capture_config)).read_text())
    timeout = float(config.get('startup_timeout_s', 60.))
    if not math.isfinite(timeout) or timeout <= 0:
        raise ValueError('startup_timeout_s는 양의 유한한 초 값이어야 합니다.')
    output = resolve(root, config['output_root'])
    output.mkdir(parents=True, exist_ok=True)
    session = Path(tempfile.mkdtemp(prefix=datetime.now().strftime('%Y%m%d_%H%M%S_'), dir=output))
    stopped = False
    def request_stop(signum: int, frame: object) -> None:
        nonlocal stopped
        stopped = True
    previous = {sig: signal.signal(sig, request_stop) for sig in (signal.SIGINT, signal.SIGTERM)}
    camera = adapter = None
    handles = []
    receipt = dict(robot_id=options.robot_id, correction_enabled=options.correction_config is not None,
                   no_motion_commands=True, session=str(session))
    result = 0
    print('TAG_SESSION: ' + str(session), flush=True)
    try:
        camera_log = (session / 'capture.log').open('w'); handles.append(camera_log)
        camera = subprocess.Popen(capture_command(root, config, session),
            env=capture_environment(dict(os.environ)), stdout=camera_log, stderr=subprocess.STDOUT,
            start_new_session=True)
        deadline = time.monotonic() + timeout
        folder = None
        while not stopped:
            if camera.poll() is not None:
                raise RuntimeError(f'캡처 종료 code={camera.returncode}; {session}/capture.log 확인')
            folder = capture_directory(session)
            if folder is not None:
                break
            if time.monotonic() >= deadline:
                raise TimeoutError(f'검출 기록 폴더 생성 시간 초과; {session}/capture.log 확인')
            time.sleep(.1)
        if not stopped and folder is not None:
            receipt['capture_directory'] = str(folder)
            print('TAG_CAPTURE_DIRECTORY: ' + str(folder), flush=True)
            if options.correction_config is not None:
                adapter_log = (session / 'correction.log').open('w'); handles.append(adapter_log)
                adapter = subprocess.Popen(adapter_command(root, resolve(root, str(options.correction_config)),
                    folder, options.robot_id), stdout=adapter_log, stderr=subprocess.STDOUT,
                    start_new_session=True)
                print('TAG_ADAPTER_STARTED: 이동 신호 대기; 상태는 correction.log 확인', flush=True)
            while not stopped:
                for name, process in (('capture', camera), ('adapter', adapter)):
                    if process is not None and process.poll() is not None:
                        raise RuntimeError(f'{name} 종료 code={process.returncode}')
                time.sleep(.1)
    except Exception as error:
        receipt['error'] = str(error)
        print('TAG_SESSION_ERROR: ' + str(error) + '; 보정만 종료, 주행 취소 명령 없음', flush=True)
        result = 1
    finally:
        receipt['adapter_exit'] = stop_owned(adapter, 5.)
        # 기존 캡처 관리자가 카메라→검출→rectify 순서로 정리할 시간을 준다.
        receipt['capture_exit'] = stop_owned(camera, 45.)
        for handle in handles:
            handle.close()
        for sig, handler in previous.items():
            signal.signal(sig, handler)
        (session / 'session.json').write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + '\n')
    return result
