#!/usr/bin/env python3
"""시험 로그를 읽기만 하는 한 화면 모니터. Ctrl+C는 모니터만 종료한다."""
import argparse
from datetime import datetime
import json
from pathlib import Path
import re
import shutil
import sys
import time
import unicodedata

ROOT = Path(__file__).resolve().parents[2]
KINDS = re.compile(r'"kind"\s*:\s*"([^"]+)"')
IGNORE = {'harvest_odom', 'harvest_scan', 'harvest_amcl', 'harvest_map_odom',
          'harvest_tf_static', 'basket_alignment', 'wall_observation',
          'harvest_task_diagnostic', 'odom', 'robot_status'}
PHASES = {'NAVIGATION_MOVE': '윈도우로 이동', 'HARVESTING': '팔 수확 중',
          'ARM_STOWING': '팔 복귀 중', 'IDLE': '다음 작업 대기',
          'WAITING_FOR_UNLOAD': '선별장 도킹 완료', 'UNLOADING_STARTED': '과실 투입 중',
          'APPROACHING': '접근 중', 'DOCKING': '도킹 중',
          'MOVING_STARTED': '수확로봇으로 주행 중',
          'WAITING_FOR_TRANSFER': '수령 접근 완료 · 수확로봇 인계 준비 대기',
          'DOCK_READY': '수확로봇 인계 자세 준비 완료',
          'DOCK_STABLE': '도킹 정렬 완료 · 인계 대기',
          'TRANSFER_COMPLETE': '수확물 인계 완료 · 이격 대기',
          'TRANSPORT_CLEAR': '운송 이격 완료 · 수확로봇 자세 복원 대기',
          'WAIT_INITIAL_MARKER': '정차 후 마커 재확인 중',
          'VERIFY_MARKER_TARGET': '마커 목표 좌표 검증 중',
          'BACKOUT_FOR_MARKER': '마커 재확인을 위해 후진 중'}
PHASES.update(DOCKING_STARTED='정밀 도킹 중', CLEARING_STARTED='하역/인계 후 이격 중',
              RETURNING='스테이션으로 주행 중', ARRIVED='목표 위치 도착')
FAILED = {'FAILED', 'REJECTED', 'CANCELED', 'UNKNOWN'}


def read_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):  # 기록 파일을 쓰는 도중이면 다음 화면에서 다시 읽는다.
        return {}


def success(event: dict) -> bool:
    return event.get('status') == 4 and event.get('result', {}).get('result_code') == 'SUCCESS'


def bar(done: int, total: int, unit: str) -> str:
    if not total:
        return '[····················]  집계 대기'
    fill = max(0, min(20, int(20 * done / total)))
    return '[' + '━' * fill + '·' * (20-fill) + f']  {done}/{total} {unit} ({done/total:.0%})'


def select_run(run: Path | None, previous: Path | None = None,
               runs_root: Path = ROOT/'sim/runs') -> Path | None:
    """반복 시험의 current를 매번 읽는다. 종료 뒤에는 마지막 결과를 유지한다."""
    def current(parent: Path) -> Path | None:
        state = read_json(parent/'continuation_status.json') if (parent/'continuation_status.json').exists() else read_json(parent/'status.json')
        value = state.get('current') or state.get('successful_attempt') or state.get('trial') or state.get('source')
        if not isinstance(value, str) or not value:
            return None
        path = Path(value)
        return (path if path.is_absolute() else parent/path).resolve()

    if run is not None:
        if (run/'status.json').exists() or (run/'continuation_status.json').exists():
            return current(run) or previous
        return run.resolve()
    candidates = {}
    for status in (*runs_root.glob('*/status.json'), *runs_root.glob('*/*/status.json'),
                   *runs_root.glob('*/continuation_status.json')):
        path = current(status.parent)
        if path is not None:
            candidates[path] = status.stat().st_mtime
        elif previous is not None and previous.parent == status.parent.resolve():
            # status.json이 작성 중이어도 이전 attempt 화면을 잠깐 다른 시험으로 바꾸지 않는다.
            candidates[previous] = status.stat().st_mtime
    for pattern in ('*/single_cycle.json', '*/attempt_*/single_cycle.json'):
        for config in runs_root.glob(pattern):
            path = config.parent.resolve()
            # 반복 시험에서는 옛 attempt의 로그 대신 supervisor가 지정한 current만 선택한다.
            if (path.parent/'status.json').exists():
                continue
            candidates.setdefault(path, config.stat().st_mtime)
    for path in candidates:
        for name in ('events.jsonl', 'post_sorter/events.jsonl', 'result.json', 'process_exit.json'):
            try:
                candidates[path] = max(candidates[path], (path/name).stat().st_mtime)
            except FileNotFoundError:
                pass
    # 최신 시험이 끝나도 오래된 미완료 기록으로 돌아가지 않는다.
    return max(candidates, key=candidates.get) if candidates else previous


