#!/usr/bin/env python3
"""ROS 검색 없이 실제 프로세스를 확인한다. 기존 프로세스는 종료하지 않는다."""
import os
from pathlib import Path
import sys


def conflicts(root: Path, proc_root: Path = Path('/proc')) -> list[dict]:
    """같은 수확 namespace 또는 장치를 사용하는 프로세스를 반환한다."""
    found = []
    for path in proc_root.glob('[0-9]*'):
        if int(path.name) == os.getpid():
            continue
        try:
            args = [x.decode(errors='replace') for x in (path/'cmdline').read_bytes().split(b'\0') if x]
        except (OSError, ValueError):
            continue
        if not args:
            continue
        # 실행 파일과 Python 진입점만 검사해 grep/조회 명령을 오인하지 않는다.
        names = {Path(x).name for x in args[:2]}
        launch = ('ros2' in names and 'launch' in args and 'farm_bringup' in args
                  and 'harvest.launch.py' in args)
        ros_node = '--ros-args' in args and '__ns:=/harvest_01' in args
        device = bool(names & {'sllidar_node', 'bringup', 'scan_to_scan_filter_chain'})
        capture = bool(names & {'tag_capture_session', 'tag_amcl_adapter'}) and str(root) in args
        if launch or ros_node or device or capture:
            found.append({'pid': int(path.name), 'command': ' '.join(args)})
    return found


def main() -> None:
    found = conflicts(Path(sys.argv[1]).resolve())
    if found:
        print('실행 중단: 기존 수확/장치 프로세스가 남아 있습니다. 새 launch는 시작하지 않았습니다.', file=sys.stderr)
        for item in found:
            print(f"PID {item['pid']}: {item['command']}", file=sys.stderr)
        raise SystemExit(3)


if __name__ == '__main__':
    main()
