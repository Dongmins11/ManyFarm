#!/usr/bin/env python3
"""기존 농장 fleet에 실제 Teacher 작업을 요청하는 유한 시간 검증기입니다.

fixture는 초기 차체 배치에만 사용합니다. 원래288과실 위치·회전·ID는 그대로이며
동작 중 reset/teleport를 하지 않습니다. 실제 결과가 실패여도 숨기지 않고 JSON에 남깁니다.
기본 smoke는 예상 후보의 실제 정책 실행과 안전한 종료를 검사합니다. 실제 안착 성공까지
필요하면 --require-harvest를 사용합니다. 작업 상태와 시험 통과 여부는 별도로 기록합니다.
"""
from __future__ import annotations
import argparse
import json
import math
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
import uuid

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'sim/ros_ws/src/farm_sim_devices'))
from farm_sim_devices.wire import LocalDatagrams


def evaluate_result(result: dict, fixture: dict, log_directory: Path | None, *,
                    require_harvest: bool, cancel_requested: bool, place_hold_s: float) -> dict:
    """실제 요청/시도/결과 로그를 대조합니다. 검증을 위해 물리 상태를 바꾸지 않습니다."""
    terminal = result.get('terminal') or {}
    job_id = result['job_id']
    expected = fixture['expected_target_ids']
    checks, errors = {}, []

    def check(name: str, condition: bool) -> None:
        checks[name] = bool(condition)

    check('terminal_received', terminal.get('job_id') == job_id
          and terminal.get('status') in ('SUCCESS', 'FAILED', 'CANCELED'))
    check('safe_stopped', terminal.get('safe_stopped') is True)
    check('process_exited_cleanly', result.get('process_returncode') == 0)
    check('natural_shutdown_completed', not result.get('natural_shutdown_timeout', False))
    protocol_completed = checks['terminal_received'] and checks['safe_stopped']
    counts = (terminal.get('success_count'), terminal.get('failed_count'))
    check('terminal_counts_valid', all(type(value) is int and value >= 0 for value in counts))
    request, logged_result, events = {}, {}, []
    try:
        if log_directory is None:
            raise ValueError('Teacher 실행 로그 경로가 없습니다.')
        request = json.loads((log_directory/'request.json').read_text())
        logged_result = json.loads((log_directory/'result.json').read_text())
        with (log_directory/'trace.jsonl').open() as trace:
            for line in trace:
                record = json.loads(line)
                if record.get('event') in ('CANDIDATES', 'TARGET', 'ATTEMPT_RESULT', 'RESULT', 'STOP_REQUEST'):
                    # TARGET의 고정 형상 표본은 검증 결과에 중복 저장하지 않습니다.
                    events.append({key:value for key,value in record.items() if key != 'sample'})
                elif record.get('event') == 'POLICY':
                    events.append(dict(event='POLICY', target_id=record.get('target_id')))
        if not isinstance(request, dict) or not isinstance(logged_result, dict):
            raise ValueError('요청/결과 로그는 JSON 객체여야 합니다.')
    except (OSError, ValueError, TypeError, AttributeError) as error:
        errors.append('Teacher 로그 읽기 실패: '+str(error))
    if not isinstance(request, dict):
        request = {}
    if not isinstance(logged_result, dict):
        logged_result = {}
    check('logs_readable', not errors)
    check('request_identity', all(request.get(key) == value for key,value in dict(
        job_id=job_id, robot_id=fixture['robot_id'], map_id=fixture['map_id'],
        task_id='teacher_physical_check', window_id=fixture['source'], expected_count=len(expected),
        goal_pose=dict(x=fixture['xy_m'][0], y=fixture['xy_m'][1], yaw=fixture['yaw_rad'])).items()))
    keys = ('job_id', 'status', 'success_count', 'failed_count', 'safe_stopped', 'error_code', 'event_seq')
    check('logged_terminal_matches', bool(logged_result)
          and all(logged_result.get(key) == terminal.get(key) for key in keys))
    final_events = [event for event in events if event['event'] == 'RESULT']
    check('trace_terminal_matches', len(final_events) == 1
          and all(final_events[0].get(key) == terminal.get(key) for key in keys))
    candidate_events = [event for event in events if event['event'] == 'CANDIDATES']
    candidates = (candidate_events[0].get('candidates', []) if len(candidate_events) == 1 else [])
    if not isinstance(candidates, list):
        candidates = []
        errors.append('CANDIDATES.candidates가 배열이 아닙니다.')
    candidate_ids = [entry.get('target_id') for entry in candidates if isinstance(entry, dict)]
    selected = [event.get('target_id') for event in events if event['event'] == 'TARGET']
    policy_ids = [event.get('target_id') for event in events if event['event'] == 'POLICY']
    attempts = logged_result.get('attempts', [])
    if not isinstance(attempts, list):
        attempts = []
        errors.append('attempts가 배열이 아닙니다.')
    attempts_valid = all(isinstance(record, dict) and isinstance(record.get('target_id'), str)
                         and type(record.get('success')) is bool for record in attempts)
    check('attempt_records_valid', attempts_valid)
    if not attempts_valid:
        attempts = []
    recorded = [record['target_id'] for record in attempts]
    identifiers_valid = all(isinstance(value, str) for value in (*candidate_ids, *selected, *policy_ids))
    check('target_identifiers_valid', identifiers_valid)
    # 형식 오류도 report로 남기고 종료합니다. 잘못된 ID를 정상 후보로 추정하지 않습니다.
    if not identifiers_valid:
        candidate_ids, selected, policy_ids = [], [], []
    expected_set = set(expected)
    check('candidates_match_fixture', len(candidate_events) == 1
          and set(candidate_ids) == expected_set and len(candidate_ids) == len(expected))
    check('candidate_count_matches', logged_result.get('candidate_count') == len(candidate_ids))
    check('selected_targets_match_fixture', set(selected) <= expected_set and len(selected) == len(set(selected)))
    check('policy_targets_were_selected', set(policy_ids) <= set(selected))
    check('attempt_targets_match_fixture', set(recorded) <= expected_set and len(recorded) == len(set(recorded)))
    check('actual_policy_executed', bool(policy_ids) if expected else not selected and not policy_ids and not attempts)
    check('completed_window_processed_all', terminal.get('status') != 'SUCCESS' or set(recorded) == expected_set)
    actual_counts = (sum(record['success'] for record in attempts), sum(not record['success'] for record in attempts))
    check('finalized_attempt_counts_match', counts == actual_counts)
    trace_attempts = [dict(event) for event in events if event['event'] == 'ATTEMPT_RESULT']
    for record in trace_attempts:
        record.pop('event')
    check('trace_attempts_match', all(record in attempts for record in trace_attempts)
          and len(trace_attempts) == sum(record.get('reason') != 'target_no_longer_available' for record in attempts))
    previous = (0, 0)
    monotonic = True
    for state in result.get('states', []):
        if state.get('job_id') != job_id:
            continue
        values = (state.get('success_count'), state.get('failed_count'))
        if not all(type(value) is int and value >= old for value,old in zip(values, previous)):
            monotonic = False
            break
        previous = values
    check('feedback_counts_monotonic', monotonic and checks['terminal_counts_valid']
          and all(value >= old for value,old in zip(counts, previous)))
    if result.get('cancel_after_s') is not None:
        stop_events = [event for event in events if event['event'] == 'STOP_REQUEST' and event.get('status') == 'CANCELED']
        check('cancel_sent_and_confirmed', cancel_requested and terminal.get('status') == 'CANCELED' and len(stop_events) == 1)
        stop_time = stop_events[0].get('time_s') if stop_events else None
        check('cancel_preserves_finalized_counts', type(stop_time) in (int, float)
              and all(type(record.get('time_s')) in (int, float) and record['time_s'] <= stop_time for record in attempts))
    else:
        check('not_unexpected_cancellation', terminal.get('status') != 'CANCELED')
    confirmed = [record['target_id'] for record in attempts if record['success']
        and record.get('physical_status') == 'SUCCEEDED' and record.get('physical_in_box') is True
        and type(record.get('physical_place_hold_s')) in (int, float)
        and math.isfinite(record['physical_place_hold_s']) and record['physical_place_hold_s']+1e-9 >= place_hold_s]
    harvest_confirmed = bool(confirmed) and checks['terminal_counts_valid'] and counts[0] > 0
    if require_harvest:
        check('harvest_confirmed_in_basket', harvest_confirmed)
    if not expected:
        check('empty_fixture_completed_normally', terminal.get('status') == 'SUCCESS' and counts == (0, 0))
    return dict(protocol_completed=protocol_completed, task_status=terminal.get('status'),
        harvested_count=counts[0], failure_count=counts[1], require_harvest=require_harvest,
        harvest_confirmed=harvest_confirmed, confirmed_target_ids=confirmed, policy_steps=len(policy_ids),
        expected_target_ids=expected, candidate_target_ids=candidate_ids, selected_target_ids=selected,
        finalized_target_ids=recorded, checks=checks, verification_errors=errors,
        passed=all(checks.values()) and not errors)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--isaac-python', type=Path, default=Path.home()/'isaac/env_isaaclab/bin/python')
    parser.add_argument('--fixture', type=Path, default=ROOT/'sim/tests/fixtures/teacher_dock.json')
    parser.add_argument('--output', type=Path, default=ROOT/'sim/runs/robotarm/teacher_check/result.json')
    parser.add_argument('--gui', action='store_true')
    parser.add_argument('--duration-s', type=float, default=90.)
    parser.add_argument('--wall-timeout-s', type=float, default=600.)
    parser.add_argument('--cancel-after-s', type=float)
    parser.add_argument('--require-harvest', action='store_true', help='기본 smoke에 더해 실제 바구니 안착 성공을 1개 이상 요구합니다.')
    parser.add_argument('--teacher-diagnostic-trace', action='store_true',
                        help='담당자 회신용 실제 추론/물리 연속 로그를 추가합니다.')
    args = parser.parse_args()
    for name in ('duration_s', 'wall_timeout_s', 'cancel_after_s'):
        value = getattr(args, name)
        if value is not None and (not math.isfinite(value) or value <= 0):
            parser.error(name+'는 유한한 양수 초여야 합니다.')
    fixture = json.loads(args.fixture.read_text())
    expected = fixture.get('expected_target_ids')
    if (not isinstance(expected, list) or any(not isinstance(value, str) or not value for value in expected)
            or len(expected) != len(set(expected))):
        parser.error('fixture.expected_target_ids는 중복 없는 문자열 배열이어야 합니다.')
    output = args.output.resolve()
    if not output.is_relative_to(ROOT/'sim'):
        parser.error('출력은 project의 sim/ 내부에 저장해야 합니다.')
    directory = output.parent
    directory.mkdir(parents=True, exist_ok=True)
    config = ROOT/'sim/ros_ws/src/farm_sim_config/config'
    fleet = json.loads((config/'harvest_fleet.json').read_text())
    stations = json.loads((ROOT/fleet['station_config']).read_text())
    stations['stations'][fixture['robot_id']].update(xy_m=fixture['xy_m'], yaw_rad=fixture['yaw_rad'])
    def save(name: str, value: dict) -> str:
        path = directory/name
        path.write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n')
        return str(path.relative_to(ROOT))
    fleet['station_config'] = save('test_stations.json', stations)
    devices = []
    harvest = None
    for i, file in enumerate(fleet['device_configs']):
        device = json.loads((ROOT/file).read_text())
        # 실행 프로세스·포트를 분리하고 센서는 원 설정을 그대로 둡니다.
        device['runtime'].update(command_port=21600+10*i, telemetry_port=21601+10*i)
        devices.append(save('test_'+device['robot_id']+'.json', device))
        if device['robot_id'] == fixture['robot_id']:
            harvest = device
    fleet['device_configs'] = devices
    fleet['clock'] = dict(command_port=21690, telemetry_port=21691)
    fleet_path = save('test_fleet.json', fleet)
    command = [str(args.isaac_python), str(ROOT/'sim/ros_ws/src/farm_sim_runtime/farm_sim_runtime/run_fleet.py'),
               '--project-root', str(ROOT), '--fleet-config', fleet_path, '--duration-s', str(args.duration_s),
               '--stop-after-arm-job']
    for path in ('sim/ros_ws/src/farm_sim_devices','sim/ros_ws/src/farm_sim_runtime','robot/ros_ws/src/farm_common'):
        command += ['--module-path', str(ROOT/path)]
    if not args.gui:
        command.append('--headless')
    if args.teacher_diagnostic_trace:
        command.append('--teacher-diagnostic-trace')
    rt = harvest['runtime']
    policy_profile = json.loads((ROOT/rt['harvest_arm']['profile']).read_text())
    place_hold_s = float(policy_profile['runtime']['place_hold_s'])
    transport = LocalDatagrams(rt['telemetry_port'], rt['command_port'])
    job = uuid.uuid4().hex
    result = dict(scope=fixture['scope'], fixture=fixture, job_id=job, command=command,
                  terminal=None, states=[], received_packets=0, completed=False,
                  cancel_after_s=args.cancel_after_s, place_hold_s=place_hold_s)
    start_wall, last_send, sim_start = time.monotonic(), -float('inf'), None
    state, latest, previous_signature = None, None, None
    started, canceled = False, False
    with (directory/'isaac.log').open('w') as log:
        process = subprocess.Popen(command, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        try:
            while time.monotonic()-start_wall < args.wall_timeout_s:
                for packet in transport.receive():
                    if packet.get('kind') != 'state' or not packet.get('arm'):
                        continue
                    state, latest = packet['arm'], packet
                    result['received_packets'] += 1
                    if sim_start is None:
                        sim_start = packet['stamp_ns']/1e9
                    signature = (state['job_id'], state['status'], state['stage'], state['event_seq'])
                    if signature != previous_signature:
                        print(json.dumps(dict(sim_time_s=packet['stamp_ns']/1e9, **state)), flush=True)
                        result['states'].append(dict(sim_time_s=packet['stamp_ns']/1e9, **state))
                        previous_signature = signature
                    if state['job_id'] == job and state['status'] in ('SUCCESS','FAILED','CANCELED'):
                        result['terminal'], result['completed'] = state, True
                if result['completed']:
                    break
                # 자연 종료 직전 전송한 최종 UDP도 한 번 비운 뒤 프로세스 종료를 확인합니다.
                if process.poll() is not None:
                    break
                wall = time.monotonic()
                if latest and wall-last_send >= .05:
                    sim_now = latest['stamp_ns']/1e9
                    if not started and sim_now-sim_start < 1.:
                        time.sleep(.005)
                        continue
                    if args.cancel_after_s is not None and sim_now-sim_start >= 1.+args.cancel_after_s:
                        canceled = True
                    op = 'cancel' if canceled else 'keepalive' if state['job_id'] == job else 'start'
                    transport.send(dict(kind='harvest_arm',op=op,session=latest['session'],robot_id=fixture['robot_id'],
                        seq=time.monotonic_ns(),sent=wall,job_id=job,map_id=fixture['map_id'],
                        task_id='teacher_physical_check',window_id=fixture['source'],
                        expected_count=len(fixture['expected_target_ids']),
                        goal_pose=dict(x=fixture['xy_m'][0], y=fixture['xy_m'][1], yaw=fixture['yaw_rad'])))
                    started, last_send = True, wall
                time.sleep(.005)
        finally:
            result['termination_method'] = 'process_exit'
            if result['completed'] and process.poll() is None:
                # terminal 이후에는 프레임 경계의 정상 cleanup을 먼저 기다립니다.
                try:
                    process.wait(timeout=60.)
                except subprocess.TimeoutExpired:
                    result['natural_shutdown_timeout'] = True
            if latest and process.poll() is None and not result['completed']:
                transport.send(dict(kind='harvest_arm',op='cancel',session=latest['session'],
                    robot_id=fixture['robot_id'],seq=time.monotonic_ns(),sent=time.monotonic(),job_id=job))
            if process.poll() is None:
                result['termination_method'] = 'sigint'
                try:
                    os.killpg(process.pid, signal.SIGINT)
                except ProcessLookupError:
                    pass
                try:
                    process.wait(timeout=20.)
                except subprocess.TimeoutExpired:
                    result['termination_method'] = 'sigkill'
                    try:
                        os.killpg(process.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                    process.wait(timeout=5.)
            transport.close()
    result.update(process_returncode=process.returncode, wall_elapsed_s=time.monotonic()-start_wall)
    if latest:
        result['teacher_log_dir'] = str(ROOT/'sim/runs/robotarm/teacher'/latest['session']/job)
    result.update(evaluate_result(result, fixture,
        Path(result['teacher_log_dir']) if 'teacher_log_dir' in result else None,
        require_harvest=args.require_harvest, cancel_requested=canceled, place_hold_s=place_hold_s))
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n')
    print('결과: '+str(output), flush=True)
    print(json.dumps(dict(passed=result['passed'], protocol_completed=result['protocol_completed'],
        task_status=result['task_status'], harvested_count=result['harvested_count'], failure_count=result['failure_count'],
        failed_checks=[key for key,value in result['checks'].items() if not value]), ensure_ascii=False), flush=True)
    return 0 if result['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
