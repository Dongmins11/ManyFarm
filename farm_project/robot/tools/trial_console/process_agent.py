"""명시한 시험 프로세스 그룹만 조회·SIGINT 종료한다. 임의 PID/셸 명령은 받지 않는다."""
from pathlib import Path
import hashlib
import json
import os
import signal
import sys
import time


def collect(rules: list) -> dict:
    rows = {}
    for path in Path('/proc').iterdir():
        if not path.name.isdigit() or int(path.name)==os.getpid():
            continue
        try:
            args = (path/'cmdline').read_bytes().decode().strip('\0').split('\0')
            stat = (path/'stat').read_text().split(') ',1)[1].split()
            if args[0] and stat[0] != 'Z':
                rows[int(path.name)] = dict(args=args, ppid=int(stat[1]), ticks=stat[19])
        except (OSError,UnicodeError,IndexError):
            continue
    selected = {pid for pid,row in rows.items() if any(
        any(Path(a).name in rule['executables'] for a in row['args'][:2])
        and rule['marker'] in row['args'] for rule in rules)}
    while True:
        children = {pid for pid,row in rows.items() if row['ppid'] in selected}-selected
        if not children:
            break
        selected |= children
    return {str(pid):rows[pid] for pid in sorted(selected)}


def fingerprint(rows: dict) -> str:
    return hashlib.sha256(json.dumps(rows,sort_keys=True).encode()).hexdigest()


def stop(rules: list, expected: str) -> dict:
    before = collect(rules)
    if fingerprint(before) != expected:
        raise ValueError('프로세스 목록이 변경됐습니다. 다시 조회하세요.')
    sent = []
    def signal_original(roots_only: bool) -> None:
        current = collect(rules)
        for pid,row in before.items():
            if roots_only and str(row['ppid']) in before:
                continue
            if pid in current and current[pid]['ticks']==row['ticks']:
                try:
                    os.kill(int(pid),signal.SIGINT)
                    sent.append(int(pid))
                except ProcessLookupError:
                    pass
    signal_original(True)
    deadline=time.monotonic()+20
    while time.monotonic()<deadline and collect(rules):time.sleep(.2)
    signal_original(False)
    deadline=time.monotonic()+10
    while time.monotonic()<deadline and collect(rules):time.sleep(.2)
    remaining=collect(rules)
    return {'ok':not remaining,'signaled':sent,'remaining':remaining,'note':'SIGINT만 사용. 강제 종료/재기동 없음'}


def main() -> None:
    req=json.loads(sys.argv[1])
    if req['action']=='list':
        rows=collect(req['rules']);result={'processes':rows,'snapshot':fingerprint(rows)}
    elif req['action']=='stop':
        result=stop(req['rules'],req['snapshot'])
    else:raise ValueError('허용하지 않은 프로세스 명령')
    print(json.dumps(result,ensure_ascii=False))


if __name__=='__main__':main()
