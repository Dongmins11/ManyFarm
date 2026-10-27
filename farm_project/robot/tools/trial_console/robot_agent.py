"""SSH 표준입력으로 실행하는 제한된 종료·저널 도구. 이동/기동 기능 없음."""
from pathlib import Path
import datetime
import hashlib
import json
import os
import shutil
import signal
import sys
import time


def processes() -> dict:
    """수확 전용 프로세스 루트와 그 자식을 PID 재사용 검사용 시각과 수집한다."""
    rows = {}
    for path in Path('/proc').iterdir():
        if not path.name.isdigit() or int(path.name) == os.getpid():
            continue
        try:
            args = (path/'cmdline').read_bytes().decode().strip('\0').split('\0')
            stat = (path/'stat').read_text().split(') ', 1)[1].split()
            if stat[0] != 'Z' and args[0]:
                rows[int(path.name)] = dict(args=args, ppid=int(stat[1]), ticks=stat[19])
        except (OSError, UnicodeError):
            pass
    selected = set()
    for pid, row in rows.items():
        args = row['args']; joined = ' '.join(args)
        names = {Path(a).name for a in args[:2]}
        owned = ('harvest.launch.py' in args
                 or ('harvest_node' in names and '/harvest_01' in joined)
                 or ('tag_capture_session' in names and 'harvest_01' in args)
                 or ('zenoh-bridge-ros2dds' in names and any(
                     a in args for a in ('/home/vic/Downloads/handoff_completion_fix/zenoh_harvest_handoff_v2.json5',
                                        '/home/vic/Downloads/pc_dummy_fsm_candidate_20261023/robot-bridge.json')))
                 or ('/harvest_01' in joined and bool(names & {
                     'controller_server', 'behavior_server', 'amcl', 'map_server',
                     'velocity_smoother', 'planner_server', 'bt_navigator', 'sllidar_node',
                     'bringup', 'scan_to_scan_filter_chain', 'robot_state_publisher',
                     'lifecycle_manager', 'route_preview'})))
        if owned:
            selected.add(pid)
    while True:
        new = {pid for pid, row in rows.items() if row['ppid'] in selected} - selected
        if not new:
            break
        selected |= new
    return {pid: rows[pid] for pid in sorted(selected)}


def reconcile(path: Path, snapshot: str, confirmed: bool, running: dict) -> dict:
    """전체 종료·사용자 재배치·미변경 저널을 확인한 뒤 미완료 건만 복구한다."""
    if running or not confirmed:
        raise ValueError('전체 종료와 스테이션 재배치 확인이 필요합니다.')
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != snapshot:
        raise ValueError('저널이 변경됐습니다. 상태를 새로 조회하세요.')
    data = json.loads(raw)
    if data.get('version') != 1 or data.get('robot_id') != 'harvest_01' or not isinstance(data.get('records'), dict):
        raise ValueError('지원하지 않는 저널 형식')
    keys = [key for key, row in data['records'].items() if row.get('active') or row.get('recovery_required')]
    if not keys:
        return dict(changed=[], note='복구할 미완료 기록 없음')
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    backup = path.parent / ('console-backup-' + str(time.time_ns()))
    backup.mkdir(mode=0o700)
    shutil.copy2(path, backup/'transfer.before.json')
    for key in keys:
        row = data['records'][key]; previous = dict(row)
        row.update(active=False, recovery_required=False)
        if 'result_code' not in row:
            row['result_code'] = 'FAILED'
        row['manual_recovery'] = dict(confirmed_at=now, previous_record=previous,
            basis='웹 사용자 스테이션 재배치 확인 및 수확 프로세스 종료 확인',
            note='실제 성공/취소 응답/종료 시각을 추정하지 않음. 재기동 후 새 도착 기준 필요.')
    tmp = path.with_name(path.name + '.console.tmp')
    shutil.copy2(path, tmp)
    with tmp.open('w') as stream:
        json.dump(data, stream, ensure_ascii=False, indent=2); stream.flush(); os.fsync(stream.fileno())
    os.replace(tmp, path)
    shutil.copy2(path, backup/'transfer.after.json')
    return dict(changed=keys, backup=str(backup))


def stop() -> dict:
    """검증한 PID에만 SIGINT. 강제 kill이나 서비스 재기동은 하지 않는다."""
    before = processes(); events = []
    roots = [pid for pid, row in before.items() if row['ppid'] not in before]
    def send(ids: list) -> None:
        current = processes()
        for pid in ids:
            if pid in current and current[pid]['ticks'] == before[pid]['ticks']:
                os.kill(pid, signal.SIGINT); events.append(pid)
    send(roots)
    end = time.monotonic() + 20
    while time.monotonic() < end and processes():
        time.sleep(.2)
    send([pid for pid in processes() if pid in before])
    end = time.monotonic() + 10
    while time.monotonic() < end and processes():
        time.sleep(.2)
    remaining = processes()
    return dict(ok=not remaining, signaled=events, remaining=remaining,
                note='남은 프로세스가 있으면 재배치하지 마세요. 강제 종료하지 않았습니다.')


def main() -> None:
    req = json.loads(sys.argv[1]); action = req['action']
    journal = Path(req['journal'])
    if action == 'status':
        raw = journal.read_bytes()
        result = dict(processes=processes(), journal_sha256=hashlib.sha256(raw).hexdigest(),
                      journal=json.loads(raw))
    elif action == 'stop':
        result = stop()
    elif action == 'reconcile':
        result = reconcile(journal, req['snapshot'], req.get('station_confirmed') is True, processes())
    else:
        raise ValueError('허용하지 않은 작업')
    print(json.dumps(result, ensure_ascii=False))

if __name__ == '__main__':
    main()
