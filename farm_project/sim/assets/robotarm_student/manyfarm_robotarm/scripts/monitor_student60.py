#!/usr/bin/env python3
"""Read-only terminal dashboard for collect_student60_set.py; stdlib only."""
import argparse
from collections import Counter
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import shutil
import statistics
import sys
import time
import unicodedata

ROOT = Path(__file__).resolve().parents[1]
KST = timezone(timedelta(hours=9))
ROLES = {'collect_student60_set.py': 'runner', 'collect_student60.py': 'capture',
         'compact_student60.py': 'audit', 'prepare_student60.py': 'prepare'}
PHASES = {'observation': '관측 준비', 'detector': '과실 탐지',
          'teacher_physics_step': 'Teacher 제어·물리 계산', 'control_record': '명령·표본 저장',
          'native_render_capture_write': '카메라 렌더링·원본 저장',
          'native_capture_finished': '카메라 촬영 완료'}
HARVEST = {'approach': '접근', 'bridge': '파지 안정화', 'pull': '당김·분리',
           'transport': '박스 운반', 'place': '열기·박스 안착'}
COLORS = {'Red': '빨강', 'Yellow': '노랑'}


class JsonReader:
    """Cache unchanged small metadata; tolerate a collector's in-place JSON write."""
    def __init__(self):
        self.cache = {}

    def read(self, path):
        path = Path(path)
        try:
            st = path.stat()
            signature = (st.st_mtime_ns, st.st_size, st.st_ino)
            old = self.cache.get(path)
            if old and old[0] == signature:
                return old[1]
            value = json.loads(path.read_text())
            if not isinstance(value, dict):
                return None
            self.cache[path] = (signature, value)
            return value
        except FileNotFoundError:
            self.cache.pop(path, None)
            return None
        except (OSError, ValueError):
            old = self.cache.get(path)
            return old[1] if old else None


def mtime(path):
    try:
        return Path(path).stat().st_mtime
    except OSError:
        return None


def option(command, name, default=None):
    try:
        return command[command.index(name) + 1]
    except (ValueError, IndexError):
        return default


def planned_colors(command):
    if '--colors' not in command:
        return ['Red', 'Yellow']
    result = []
    for token in command[command.index('--colors') + 1:]:
        if token.startswith('--'):
            break
        result.append(token)
    return result or ['Red', 'Yellow']


class ProcessProbe:
    """Inspect only our four scripts and this run's paths; never send a signal."""
    def __init__(self):
        self.previous = {}

    def scan(self, root, now):
        found = []
        try:
            entries = list(Path('/proc').iterdir())
            full_visibility = Path('/proc/1/comm').read_text().strip() in ('systemd', 'init')
        except OSError:
            return [], False
        ticks_per_second = os.sysconf('SC_CLK_TCK')
        for entry in entries:
            if not entry.name.isdigit():
                continue
            try:
                argv = [x.decode(errors='replace') for x in (entry/'cmdline').read_bytes().split(b'\0') if x]
                role = next((ROLES[Path(x).name] for x in argv if Path(x).name in ROLES), None)
                if role is None:
                    continue
                matches = False
                for flag in ('--output', '--source'):
                    value = option(argv, flag)
                    if value is None:
                        continue
                    path = Path(value)
                    if not path.is_absolute():
                        path = Path(os.readlink(entry/'cwd'))/path
                    path = path.resolve()
                    if path == root or path.is_relative_to(root):
                        matches = True
                if not matches:
                    continue
                fields = (entry/'stat').read_text().rsplit(')', 1)[1].split()
                if fields[0] == 'Z':
                    continue
                pid = int(entry.name)
                cpu_time = (int(fields[11]) + int(fields[12]))/ticks_per_second
                identity = (pid, fields[19])
                old = self.previous.get(identity)
                cpu = max(0., (cpu_time-old[1])*100/(now-old[0])) if old and now > old[0] else None
                self.previous[identity] = (now, cpu_time)
                found.append(dict(pid=pid, role=role, state=fields[0], cpu_percent=cpu))
            except (OSError, ValueError, IndexError):
                continue
        live = {p['pid'] for p in found}
        self.previous = {k: v for k, v in self.previous.items() if k[0] in live}
        return sorted(found, key=lambda p: p['pid']), full_visibility


