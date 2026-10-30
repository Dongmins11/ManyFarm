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
    """액션 완료와 실제 전량 선별을 모두 요구한다. 과거 결과 재사용은 거절한다."""
    def ok(reply: dict) -> bool:
        return reply.get('status', reply.get('ros_status')) == 4 and reply.get('result', {}).get('result_code') == 'SUCCESS'
    post = result.get('sorter_and_transport_return', {})
    dock = result.get('dock_final', {}).get('result', {})
    harvest = result.get('harvest_results', [])
    return bool(result.get('passed') and not result.get('scout_reused') and not result.get('harvest_reused')
        and all(ok(result.get(k, {})) for k in ('scout', 'scout_sec02', 'scout_return', 'harvest_return', 'pickup_final', 'dock_final'))
        and harvest and len(harvest) == result.get('window_count') and all(ok(x) for x in harvest)
        and all(dock.get(k) is True for k in ('transfer_complete', 'transport_clear', 'restore_complete'))
        and all(ok(post.get(k, {})) for k in ('unload', 'sort', 'return'))
        and post.get('count_valid') and post.get('all_input_fruits_sorted')
        and post.get('input_count', 0) > 0 and post.get('sorted_count') == post.get('input_count')
        and post.get('remaining_fruit_paths') == [])


def main() -> None:
    base = Path(sys.argv[1]).resolve()
    if not base.is_relative_to(ROOT / 'sim/runs'):
        raise ValueError('sim/runs 아래 새 디렉터리가 필요합니다.')
    if os.environ.get('ROS_DOMAIN_ID') != '13' or os.environ.get('ROS_AUTOMATIC_DISCOVERY_RANGE') != 'SUBNET':
        raise ValueError('ROS Domain13/SUBNET 필요')
    base.mkdir(parents=True, exist_ok=False)
    attempts = []
    def save(state: str, **values) -> None:
        data = dict(state=state, updated_at=datetime.now(timezone.utc).isoformat(), attempts=attempts, **values)
        temp = base / 'status.tmp'; temp.write_text(json.dumps(data, ensure_ascii=False, indent=2)+'\n')
        temp.replace(base / 'status.json')
    index = 0
    while True:
        index += 1
        trial = base / f'attempt_{index:03d}'
        entry = dict(attempt=index, path=str(trial), started_at=datetime.now(timezone.utc).isoformat())
        attempts.append(entry); save('RUNNING', current=str(trial))
        with (base / f'attempt_{index:03d}_runner.log').open('w') as stream:
            process = subprocess.Popen([sys.executable, str(ROOT / 'sim/tools/run_single_cycle.py'),
                str(trial), '--overlap-cycle'], cwd=ROOT, stdout=stream, stderr=subprocess.STDOUT, start_new_session=True)
            try:
                code = process.wait()
            except KeyboardInterrupt:
                os.killpg(process.pid, signal.SIGINT)
                process.wait(timeout=180)
                save('STOPPED', current=str(trial))
                raise
        try: result = json.loads((trial / 'result.json').read_text())
        except (OSError, ValueError): result = {}
        entry.update(finished_at=datetime.now(timezone.utc).isoformat(), exit_code=code,
            success=code == 0 and complete(result), error=result.get('error', ''))
        if entry['success']:
            save('SUCCEEDED', successful_attempt=str(trial)); print('SUCCESS:', trial, flush=True); return
        if not entry['error']: entry['error'] = '성공 조건 미충족 또는 준비/프로세스 오류; runner.log 확인'
        save('RESTARTING', current=str(trial))
        print('RETRY:', json.dumps(entry, ensure_ascii=False), flush=True)
        # run_single_cycle이 자식 프로세스를 정리한 뒤 새 시뮬/초기 과실/예찰을 생성한다.
        time.sleep(3)


if __name__ == '__main__':
    main()