class Monitor:
    def __init__(self, base: Path) -> None:
        self.base = base
        self.offsets = {}
        self.events = {}
        self.harvested = {}
        self.started = None
        self.handoff = {}
        self.transport_detail = None
        self.patrol = read_json(ROOT/'sim/ros_ws/src/farm_sim_config/config/scout_patrol.json')

    def new_lines(self, path: Path):
        """완성된 줄만 증분 소비한다. 작성 중인 마지막 줄은 다음 갱신에서 읽는다."""
        if not path.exists():
            return
        offset = self.offsets.get(path, 0)
        if path.stat().st_size < offset:
            raise RuntimeError('선택한 시험 로그가 교체됐습니다. 모니터를 다시 실행하세요.')
        with path.open('rb') as stream:
            stream.seek(offset)
            while line := stream.readline():
                if not line.endswith(b'\n'):
                    break
                self.offsets[path] = stream.tell()
                yield line.decode('utf-8', errors='replace')

    def poll(self) -> None:
        self.handoff = read_json(self.base/'control/simul-handoff.json') or self.handoff
        # 큰 센서 로그도 처음 한 번만 훑고 이후 추가된 줄만 읽는다.
        for path in (self.base/'events.jsonl', self.base/'post_sorter/events.jsonl'):
            for text in self.new_lines(path):
                match = KINDS.search(text[:350])
                if not match or match[1] in IGNORE:
                    continue
                try:
                    event = json.loads(text)
                except ValueError:
                    continue
                kind = event['kind']
                self.events[kind] = event
                if kind in ('scout_goal','scout_reused') and self.started is None:
                    self.started = event.get('at')
                if kind == 'harvest_result':
                    self.harvested[event['result']['task_id']] = event
                if kind == 'harvest_reused':
                    self.harvested.update({v['result']['task_id']:v for v in event['results']})
        # Action feedback이 MOVING_STARTED에 머무는 내부 정밀 접근은 기존 진단 로그로 보완한다.
        for text in self.new_lines(self.base/'precision.log'):
            match = re.search(r'\[(\d+\.\d+)\].*?(?:Station docking phase: (\w+)|(Harvest route marker recognized:))', text)
            if match:
                self.transport_detail = (float(match[1]),
                    PHASES.get(match[2], '정밀 도킹 · '+str(match[2])) if match[2]
                    else '마커 인식 · 주행 정지 후 정밀 접근 전환')

    def screen(self) -> str:
        e = self.events
        final = read_json(self.base/'result.json')
        exits = read_json(self.base/'process_exit.json')
        jobs = {j['role']: j for j in self.handoff.get('jobs', [])}
        failed_job = next((j for j in jobs.values() if j.get('state') in FAILED), None)
        action_failure = any(v.get('status') not in (None,4) for k,v in e.items()
                             if k.endswith('_result') and 'status' in v)
        stopped = bool(final and not final.get('passed') or exits and not final.get('passed')
                       or failed_job or action_failure or 'error' in e)
        state = '완료' if final.get('passed') else '중단' if stopped else '진행 중'
        elapsed = '--:--'
        if self.started:
            end = datetime.now().astimezone()
            if final or exits:
                end = datetime.fromtimestamp((self.base/('result.json' if final else 'process_exit.json')).stat().st_mtime).astimezone()
            elif failed_job and failed_job.get('finished_at'):
                end = datetime.fromisoformat(failed_job['finished_at'])
            seconds = max(0, int((end-datetime.fromisoformat(self.started)).total_seconds()))
            elapsed = f'{seconds//3600:02}:{seconds//60%60:02}:{seconds%60:02}'
        log = self.base/'events.jsonl'
        age = f'{max(0, int(time.time()-log.stat().st_mtime))}초 전' if log.exists() else '대기'
        lines = ['농장 시험 모니터  |  ' + state + '  |  경과 ' + elapsed,
                 f'{self.base.name}', f'로그 갱신 {age} · 진행률은 완료 작업 수 기준', '']
        campaign=read_json(self.base.parent/'status.json')
        if len(campaign.get('sections',[]))>1:
            lines.insert(1,'전체 섹션 '+bar(len(campaign.get('completed_sections',[])),len(campaign['sections']),'SEC'))

        next_scout = 'scout_sec02_goal' in e
        prefix = 'scout_sec02' if next_scout else 'scout'
        section = e.get(prefix+'_goal', {}).get('goal', {}).get('section_id',
            read_json(self.base/'single_cycle.json').get('section','SEC01'))
        sr = e.get('scout_reused',e.get(prefix+'_completed', e.get(prefix+'_result', {})))
        feedback = e.get(prefix+'_feedback', {}).get('data', {})
        done = sr.get('result', {}).get('completed_segment_count', feedback.get('completed_segment_count', 0))
        total = len(self.patrol.get('sections', {}).get(section, {}).get('segments', []))
        current = '예찰 완료 · 현위치 대기' if success(sr) else '예찰 실패' if sr else '예찰/이동 중' if prefix+'_goal' in e else '시작 준비 중'
        remain = '없음 (추가 예찰·복귀 명령 없음)' if success(sr) and next_scout else f'관측 {max(0,total-done)}구간'
        single=read_json(self.base/'single_cycle.json').get('single_section')
        if not next_scout and not single:
            remain += ' → SEC02 예찰'
        if 'scout_reused' in e:current,remain='예찰 생략 · 저장 결과 사용','없음'
        elif (self.base/'reused_scout_result.json').exists():current,remain='예찰 생략 · 재사용 준비 중','없음'
        if stopped and not sr:current='미실행 / 중단'
        if read_json(self.base/'single_cycle.json').get('overlap_cycle'):
            if success(sr):remain='수확 출발 전 스테이션 복귀' if single else '다른 로봇 복귀 후 스테이션 복귀'
            if 'scout_return_goal' in e:current,remain='스테이션 복귀 중','스테이션 복귀'
            if 'scout_return_result' in e:
                current,remain=('스테이션 복귀 완료','없음') if success(e['scout_return_result']) else ('스테이션 복귀 실패','오류 확인')
        lines += [f'예찰  {section} | {current}', '  '+bar(done,total,'관측'), '  남은 일: '+remain, '']

        scout = e.get('scout_reused',e.get('scout_result', {})).get('result', {})
        total = scout.get('harvest_task_count', 0)
        done = sum(success(v) for v in self.harvested.values())
        count = sum(v['result'].get('harvested_count', 0) for v in self.harvested.values())
        task = e.get('harvest_goal', {}).get('goal', {}).get('harvest_task', {})
        active_id = task.get('task_id')
        feedback = e.get('harvest_feedback', {}).get('data', {})
        # 진행 중 feedback은 완료 result와 중복 합산하지 않는다.
        if active_id and active_id not in self.harvested and feedback.get('task_id') == active_id:
            count += feedback.get('success_count', 0)
        current = PHASES.get(e.get('harvest_status', {}).get('data', {}).get('state', ''), '예찰 결과 대기')
        window = task.get('window_id', '').rsplit('_', 1)[-1]
        if window:
            current = window + ' · ' + current
        remain = f'윈도우 {max(0,total-done)}개 → 인계 → 스테이션 복귀' if total else '예찰 후 수확 → 인계 → 복귀'
        if total and done == total:
            current, remain = '수확 완료 · 인계 대기/진행', '인계 → 스테이션 복귀'
        harvest_job = jobs.get('harvest', {})
        if harvest_job:
            current = PHASES.get(harvest_job.get('feedback',{}).get('event'), '인계 작업 중')
            if harvest_job.get('state')=='SUCCEEDED':current='인계·자세 복원 완료 · 복귀 대기'
        if 'harvest_return_goal' in e:
            current, remain = '스테이션 복귀 중', '스테이션 복귀'
        if success(e.get('harvest_return_result', {})):
            current, remain = '스테이션 복귀 완료', '없음'
        elif stopped:
            current = '중단 · '+('수확 완료, 후속 작업 미완료' if total and done==total else '수확 미완료')
        harvest_section=read_json(self.base/'single_cycle.json').get('section','SEC01')
        lines += [f'수확  {harvest_section} | {current}', '  '+bar(done,total,'윈도우'),
                  f"  수확 집계 {count}개 / 예찰 예상 {scout.get('total_expected_count', '?')}개"+
                  (' · 이전 시험 실적 재사용' if 'harvest_reused' in e else ''),
                  '  남은 일: '+remain, '']

        transport_job = jobs.get('transport', {})
        approached = 'WAITING_FOR_TRANSFER' in transport_job.get('observed_events', {})
        handed = (transport_job.get('state')=='SUCCEEDED' and harvest_job.get('state')=='SUCCEEDED')
        # 선별장 명령은 양측 인계 성공 뒤에만 시작한다. 오래된 기록도 이 근거로 호환한다.
        handed = handed or 'unload_goal' in e
        unloaded, returned = success(e.get('unload_result', {})), success(e.get('return_result', {}))
        approached = approached or handed
        td = int(approached) + int(handed) + int(unloaded) + int(returned)
        current, remain = '수확 완료 대기', '수확물 인계 → 선별장 하역 → 복귀'
        if 'pickup_started' in e:
            current = PHASES.get(transport_job.get('feedback',{}).get('event'), '운송 접수 대기')
            feedback_time = transport_job.get('feedback',{}).get('timestamp')
            if self.transport_detail and feedback_time and self.transport_detail[0] > datetime.fromisoformat(feedback_time).timestamp():
                current = self.transport_detail[1]
        if handed:
            current, remain = '선별장 이동 준비', '선별장 이동·도킹·하역 → 복귀'
        if 'unload_goal' in e:
            feedback = e.get('unload_feedback', {}).get('data', {})
            phase = feedback.get('event', '')
            current = '선별장으로 주행 중' if phase=='MOVING_STARTED' else PHASES.get(phase, '선별장 이동·도킹·하역 중')
            if (self.transport_detail and feedback.get('timestamp') and
                    self.transport_detail[0]>datetime.fromisoformat(feedback['timestamp']).timestamp()):
                current='선별장 · '+self.transport_detail[1]
        if unloaded:
            current, remain = '하역 완료 · 선별 대기', '선별 후 스테이션 복귀'
        if 'return_goal' in e:
            phase = e.get('return_feedback',{}).get('data',{}).get('phase','')
            current = '복귀 · '+PHASES.get(phase,'스테이션 복귀 중')
        if returned:
            current, remain = '스테이션 복귀 완료', '없음'
        elif stopped:
            current = ('실패' if transport_job.get('state') in FAILED else '중단')+' · '+current
            # 실패를 마지막 진행 상태로 덮지 않는다.
            if transport_job.get('state') in FAILED and transport_job.get('result'):
                r=transport_job['result'];current='실패 · '+r.get('error_code',r.get('result_code',''))
            for label in ('unload','return'):
                outcome=e.get(label+'_result',{})
                if outcome and not success(outcome):current='실패 · '+outcome.get('result',{}).get('error_code',label)
        lines += ['운송  | '+current, '  '+bar(td,4,'단계')+' (수령 접근 → 인계 → 선별장 하역 → 복귀)', '  남은 일: '+remain, '']

        sorted_event = e.get('sort_result', {})
        sort_data = sorted_event.get('result', e.get('sort_feedback', {}).get('data', {}))
        sorted_count = sort_data.get('red_count', 0) + sort_data.get('yellow_count', 0)
        cargo = read_json(self.base/'cargo_manifest.json')
        inputs = len(cargo.get('fruit_paths', []))
        current = '완료' if success(sorted_event) else '실패' if sorted_event else '선별 중' if 'sort_goal' in e else '투입 대기'
        if 'sort_goal' in e and not sorted_event and sort_data.get('phase'):
            current+=' · '+sort_data['phase']
        if stopped and not sorted_event:current='중단' if 'sort_goal' in e else '미실행 · 앞 단계 중단'
        lines += ['선별팔 | '+current, '  '+bar(sorted_count,inputs,'과실'),
                  '  '+('남은 일: 없음 · 실제 잔량은 별도 결과 확인' if success(sorted_event) else '남은 일: 색별 선별·보관·HOME 복귀'), '']
        error = final.get('error') or e.get('error', {}).get('detail')
        if failed_job:
            r=failed_job.get('result') or {}
            error=' / '.join(v for v in (r.get('error_code'),r.get('error_message') or failed_job.get('reason')) if v)
        elif error:
            error=str(error).splitlines()[0]
            if len(error)>250:error=error[:250]+'… (result.json 확인)'
        if error:
            lines += ['오류: '+str(error)]
        if state == '진행 중' and log.exists() and time.time()-log.stat().st_mtime > 15:
            lines += ['주의: 로그 갱신 지연 · 마지막 기록 표시 (로봇 상태 확인 필요)']
        if state == '중단':
            lines += ['중단 전 마지막 작업입니다. 남은 일은 자동 재개를 의미하지 않습니다.']
        lines += ['Ctrl+C: 이 모니터만 종료 · 로봇/시험에는 명령을 보내지 않음']
        return '\n'.join(lines)