class Monitor:
    def __init__(self, root, recent=6, reserve_seconds=300, stale_seconds=90, probe=None):
        self.root = Path(root).resolve()
        self.reader = JsonReader()
        self.probe = probe or ProcessProbe()
        self.recent = recent
        self.reserve = reserve_seconds
        self.stale = stale_seconds
        plan = self.reader.read(self.root/'plan.json')
        if not plan or not isinstance(plan.get('batches'), list) or not plan['batches']:
            raise ValueError('Student60 묶음 수집의 plan.json이 필요합니다.')
        self.compact = bool(plan.get('compact_native'))
        self.batches = []
        for entry in plan['batches']:
            destination = Path(entry['destination']).resolve()
            scratch = Path(entry['scratch']).resolve()
            if destination.parent != self.root or scratch.parent != self.root:
                raise ValueError('plan.json의 묶음 경로가 작업 폴더 밖에 있습니다.')
            command = entry['command']
            per_color = int(option(command, '--per-color', '2'))
            colors = planned_colors(command)*per_color
            self.batches.append(dict(name=destination.name, destination=destination,
                scratch=scratch, colors=colors, per_color=per_color, split=option(command, '--split', 'train')))
        self.started = mtime(self.root/'plan.json')

    def snapshot(self, now=None):
        now = time.time() if now is None else now
        processes, full_visibility = self.probe.scan(self.root, now)
        totals, by_color = Counter(), Counter()
        samples = 0
        completed = []
        split_totals, split_done = Counter(), Counter()
        durations = []
        previous_end = self.started
        active = None
        for index, batch in enumerate(self.batches):
            split_totals[batch['split']] += 1
            destination, scratch = batch['destination'], batch['scratch']
            # During export the same episode exists twice. Always count one source.
            folder = scratch if scratch.exists() else destination
            run = self.reader.read(folder/'run.json') or {}
            audit = self.reader.read(destination/'verification.json') or {}
            cert_time = mtime(destination/'compact_certificate.json')
            if self.compact:
                done = bool(cert_time and run.get('completed') and audit.get('audit_passed')
                            and audit.get('final_runtime_audit_complete') and not scratch.exists())
                end = cert_time
            else:
                done = bool(run.get('completed') and not (folder/'COLLECTION_IN_PROGRESS.json').exists())
                end = mtime(folder/'run.json')
            outcomes = Counter()
            try:
                episodes = sorted(folder.glob('episode_*'))
            except OSError:
                episodes = []
            for episode in episodes:
                result = self.reader.read(episode/'result.json')
                if not result or not result.get('status'):
                    continue
                status = result['status']
                outcomes[status] += 1
                totals[status] += 1
                if status == 'SUCCEEDED':
                    samples += int(result.get('samples', 0))
                    diagnostic = result.get('diagnostics', {})
                    color = diagnostic.get('color')
                    if not color:
                        meta = self.reader.read(episode/'metadata.json') or {}
                        color = meta.get('layout', {}).get('target_color')
                    by_color[color or '?'] += 1
            if done:
                split_done[batch['split']] += 1
                duration = end-previous_end if previous_end and end and end > previous_end else None
                if duration is not None:
                    durations.append(duration)
                completed.append(dict(index=index+1, name=batch['name'], end=end,
                                      duration_seconds=duration, outcomes=dict(outcomes)))
                previous_end = end
            elif active is None:
                active = dict(index=index+1, name=batch['name'], folder=str(folder),
                    started=previous_end, elapsed_seconds=max(0., now-previous_end),
                    outcomes=dict(outcomes), expected=len(batch['colors']), colors=batch['colors'])
                phase = self.reader.read(folder/'phase.json') or {}
                active['phase'] = phase
                phase_time = phase.get('wall_time')
                active['heartbeat_age_seconds'] = max(0., now-phase_time) if isinstance(phase_time, (int, float)) else None
                if run.get('completed'):
                    if any(p['role'] == 'capture' for p in processes):
                        active['stage'] = 'closing'
                    elif cert_time:
                        active['stage'] = 'cleanup'
                    elif destination.exists() and self.compact:
                        active['stage'] = 'export'
                    else:
                        active['stage'] = 'audit'
                else:
                    active['stage'] = 'capture' if phase else 'startup'
                ep = phase.get('episode', -1)
                step = phase.get('step', -1)
                active['color'] = batch['colors'][ep] if isinstance(ep, int) and 0 <= ep < len(batch['colors']) else None
                if isinstance(ep, int) and ep >= 0 and isinstance(step, int) and step >= 0:
                    for candidate in (step, step-1):
                        note = self.reader.read(folder/f'episode_{ep:04d}'/f'{candidate:06d}.json') or {}
                        if note:
                            active['harvest_phase'] = note.get('phase')
                            break
                active['error'] = self.reader.read(folder/'error.json')
        data = self.reader.read(self.root/'data.json') or {}
        stopped = self.reader.read(self.root/'stopped.json')
        error = (stopped or {}).get('error')
        if not error and active and active.get('error'):
            error = active['error'].get('traceback', '수집 오류')
        ready = bool(data.get('ready_for_initial_bc'))
        age = active.get('heartbeat_age_seconds') if active else None
        fresh = bool(active and active['stage'] == 'capture' and age is not None and age < 10)
        cpu_active = any((p['cpu_percent'] or 0) > .5 or (p['cpu_percent'] is None and p['state'] == 'R') for p in processes)
        activity = bool((fresh or cpu_active) and not error and not ready)
        delayed = bool(active and active['stage'] == 'capture' and age is not None and age >= self.stale)
        if error:
            status = 'stopped'
        elif ready:
            status = 'complete'
        elif not processes and full_visibility:
            status = 'not_running'
        elif delayed:
            status = 'delayed'
        elif processes or fresh:
            status = 'running'
        else:
            status = 'unconfirmed'
        if status in ('stopped', 'not_running', 'complete'):
            activity = False
        count = len(completed)
        total = len(self.batches)
        history = durations[-self.recent:]
        average = statistics.mean(history) if history else None
        eta = None
        if ready:
            eta = dict(seconds=0, finish_unix=now, range_seconds=[0, 0])
        elif average and count < total and status not in ('stopped', 'not_running', 'delayed', 'unconfirmed'):
            elapsed = active['elapsed_seconds'] if active else 0
            pending = total-count
            def remaining(speed):
                return (pending-1)*speed + max(30., speed-elapsed) + self.reserve
            eta = dict(seconds=remaining(average), finish_unix=now+remaining(average),
                       range_seconds=[remaining(min(history)), remaining(max(history))])
        disk = shutil.disk_usage(self.root)
        per_color = max(b['per_color'] for b in self.batches)
        reserve_bytes = (8*per_color+5)*1024**3
        return dict(root=str(self.root), checked_unix=now, started_unix=self.started,
            elapsed_seconds=max(0., now-self.started), status=status, activity=activity,
            error=error, data_ready=ready, batches_done=count, batches_total=total,
            split_totals=dict(split_totals), split_done=dict(split_done),
            episodes_done=sum(totals.values()), episodes_total=sum(len(b['colors']) for b in self.batches),
            outcomes=dict(totals), success_rate=totals['SUCCEEDED']/sum(totals.values()) if totals else None,
            successful_samples=samples, successful_colors=dict(by_color), active=active,
            average_batch_seconds=average, duration_samples=len(history), eta=eta,
            preparation_reserve_seconds=self.reserve, recent_batches=completed[-3:],
            disk_free_bytes=disk.free, disk_total_bytes=disk.total, disk_required_bytes=reserve_bytes,
            processes=processes, process_visibility='full' if full_visibility else 'limited')


