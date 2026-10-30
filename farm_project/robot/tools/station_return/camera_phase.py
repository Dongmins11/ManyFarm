"""14번 정지 후 사용자가 실행하는 카메라 OFF 비교 도구. 주행 명령은 보내지 않는다."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import signal
import time


def main() -> int:
    """기본은 조회, --stop은 기존 세션 관리자에 SIGINT를 보내고 자식 종료를 확인한다."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stop', action='store_true', help='14번 이동 성공·실제 정지 후에만 실행')
    args = parser.parse_args()
    source = Path(__file__).resolve().parents[1] / 'trial_console/process_agent.py'
    spec = importlib.util.spec_from_file_location('process_inventory', source)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    rules = [{'executables': ['tag_capture_session'], 'marker': 'harvest_01'}]
    before = module.collect(rules)
    roots = [pid for pid, row in before.items() if str(row['ppid']) not in before]
    print(json.dumps({'time_ns': time.time_ns(), 'processes': before}, ensure_ascii=False), flush=True)
    if not args.stop:
        print('CAMERA_ON' if len(roots) == 1 else 'CAMERA_NOT_READY')
        return 0 if len(roots) == 1 else 2
    if len(roots) != 1:
        print('카메라 세션 1개를 확인할 수 없습니다. 신호를 보내지 않았습니다.')
        return 2
    # 기존 관리자가 adapter부터 종료하고 camera/detector/rectify를 정리한다.
    current = module.collect(rules)
    pid = roots[0]
    if pid not in current or current[pid]['ticks'] != before[pid]['ticks']:
        print('조회 중 세션이 바뀌었습니다. 신호를 보내지 않았습니다.')
        return 2
    os.kill(int(pid), signal.SIGINT)
    print('CAMERA_STOP_REQUESTED time_ns=' + str(time.time_ns()), flush=True)
    deadline = time.monotonic() + 65.
    absent_since = None
    while time.monotonic() < deadline:
        remaining = module.collect(rules)
        # 부모 종료 후 재부모화된 자식도 기존 시작 시각으로 추적한다.
        for old_pid, row in before.items():
            try:
                stat = Path('/proc', old_pid, 'stat').read_text().split(') ', 1)[1].split()
                if stat[0] != 'Z' and stat[19] == row['ticks']:
                    remaining[old_pid] = row
            except (OSError, IndexError):
                pass
        if remaining:
            absent_since = None
        elif absent_since is None:
            absent_since = time.monotonic()
        elif time.monotonic() - absent_since >= 5.:
            print('CAMERA_OFF_CONFIRMED time_ns=' + str(time.time_ns()), flush=True)
            return 0
        time.sleep(.25)
    print('종료 확인 시간 초과. 강제 종료하지 않았습니다: ' + json.dumps(remaining))
    return 3


if __name__ == '__main__':
    raise SystemExit(main())
