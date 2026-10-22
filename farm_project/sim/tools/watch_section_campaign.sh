#!/usr/bin/env bash
# 캠페인 ActionClient가 받은 feedback/result 원본을 읽어 터미널과 파일에 표시한다.
set -euo pipefail
project_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"
campaign_dir="${1:-$project_root/sim/runs/sec01_goal_time_fix_20261020_183345}"
exec python3 -u - "$campaign_dir" <<'PY'
import json
import sys
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

root = Path(sys.argv[1]).resolve()
if not root.is_dir():
    sys.exit(f"캠페인 폴더가 없습니다: {root}")
tz = ZoneInfo('Asia/Seoul')
log_path = root / 'terminal_feedback.log'


def read_state(path: Path) -> dict:
    try:
        return json.loads(path.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def emit(message: str, at: str = '') -> None:
    stamp = datetime.fromisoformat(at).astimezone(tz) if at else datetime.now(tz)
    line = f"[{stamp:%m-%d %H:%M:%S} KST] {message}"
    print(line, flush=True)
    with log_path.open('a') as log:
        log.write(line + '\n')


def show_event(attempt: str, event: dict) -> None:
    kind, data = event.get('kind'), event.get('data', {})
    if kind not in ('goal', 'feedback', 'result', 'diagnostic_error', 'ready'):
        return
    payload = data.get('result', data.get('harvest_task', data))
    # 예찰 결과의 전체 window 좌표는 events.jsonl 원본에 보존한다.
    fields = {key: value for key, value in payload.items() if key not in
              ('harvest_tasks', 'goal_pose', 'timestamp')}
    if kind == 'result':
        fields['ros_status'] = data.get('status')
    emit(f"{attempt} {kind.upper()} " + json.dumps(fields, ensure_ascii=False), event.get('at', ''))


emit(f"감시 시작: {root} | 기록: {log_path} | Ctrl+C는 감시만 종료")
emit('현재 시도의 기존 이벤트를 먼저 재생하고, 이후 새 이벤트를 표시합니다.')
directories = sorted(root.glob('SEC*_attempt_*'))
first = directories[-1].name if directories else ''
offsets = {}
last_status = None
next_heartbeat = 0.0
try:
    while True:
        directories = [d for d in sorted(root.glob('SEC*_attempt_*')) if d.name >= first]
        for directory in directories:
            path = directory / 'events.jsonl'
            if not path.exists():
                continue
            with path.open('rb') as stream:
                stream.seek(offsets.get(path, 0))
                while line := stream.readline():
                    if not line.endswith(b'\n'):
                        break  # 기록 중인 줄은 다음 순회에서 완성된 뒤 읽는다.
                    offsets[path] = stream.tell()
                    try:
                        show_event(directory.name, json.loads(line))
                    except json.JSONDecodeError:
                        emit(f'{directory.name} 읽을 수 없는 이벤트: {path}')
        if directories:
            directory = directories[-1]
            state = read_state(directory / 'result.json')
            status = (directory.name, state.get('status'), state.get('phase'),
                      state.get('window_index'), len(state.get('harvest_results', [])))
            now = time.monotonic()
            if status != last_status or now >= next_heartbeat:
                telemetry = directory / 'telemetry.jsonl'
                age = f'{max(0, time.time() - telemetry.stat().st_mtime):.0f}초 전' if telemetry.exists() else '아직 없음'
                emit(f"{directory.name} STATUS={state.get('status', '시작 준비')} "
                     f"단계={state.get('phase', '-')} window={state.get('window_index', '-')}/{state.get('window_count', '-')} "
                     f"완료결과={len(state.get('harvest_results', []))} "
                     f"예찰재사용={state.get('scout_reused', '-')} 마지막ROS기록={age} "
                     f"오류={state.get('error', '없음')}")
                last_status, next_heartbeat = status, now + 30
        time.sleep(0.5)
except KeyboardInterrupt:
    emit('감시 종료. 시험은 별도로 계속 실행됩니다.')
PY