def clean(text):
    return ''.join(c if c.isprintable() else ' ' for c in str(text))


def cell_width(text):
    return sum(0 if unicodedata.combining(c) else 2 if unicodedata.east_asian_width(c) in ('W', 'F') else 1 for c in text)


def fit(text, width):
    text = clean(text)
    if cell_width(text) <= width:
        return text
    result = ''
    for c in text:
        if cell_width(result+c) > width-1:
            break
        result += c
    return result+'…'


def duration(seconds):
    if seconds is None:
        return '계산 중'
    seconds = max(0, int(seconds))
    hours, rem = divmod(seconds, 3600)
    minutes, sec = divmod(rem, 60)
    return f'{hours}시간 {minutes:02d}분' if hours else f'{minutes}분 {sec:02d}초'


def clock(stamp):
    return datetime.fromtimestamp(stamp, KST).strftime('%m/%d %H:%M') if stamp else '-'


def render(s, frame=0, width=95, height=30, color=False, interval=2):
    width = max(35, width)
    status_names = {'running': '실행 중', 'complete': '수집·데이터 준비 완료',
        'stopped': '오류로 중단', 'not_running': '수집 프로세스 없음',
        'delayed': '상태 기록 갱신 지연', 'unconfirmed': '진행 여부 확인 제한'}
    active = s['active'] or {}
    stage_names = {'capture': '영상·시연 수집', 'startup': '다음 묶음·시뮬레이터 준비',
        'closing': '수집 완료·시뮬레이터 종료', 'audit': '원본 영상·명령 전수 검사',
        'export': '압축 자료 복사', 'cleanup': '압축 검증·임시 자료 정리'}
    phase = active.get('phase', {})
    count, total = s['batches_done'], s['batches_total']
    bar_width = max(10, min(34, width-38))
    filled = int(bar_width*count/total)
    bar = '#'*filled+'-'*(bar_width-filled)
    spinner = '|/-\\'[frame % 4] if s['activity'] else '=' if s['data_ready'] else '.'
    cells = ['·']*12
    if s['activity']:
        pos = frame % 22
        cells[pos if pos < 12 else 22-pos] = '■'
    pulse = ''.join(cells)
    outcomes = s['outcomes']
    rate = f"{s['success_rate']*100:.1f}%" if s['success_rate'] is not None else '-'
    eta = s['eta']
    if eta and not s['data_ready']:
        eta_line = f"남은 약 {duration(eta['seconds'])}  |  예상 완료 {clock(eta['finish_unix'])} KST"
        range_line = '최근 속도 범위 '+ ' ~ '.join(duration(x) for x in eta['range_seconds'])
    elif s['data_ready']:
        eta_line, range_line = '남은 시간 0초  |  데이터 준비 완료', '다음 단계: 별도로 Student 학습 실행'
    elif count == total:
        eta_line, range_line = '전체 묶음 완료  |  마지막 데이터 준비·검사 단계', '준비 단계의 남은 시간은 아직 측정되지 않았습니다.'
    elif s['status'] in ('stopped', 'not_running', 'delayed'):
        eta_line, range_line = '남은 시간 추정 보류  |  중단·갱신 지연 확인 필요', '현재 상태에서 예상 완료 시각을 계속 미루지 않습니다.'
    elif s['status'] == 'unconfirmed':
        eta_line, range_line = '남은 시간 추정 보류  |  실행 신호 확인 필요', '호스트 터미널에서 실행하면 프로세스를 함께 확인합니다.'
    else:
        eta_line, range_line = '남은 시간 계산 중  |  첫 묶음 완료 후 추정', '완료된 묶음의 수집·검사·압축 시간을 사용합니다.'
    info = f"최종 준비 여유 {duration(s['preparation_reserve_seconds'])} 포함(가정) · Student 학습 별도"
    if s['error']:
        info = '오류: '+str(s['error']).strip().splitlines()[-1]
    elif s['disk_free_bytes'] < s['disk_required_bytes'] and not s['data_ready']:
        info = '주의: 다음 묶음 시작에 필요한 디스크 여유보다 적습니다.'
    elif s['status'] == 'unconfirmed':
        info = '프로세스 열람 제한 · 오래된 수집 기록만으로 실행 중이라고 표시하지 않습니다.'
    pnames = {'runner': '묶음', 'capture': '촬영', 'audit': '검사/압축', 'prepare': '자료준비'}
    proc = ' / '.join(f"{pnames[p['role']]} PID{p['pid']} "+
        (f"CPU {p['cpu_percent']:.0f}%" if p['cpu_percent'] is not None else 'CPU 측정 중') for p in s['processes'])
    if not proc:
        proc = '없음' if s['process_visibility'] == 'full' else '현재 실행 환경에서 열람 제한'
    age = active.get('heartbeat_age_seconds')
    evidence = f'기록 갱신 {age:.1f}초 전' if age is not None else '촬영 기록 대기'
    if active.get('stage') in ('audit', 'export', 'cleanup', 'closing'):
        evidence = '검사·저장 단계: 아래 프로세스 CPU 활동 확인'
    activity_line = f"활동 {spinner} [{pulse}] "+('실행 신호 확인' if s['activity'] else '완료' if s['data_ready'] else '최근 실행 신호 대기')
    task = stage_names.get(active.get('stage'), '최종 데이터 준비' if not s['data_ready'] else '완료')
    detail = PHASES.get(phase.get('phase'), phase.get('phase', '-'))
    harvest = HARVEST.get(active.get('harvest_phase'), '-')
    current = (f"현재 {active.get('index')}/{total} {active.get('name')} · {COLORS.get(active.get('color'), '-')} · "+
        f"묶음 경과 {duration(active.get('elapsed_seconds'))}") if active else '현재 전체 묶음 수집·압축 완료'
    splits = ' / '.join(f"{'학습용' if k == 'train' else '검증용'} {s['split_done'].get(k, 0)}/{v}" for k, v in s['split_totals'].items())
    lines = [f"STUDENT60 수집 모니터  {datetime.fromtimestamp(s['checked_unix'], KST).strftime('%H:%M:%S')} KST",
        '작업 '+Path(s['root']).name, '상태 '+status_names[s['status']]+'  |  '+evidence,
        '─'*width, f"전체 [{bar}] {count/total*100:5.1f}%  {count}/{total} 묶음", splits,
        f"회차 {s['episodes_done']}/{s['episodes_total']} 완료  |  성공률 {rate} (Teacher 시연)",
        f"성공 {outcomes.get('SUCCEEDED', 0)}  실패 {outcomes.get('FAILED', 0)}  시간초과 {outcomes.get('TIMED_OUT', 0)}  기타 {sum(v for k,v in outcomes.items() if k not in ('SUCCEEDED','FAILED','TIMED_OUT'))}",
        f"성공 시연 표본 {s['successful_samples']:,}개  |  빨강 {s['successful_colors'].get('Red', 0)} / 노랑 {s['successful_colors'].get('Yellow', 0)}회",
        '─'*width, current, f"단계 {task} · {harvest} · step {phase.get('step', '-')} · {detail}",
        activity_line, f"시작 {clock(s['started_unix'])}  |  총 경과 {duration(s['elapsed_seconds'])}",
        eta_line, range_line,
        f"속도 최근 {s['duration_samples']}묶음 평균 {duration(s['average_batch_seconds'])} / 묶음",
        f"디스크 여유 {s['disk_free_bytes']/1024**3:.1f} GiB  |  다음 묶음 필요 {s['disk_required_bytes']/1024**3:.0f} GiB",
        '프로세스 '+proc]
    recent_count = max(0, min(3, height-len(lines)-3))
    for batch in s['recent_batches'][-recent_count:] if recent_count else []:
        c = batch['outcomes']
        lines.append(f"최근 {batch['name']}  {duration(batch['duration_seconds'])}  성공 {c.get('SUCCEEDED',0)}/{sum(c.values())}")
    lines += [info, '─'*width, f'{interval:g}초마다 기록 갱신 · Ctrl+C는 모니터만 종료 · 수집 계속 실행']
    if height < 22:
        # Keep progress, live activity, ETA and warnings visible on small terminals.
        indices = [0, 2, 4, 6, 7, 10, 11, 12, 14, 17, 18]
        lines = [lines[i] for i in indices]+[info, lines[-1]]
        if height < len(lines):
            lines = lines[:max(1, height-1)]+[lines[-1]]
    result = []
    for index, line in enumerate(lines):
        line = fit(line, width)
        if color and index in (2, 12, 14):
            code = 31 if s['status'] in ('stopped','not_running') else 33 if s['status'] in ('delayed','unconfirmed') else 32
            line = f'\x1b[1;{code}m{line}\x1b[0m'
        result.append(line)
    return '\n'.join(result)


