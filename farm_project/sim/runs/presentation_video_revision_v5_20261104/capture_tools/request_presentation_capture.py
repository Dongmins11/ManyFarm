"""실행 중인 독립 GUI 촬영 세션에 컷을 순서대로 요청하고 완료를 확인한다."""
import argparse
import json
import time
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--preview', action='store_true')
    parser.add_argument('settings', type=Path, nargs='+')
    args = parser.parse_args()
    if not (args.output / 'ready.json').exists():
        raise SystemExit('GUI 촬영 세션을 먼저 실행하세요.')
    for path in args.settings:
        request = json.loads(path.read_text())
        request['preview_only'] = args.preview
        name = request['name']
        suffix = '-preview' if args.preview else ''
        result = args.output / (name + suffix + '.json')
        error = args.output / (name + '-error.json')
        started = time.time_ns()
        temporary = args.output / 'request.tmp'
        temporary.write_text(json.dumps(request, indent=2) + '\n')
        temporary.replace(args.output / 'request.json')
        print('REQUESTED ' + name, flush=True)
        deadline = time.monotonic() + 1800
        while time.monotonic() < deadline:
            if error.exists() and error.stat().st_mtime_ns >= started:
                raise SystemExit(error.read_text())
            if result.exists() and result.stat().st_mtime_ns >= started:
                print('COMPLETED ' + name, flush=True)
                break
            time.sleep(1)
        else:
            raise SystemExit('촬영 완료 대기 시간 초과: ' + name)


if __name__ == '__main__':
    main()
