"""새 예찰부터 병행 전체 사이클을 재시작하며 최초 완전 성공에서 멈춘다."""
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[2]


def complete(result: dict) -> bool:
    """액션·복귀 완료와 집계 유효성을 요구한다. 미선별 수량은 성능 지표다."""
    def ok(reply: dict) -> bool:
        return reply.get('status', reply.get('ros_status')) == 4 and reply.get('result', {}).get('result_code') == 'SUCCESS'
    post = result.get('sorter_and_transport_return', {})
    dock = result.get('dock_final', {}).get('result', {})
    harvest = result.get('harvest_results', [])
    required = ['scout', 'scout_return', 'harvest_return', 'pickup_final', 'dock_final']
    if not result.get('single_section'):required.append('scout_sec02')
    return bool(result.get('passed') and not result.get('scout_reused') and not result.get('harvest_reused')
        and all(ok(result.get(k, {})) for k in required)
        and harvest and len(harvest) == result.get('window_count') and all(ok(x) for x in harvest)
        and all(dock.get(k) is True for k in ('transfer_complete', 'transport_clear', 'restore_complete'))
        and all(ok(post.get(k, {})) for k in ('unload', 'sort', 'return'))
        and post.get('count_valid')
        and isinstance(post.get('input_count'), int) and isinstance(post.get('sorted_count'), int)
        and 0 <= post['sorted_count'] <= post['input_count']
        and isinstance(post.get('remaining_fruit_paths'), list))


def main() -> None:
    signal.signal(signal.SIGINT,signal.default_int_handler)
    signal.signal(signal.SIGTERM,signal.default_int_handler)
    base = Path(sys.argv[1]).resolve()
    if not base.is_relative_to(ROOT / 'sim/runs'):
        raise ValueError('sim/runs 아래 새 디렉터리가 필요합니다.')
    if os.environ.get('ROS_DOMAIN_ID') != '13' or os.environ.get('ROS_AUTOMATIC_DISCOVERY_RANGE') != 'SUBNET':
        raise ValueError('ROS Domain13/SUBNET 필요')
    section_mode='--sections' in sys.argv
    sections=(sys.argv[sys.argv.index('--sections')+1].split(',') if section_mode else ['SEC01'])
    if not sections or len(set(sections))!=len(sections) or any(s not in {f'SEC{i:02d}' for i in range(1,17)} for s in sections):
        raise ValueError('중복 없는 SEC01~16 목록 필요')
    resume_pid = int(sys.argv[sys.argv.index('--resume-active')+1]) if '--resume-active' in sys.argv else None
    base.mkdir(parents=True, exist_ok=resume_pid is not None)
    if '--video-config' in sys.argv:
        config=Path(sys.argv[sys.argv.index('--video-config')+1])
        (base/'portfolio_capture.json').write_bytes(config.read_bytes())
    previous=json.loads((base/'status.json').read_text()) if resume_pid is not None else {}
    attempts = previous.get('attempts', [])
    completed=previous.get('completed_sections', [])
    if resume_pid is not None:
        if previous.get('sections') != sections or previous.get('state') != 'RUNNING':
            raise ValueError('진행 중인 동일 섹션 목록만 인수 가능')
        expected=str(base / f"attempt_{len(attempts):03d}")
        command=Path(f'/proc/{resume_pid}/cmdline').read_bytes().split(b'\0')
        if expected.encode() not in command or not any(x.endswith(b'/run_single_cycle.py') for x in command):
            raise ValueError('현재 시험 PID/경로 불일치')
    def save(state: str, **values) -> None:
        data = dict(state=state, updated_at=datetime.now(timezone.utc).isoformat(), attempts=attempts,
                    sections=sections, completed_sections=completed, **values)
        temp = base / 'status.tmp'; temp.write_text(json.dumps(data, ensure_ascii=False, indent=2)+'\n')
        temp.replace(base / 'status.json')
    index = len(attempts)
    while True:
        if (base/'STOP').exists():save('STOPPED');return
        if resume_pid is not None:
            entry=attempts[-1]; section=entry['section']; trial=Path(entry['path'])
            entry['supervisor_reattached_at']=datetime.now(timezone.utc).isoformat()
            save('RUNNING', current=str(trial))
            try:
                while True:
                    try:stat=Path(f'/proc/{resume_pid}/stat').read_text()
                    except FileNotFoundError:break
                    if stat.split(') ',1)[1].startswith('Z'):break
                    if (base/'STOP').exists():raise KeyboardInterrupt
                    time.sleep(1)
            except KeyboardInterrupt:
                os.killpg(resume_pid, signal.SIGINT)
                save('STOPPED', current=str(trial)); return
            # 비자식의 OS 종료코드는 얻을 수 없다. 원본 실행기의 최종 결과로 검증한다.
            code=None
            resume_pid=None
        else:
            index += 1
            section=sections[len(completed)]
            trial = base / f'attempt_{index:03d}'
            entry = dict(attempt=index, section=section, path=str(trial), started_at=datetime.now(timezone.utc).isoformat())
            attempts.append(entry); save('RUNNING', current=str(trial))
            with (base / f'attempt_{index:03d}_runner.log').open('w') as stream:
                command=[sys.executable,str(ROOT/'sim/tools/run_single_cycle.py'),str(trial)]
                command+=['--section',section] if section_mode else ['--overlap-cycle']
                process = subprocess.Popen(command, cwd=ROOT, stdout=stream, stderr=subprocess.STDOUT, start_new_session=True)
                try:
                    while process.poll() is None:
                        if (base/'STOP').exists():raise KeyboardInterrupt
                        time.sleep(1)
                    code = process.returncode
                except KeyboardInterrupt:
                    os.killpg(process.pid, signal.SIGINT)
                    process.wait(timeout=180)
                    save('STOPPED', current=str(trial))
                    raise
        try: result = json.loads((trial / 'result.json').read_text())
        except (OSError, ValueError): result = {}
        entry.update(finished_at=datetime.now(timezone.utc).isoformat(), exit_code=code,
            success=code in (0, None) and complete(result) and (not section_mode or result.get('section')==section),
            error=result.get('error', ''))
        if entry['success']:
            completed.append(section)
            print('SUCCESS:',section,trial,flush=True)
            if len(completed)==len(sections):
                save('SUCCEEDED', successful_attempt=str(trial));return
            save('NEXT_SECTION',current=str(trial))
            continue
        if not entry['error']: entry['error'] = '성공 조건 미충족 또는 준비/프로세스 오류; runner.log 확인'
        save('RESTARTING', current=str(trial))
        print('RETRY:', json.dumps(entry, ensure_ascii=False), flush=True)
        # 실패 원문·분류를 보존한 뒤 같은 섹션을 재시작한다.
        try:
            subprocess.run([sys.executable,str(ROOT/'sim/tools/analyze_cycle_failures.py'),str(base)],cwd=ROOT,
                           stdout=subprocess.DEVNULL,timeout=120,check=False)
        except subprocess.TimeoutExpired:
            entry['analysis_error']='실패 분석 120초 초과; 원본 로그 보존'
        # run_single_cycle이 자식 프로세스를 정리한 뒤 새 시뮬/초기 과실/예찰을 생성한다.
        time.sleep(3)


if __name__ == '__main__':
    main()