def discover():
    candidates = list((ROOT/'outputs/harvest_rl').glob('student60_set_*/plan.json'))
    if not candidates:
        raise ValueError('Student60 수집 작업이 없습니다. --data로 작업 폴더를 지정하세요.')
    return max(candidates, key=lambda p: p.stat().st_mtime).parent


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data', type=Path, help='수집 작업 폴더. 생략하면 최신 Student60 set 자동 선택')
    parser.add_argument('--interval', type=float, default=2, help='기록 갱신 간격(초), 기본 2')
    parser.add_argument('--recent', type=int, default=6, help='ETA 계산에 사용할 최근 완료 묶음 수')
    parser.add_argument('--prepare-minutes', type=float, default=5, help='최종 데이터 준비 예상 여유(분), 기본 5')
    parser.add_argument('--stale-seconds', type=float, default=90, help='촬영 상태 기록 갱신 지연 표시 기준')
    parser.add_argument('--once', action='store_true', help='한 번만 출력')
    parser.add_argument('--json', action='store_true', help='한 번만 JSON 출력')
    parser.add_argument('--no-color', action='store_true')
    args = parser.parse_args()
    if not .5 <= args.interval <= 60 or args.recent < 1 or args.prepare_minutes < 0 or args.stale_seconds <= 0:
        parser.error('interval=.5..60, recent>=1, prepare-minutes>=0, stale-seconds>0 필요')
    try:
        monitor = Monitor(args.data or discover(), args.recent, args.prepare_minutes*60, args.stale_seconds)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        parser.error(str(exc))
    if args.json:
        print(json.dumps(monitor.snapshot(), ensure_ascii=False, indent=2))
        return
    tty = sys.stdout.isatty() and os.environ.get('TERM') != 'dumb'
    if args.once or not tty:
        print(render(monitor.snapshot(), interval=args.interval))
        return
    # The collector is an unrelated process. No process control or IPC is used.
    print('\x1b[?1049h\x1b[?25l', end='', flush=True)
    try:
        refresh = 0.
        frame = 0
        while True:
            now = time.monotonic()
            if now >= refresh:
                snapshot = monitor.snapshot()
                refresh = now+args.interval
            size = shutil.get_terminal_size((96, 30))
            view = render(snapshot, frame, size.columns-1, size.lines, not args.no_color, args.interval)
            print('\x1b[H'+view+'\x1b[J', end='', flush=True)
            frame += 1
            time.sleep(.2)
    except KeyboardInterrupt:
        pass
    finally:
        print('\x1b[?25h\x1b[?1049l', end='', flush=True)
    print('모니터 종료. 수집 작업은 계속 실행됩니다.')


if __name__ == '__main__':
    main()