def fit(line: str, width: int) -> str:
    result, size = '', 0
    for char in line:
        if unicodedata.category(char).startswith('C'):
            continue
        size += 2 if unicodedata.east_asian_width(char) in ('W','F') else 1
        if size > width:
            break
        result += char
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('run', nargs='?', type=Path,
                        help='생략: 최신 시험 자동 추적 / 반복 시험 폴더: current attempt 추적 / 개별 시험 폴더: 고정')
    parser.add_argument('--once', action='store_true', help='한 번 출력하고 종료')
    args = parser.parse_args()
    if args.run is not None and not args.run.is_dir():
        parser.error('시험 폴더가 없습니다.')
    if args.run is not None:
        args.run = args.run.resolve()
    monitor = None
    following = args.run is None or (args.run/'status.json').exists() or (args.run/'continuation_status.json').exists()
    interactive = sys.stdout.isatty() and not args.once
    try:
        if interactive:
            print('\033[?1049h\033[?25l', end='', flush=True)
        while True:
            target = select_run(args.run, monitor.base if monitor else None)
            if target is not None and (monitor is None or target != monitor.base):
                # 이전 attempt의 진행률·오류·로그 offset을 새 시험에 섞지 않는다.
                monitor = Monitor(target)
            if monitor is None:
                screen = '농장 시험 모니터 | 시험 시작 대기 · 새 시험을 자동으로 찾습니다.'
            else:
                monitor.poll()
                screen = monitor.screen()
                if following:
                    screen = ('자동 추적: '+str(monitor.base.relative_to(ROOT/'sim/runs')
                              if monitor.base.is_relative_to(ROOT/'sim/runs') else monitor.base)
                              +' · 재시작 시 화면 자동 전환\n'+screen)
            if interactive:
                terminal = shutil.get_terminal_size()
                lines = screen.splitlines()
                if len(lines) >= terminal.lines:
                    lines = [line for line in lines if line]
                screen = '\n'.join(fit(line,terminal.columns-1) for line in lines[:terminal.lines-1])
            print(('\033[H' if interactive else '')+screen+('\033[J' if interactive else ''), end='\n', flush=True)
            if not interactive:
                break
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        if interactive:
            print('\033[?25h\033[?1049l', end='', flush=True)


if __name__ == '__main__':
    main()
