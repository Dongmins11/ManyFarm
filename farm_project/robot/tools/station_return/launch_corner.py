"""사용자 직접 실행하는 실물 복귀 시험 런치. 기존 중복 검사·로그 구조를 재사용한다."""
from pathlib import Path
import argparse
import fcntl
import importlib.util
import os
import shlex
import time

ROOT = Path('/home/vic/vmany/main/farm_project')
BASE = Path('/home/vic/vmany-runtime-staging/jetson_reply_20261027_1741')


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('overlay', type=Path)
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--docking-config', type=Path,
                        help='명시할 때만 스테이션 라이다 도킹 설정을 선택한다')
    parser.add_argument('--without-camera', action='store_true',
                        help='이번 실행에서만 태그 촬영·보정 프로세스를 생성하지 않는다')
    args = parser.parse_args()
    overlay = args.overlay.resolve()
    if not (overlay/'install/harvest_robot/share/harvest_robot/launch/station_return.launch.py').is_file():
        raise SystemExit('검증한 복귀 overlay 설치본이 없습니다.')
    spec = importlib.util.spec_from_file_location('existing_terminal', BASE/'terminal.py')
    terminal = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(terminal)
    command = ['ros2', 'launch', 'harvest_robot', 'station_return.launch.py',
        f'project_root:={ROOT}', f'environment_config:={BASE}/config/harvest_station_return_jetson_real.yaml',
        'devices:=true', f'tag_correction:={str(not args.without_camera).lower()}',
        f'tag_camera:={str(not args.without_camera).lower()}', 'corner_radius_m:=0.20',
        f'handoff_config:={ROOT}/robot/config/robots/vicpinky/transfer/handoff_fsm.json']
    if args.docking_config is not None:
        command.append(f'docking_config:={args.docking_config.resolve()}')
    if args.check:
        print('CHECK_ONLY:', shlex.join(command))
        print('기존 실행 충돌 PID:', [pid for pid, _ in terminal.conflicts('launch', terminal.processes())])
        return
    lockdir = Path.home()/'.cache/manyfarm'
    lockdir.mkdir(parents=True, exist_ok=True)
    lock = open(lockdir/'terminal-launch.lock', 'a')
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        raise SystemExit('기존 런치가 실행 중입니다. 사용자가 기존 터미널에서 종료해야 합니다.')
    os.set_inheritable(lock.fileno(), True)
    clashes = terminal.conflicts('launch', terminal.processes())
    if clashes:
        raise SystemExit('중복 기동 차단: '+str([pid for pid, _ in clashes]))
    folder = Path.home()/'vmany-terminal-logs'/(time.strftime('%Y%m%d_%H%M%S')+'_launch_'+str(os.getpid()))
    folder.mkdir(parents=True)
    os.environ.update(HANDOFF_TF_EXECUTOR='dedicated', HANDOFF_TIMING='1', HANDOFF_INPUT_TRACE=str(folder/'trace'))
    print('복귀 overlay:', overlay, '\n로그:', folder/'console.log', flush=True)
    os.chdir(ROOT)
    os.execvp('bash', ['bash', '-c', 'set -o pipefail; '+shlex.join(command)+' 2>&1 | tee '+shlex.quote(str(folder/'console.log'))])


if __name__ == '__main__':
    main()
