#!/usr/bin/env python3
"""SEC01~16 예찰→모든 window 수확. 재기동 시 성공한 예찰을 재사용하고 로그 보존."""
from __future__ import annotations

import argparse
import copy
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import time
import traceback

ROOT = Path(__file__).resolve().parents[2]
RUNS = ROOT / 'sim/runs'
ARTIFACT_DIRS = ('scout_survey', 'drive_diagnostics', 'apriltag', 'harvest_motion',
                 'robotarm/student', 'runtime')


def utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def save(path: Path, value: dict) -> None:
    """완성된 JSON만 관측되도록 동일 디렉터리에서 교체한다."""
    temp = path.with_suffix(path.suffix + '.tmp')
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
    temp.replace(path)


def validate_scout_result(data: dict, section: str) -> None:
    """성공한 해당 SEC의 완전한 window 목록만 재사용한다."""
    result = data.get('result', {})
    tasks = result.get('harvest_tasks')
    if (data.get('status') != 4 or result.get('result_code') != 'SUCCESS'
            or result.get('section_id') != section):
        raise ValueError('재사용할 예찰 결과가 해당 SEC의 SUCCESS가 아님')
    if not isinstance(tasks, list) or len(tasks) != result.get('harvest_task_count'):
        raise ValueError('예찰 결과 window 개수와 목록 불일치')


def cache_scout_result(directory: Path, section: str, data: dict) -> dict:
    """지도 불변인 동일 캠페인 안에서 원본 결과와 출처를 원자적으로 보존한다."""
    validate_scout_result(data, section)
    cache = dict(section=section, map_id='farm_map_v1', saved_at=utc(),
                 source_attempt=directory.name, scout_result=data)
    path = directory.parent / 'scout_cache' / f'{section}.json'
    path.parent.mkdir(exist_ok=True)
    save(path, cache)
    return cache


def load_scout_cache(output: Path, section: str) -> dict | None:
    """기존 실행 중 도입할 때도 가장 최근 성공 예찰을 찾아 수확 실패와 무관하게 보존한다."""
    path = output / 'scout_cache' / f'{section}.json'
    if path.exists():
        cache = json.loads(path.read_text())
        if cache.get('map_id') != 'farm_map_v1' or cache.get('section') != section:
            raise ValueError('예찰 캐시 지도/SEC 불일치')
        validate_scout_result(cache['scout_result'], section)
        return cache
    for directory in sorted(output.glob(f'{section}_attempt_*'), reverse=True):
        result_path = directory / 'result.json'
        if not result_path.exists():
            continue
        result = json.loads(result_path.read_text())
        data = result.get('scout_result', {})
        try:
            validate_scout_result(data, section)
        except ValueError:
            continue
        return cache_scout_result(directory, section, data)
    return None


def dump_parameters(directory: Path, robot_ids: tuple, event: object) -> None:
    """진단 설정 복사 실패는 별도 기록하며 정상 준비된 로봇의 시험을 중단하지 않는다."""
    for rid in robot_ids:
        for name in ('controller_server', 'velocity_smoother'):
            path = directory / f'{rid}_{name}_params.yaml'
            with path.open('w') as output:
                try:
                    result = subprocess.run(['ros2', 'param', 'dump', f'/{rid}/{name}'],
                                            stdout=output, stderr=subprocess.STDOUT, timeout=20)
                    if result.returncode:
                        event('diagnostic_error', dict(operation='param_dump', node=f'/{rid}/{name}',
                                                      returncode=result.returncode))
                except (subprocess.TimeoutExpired, OSError) as error:
                    event('diagnostic_error', dict(operation='param_dump', node=f'/{rid}/{name}',
                                                  error=str(error)))


def run_worker(directory: Path, section: str) -> int:
    """실제 공통 Action 계약을 사용하고 독립 구독으로 명령/위치를 기록한다."""
    import rclpy
    from rclpy.action import ActionClient
    from rclpy.node import Node
    from rclpy.qos import qos_profile_sensor_data
    from rosidl_runtime_py.convert import message_to_ordereddict
    from rosidl_runtime_py.set_message import set_message_fields
    from rosidl_runtime_py.utilities import get_message
    from lifecycle_msgs.srv import GetState
    from farm_interfaces.action import ScoutArea, HarvestTask

    rclpy.init()
    node = Node('section_campaign_observer')
    events = (directory / 'events.jsonl').open('a', buffering=1)
    telemetry = (directory / 'telemetry.jsonl').open('a', buffering=1)
    state = {'section': section, 'status': 'STARTING', 'started_at': utc(),
             'harvest_results': [], 'phase': 'startup',
             'harvest_policy': 'camera_attempt_retry_once_v1'}
    latest, last_logged, subscriptions = {}, {}, {}
    sim_clock = [None, time.monotonic()]
    handle = None

    def event(kind: str, data: object) -> None:
        events.write(json.dumps(dict(at=utc(), monotonic_s=time.monotonic(),
                                    kind=kind, data=data), ensure_ascii=False) + '\n')

    def record(topic: str, message: object) -> None:
        now = time.monotonic()
        latest[topic] = now
        if topic == '/clock':
            stamp = message.clock.sec + message.clock.nanosec / 1e9
            if stamp != sim_clock[0]:
                sim_clock[:] = [stamp, now]
        if topic == '/rosout' and message.level < 30:
            return
        period = 0 if 'cmd_vel' in topic or topic == '/rosout' else .2
        if now - last_logged.get(topic, -1e9) < period:
            return
        last_logged[topic] = now
        data = dict(message_to_ordereddict(message))
        telemetry.write(json.dumps(dict(at=utc(), monotonic_s=now, topic=topic,
                                        sim_time_s=sim_clock[0], data=data)) + '\n')

    def discover() -> None:
        topics = node.get_topic_names_and_types()
        for topic, types in topics:
            wanted = topic in ('/clock', '/rosout', '/tf', '/tf_static') or (
                topic.startswith(('/scout_01/', '/harvest_01/')) and
                topic.rsplit('/', 1)[-1] in ('cmd_vel', 'cmd_vel_nav', 'odom', 'amcl_pose'))
            if wanted and topic not in subscriptions and len(types) == 1:
                subscriptions[topic] = node.create_subscription(
                    get_message(types[0]), topic, lambda msg, t=topic: record(t, msg),
                    qos_profile_sensor_data)
                event('subscribe', {'topic': topic, 'type': types[0]})
        save(directory / 'topics.json', dict(topics=topics))

    node.create_timer(5., discover)
    scout = ActionClient(node, ScoutArea, '/scout_01/scout_area')
    harvest = ActionClient(node, HarvestTask, '/harvest_01/harvest_task')

    def wait(future: object, timeout: float) -> object:
        end = time.monotonic() + timeout
        while not future.done():
            rclpy.spin_once(node, timeout_sec=.1)
            if (directory.parent / 'STOP').exists():
                raise InterruptedError('사용자 STOP 요청')
            if time.monotonic() > end:
                raise TimeoutError(f'{state["phase"]} 대기 제한 {timeout}s 초과')
            if state['phase'] != 'startup' and time.monotonic() - sim_clock[1] > 120:
                raise TimeoutError('시뮬 clock 진행이 120초 이상 멈춤')
        return future.result()

    def action(client: object, goal: object, timeout: float) -> object:
        nonlocal handle
        handle = None
        event('goal', dict(message_to_ordereddict(goal)))
        handle = wait(client.send_goal_async(goal, feedback_callback=lambda msg:
            event('feedback', dict(message_to_ordereddict(msg.feedback)))), 30)
        if not handle.accepted:
            raise RuntimeError(f'{state["phase"]} Goal 거절')
        response = wait(handle.get_result_async(), timeout)
        data = dict(status=response.status, result=dict(message_to_ordereddict(response.result)))
        event('result', data)
        handle = None
        return response, data

    try:
        cache = load_scout_cache(directory.parent, section)
        state['scout_reused'] = cache is not None
        if cache is not None:
            state.update(scout_result=cache['scout_result'],
                         scout_source_attempt=cache['source_attempt'])
            event('scout_reused', cache)
        save(directory / 'result.json', state)
        # 캐시가 있으면 예찰 준비를 기다리지 않고 수확 로봇만 확인한다.
        robot_ids = ('harvest_01',) if cache is not None else ('scout_01', 'harvest_01')
        lifecycle = [node.create_client(GetState, f'/{rid}/{name}/get_state')
                     for rid in robot_ids
                     for name in ('controller_server', 'planner_server', 'amcl')]
        deadline = time.monotonic() + 300
        while True:
            discover()
            rclpy.spin_once(node, timeout_sec=.2)
            fresh = all(time.monotonic() - latest.get(f'/{rid}/odom', -1e9) < 2
                        for rid in robot_ids)
            if (cache is not None or scout.server_is_ready()) and harvest.server_is_ready() and fresh:
                if all(c.service_is_ready() for c in lifecycle):
                    states = [wait(c.call_async(GetState.Request()), 10).current_state.id
                              for c in lifecycle]
                    if all(s == 3 for s in states):
                        break
            if time.monotonic() > deadline:
                raise TimeoutError(f'300초 내 {robot_ids} Action/Nav2/odom 준비 실패')
            time.sleep(.5)
        event('ready', {'sim_time_s': sim_clock[0]})
        try:
            snapshot = json.loads((RUNS / 'runtime/harvest_scene.json').read_text())
            if not snapshot.get('complete') or not 0 <= time.monotonic()-snapshot['written_monotonic_s'] < 5:
                raise ValueError('수확 전 정답 snapshot이 불완전하거나 오래됨')
            save(directory / 'initial_scene.json', snapshot)
            baseline = directory.parent / 'evaluation_scene_initial.json'
            if not baseline.exists():
                save(baseline, snapshot)
        except (OSError, ValueError, KeyError) as error:
            event('diagnostic_error', dict(operation='initial_scene', error=str(error)))
        dump_parameters(directory, robot_ids, event)
        state.update(status='RUNNING', phase='harvest' if cache is not None else 'scout')
        save(directory / 'result.json', state)
        if cache is None:
            goal = ScoutArea.Goal()
            goal.robot_id, goal.map_id, goal.frame_id = 'scout_01', 'farm_map_v1', 'map'
            goal.task_id, goal.section_id = 'CAMPAIGN_' + directory.name, section
            goal.crop_type, goal.target_ripeness, goal.timestamp = 'PAPRIKA', 'RIPE', utc()
            response, data = action(scout, goal, 1800)
            state['scout_result'] = data
            save(directory / 'result.json', state)
            if response.status != 4 or response.result.result_code != 'SUCCESS':
                raise RuntimeError('예찰 실패: ' + response.result.error_code + ' ' + response.result.error_message)
            cache = cache_scout_result(directory, section, data)
            state['scout_source_attempt'] = cache['source_attempt']
            event('scout_cached', cache)
        # 원래 순서/좌표/수량을 복원한다. 전체 재시작으로 과실도 초기화되므로
        # 이전 시도에서 완료한 window까지 포함해 W001부터 다시 수확한다.
        scout_result = ScoutArea.Result()
        # ROS 변환은 입력의 중첩 목록도 수정하므로 로그 원본은 별도로 유지한다.
        set_message_fields(scout_result, copy.deepcopy(cache['scout_result']['result']))
        tasks = scout_result.harvest_tasks
        state['window_count'] = len(tasks)
        state['empty_harvest'] = not tasks
        for index, task in enumerate(tasks):
            state.update(phase='harvest', window_index=index + 1, window_id=task.window_id)
            save(directory / 'result.json', state)
            goal = HarvestTask.Goal()
            goal.robot_id, goal.map_id, goal.timestamp = 'harvest_01', 'farm_map_v1', utc()
            goal.harvest_task = task
            response, data = action(harvest, goal, 7500)
            state['harvest_results'].append(data)
            save(directory / 'result.json', state)
            # Action 완료 여부와 수확 실적은 별개다. 개별 시도의 실패 수량으로
            # 정상 종료된 window를 실패시키거나 같은 SEC를 다시 보내지 않는다.
            if response.status != 4 or response.result.result_code != 'SUCCESS':
                raise RuntimeError('수확 실패: ' + response.result.error_code + ' ' + response.result.error_message)
        state.update(status='SUCCESS', phase='complete')
    except BaseException as error:
        state.update(status='STOPPED' if isinstance(error, (KeyboardInterrupt, InterruptedError)) else 'FAILED',
                     error=str(error), traceback=traceback.format_exc())
        event('failure', state)
        if handle is not None and handle.accepted:
            try:
                # 취소 결과도 기록한 뒤 supervisor가 전체 스택을 종료한다.
                future = handle.cancel_goal_async()
                rclpy.spin_until_future_complete(node, future, timeout_sec=10)
                future = handle.get_result_async()
                rclpy.spin_until_future_complete(node, future, timeout_sec=30)
                if future.done():
                    response = future.result()
                    event('cancel_result', dict(status=response.status,
                          result=dict(message_to_ordereddict(response.result))))
            except Exception as cancel_error:
                event('cancel_error', str(cancel_error))
    finally:
        state['finished_at'] = utc()
        save(directory / 'result.json', state)
        events.close()
        telemetry.close()
        node.destroy_node()
        rclpy.shutdown()
    return 0 if state['status'] == 'SUCCESS' else 1


def stop_group(process: subprocess.Popen) -> None:
    """이번 시험이 만든 프로세스 그룹만 순차 종료한다."""
    for sig, timeout in ((signal.SIGINT, 45), (signal.SIGTERM, 15), (signal.SIGKILL, 5)):
        try:
            os.killpg(process.pid, sig)
        except ProcessLookupError:
            return
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            process.poll()
            try:
                os.killpg(process.pid, 0)
            except ProcessLookupError:
                return
            time.sleep(.5)


def inventory() -> dict[str, int]:
    """시험 산출물의 변경 전 상태만 읽는다."""
    return {str(p): p.stat().st_mtime_ns for name in ARTIFACT_DIRS
            for p in (RUNS / name).rglob('*') if p.is_file()}


def archive(directory: Path, before: dict) -> None:
    """재시작 전에 이번 시도의 변경 산출물을 독립 복사한다."""
    copied = []
    for path, stamp in inventory().items():
        if before.get(path) != stamp:
            source = Path(path)
            dest = directory / 'artifacts' / source.relative_to(RUNS)
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, dest)
            copied.append(str(dest.relative_to(directory)))
    save(directory / 'artifacts.json', dict(files=copied, archived_at=utc()))


def write_analysis(output: Path, summary: dict) -> None:
    """성공률 분모에서 실패 시도를 숨기지 않고 원인별 증거 색인을 갱신한다."""
    groups = {}
    sections = {}
    for item in summary['attempts']:
        sections.setdefault(item['section'], []).append(item)
        if item['status'] != 'SUCCESS':
            key = (item.get('phase') or 'unknown') + ': ' + (item.get('error') or item['status'])
            groups.setdefault(key, []).append(item['directory'])
    save(output / 'failure_analysis.json', dict(
        updated_at=utc(), campaign_status=summary['status'],
        completed_sections=summary['completed_sections'], total_attempts=len(summary['attempts']),
        failure_groups=[dict(signature=k, count=len(v), evidence=v) for k, v in groups.items()],
        sections=sections,
        interpretation='오류 문구별 집계이며 근본 원인 확정은 events/telemetry/stack/drive/arm 원본 대조 필요'))
    # 오프라인 성능 집계 오류가 다음 SEC 실행을 중단시키지 않도록 분리한다.
    try:
        from campaign_performance import write_performance
        write_performance(output)
    except Exception as error:
        save(output / 'performance_error.json', dict(updated_at=utc(), error=str(error)))


def campaign(output: Path, args: argparse.Namespace) -> int:
    """각 SEC가 성공할 때까지 제한 없는 재시도와 재기동을 수행한다."""
    output.mkdir(parents=True, exist_ok=True)
    # 중복 감독 프로세스로 인한 동시 Goal/UDP 포트 충돌을 막는다.
    import fcntl
    lock = (output / 'campaign.lock').open('w')
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    lock.write(str(os.getpid())); lock.flush()
    env = dict(os.environ, ROS_DOMAIN_ID=str(args.domain),
               ROS_AUTOMATIC_DISCOVERY_RANGE='SUBNET', PYTHONUNBUFFERED='1')
    metadata = dict(started_at=utc(), sections=args.sections, ros_domain_id=args.domain,
                    ros_automatic_discovery_range=env['ROS_AUTOMATIC_DISCOVERY_RANGE'],
                    headless=True, rviz=False, tag_correction=True,
                    success_rule='Scout SUCCESS then every returned window ROS SUCCEEDED/result SUCCESS; counts are yield only',
                    reset_rule='Every attempt starts a fresh full Isaac + ROS stack; failures retry same SEC',
                    scout_reuse_rule='Same unchanged-map campaign: persist successful scout; retry all cached windows from harvest',
                    empty_harvest_rule='Zero returned windows is logged explicitly; no synthetic harvest',
                    git_head=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
                    source_hashes={})
    for tree in ('sim/ros_ws/src/farm_sim_config/config', 'robot/config/navigation'):
        for path in (ROOT / tree).rglob('*'):
            if path.is_file():
                metadata['source_hashes'][str(path.relative_to(ROOT))] = hashlib.sha256(path.read_bytes()).hexdigest()
    session_source = ROOT / 'sim/ros_ws/src/farm_sim_devices/farm_sim_devices/student_session.py'
    metadata['source_hashes'][str(session_source.relative_to(ROOT))] = hashlib.sha256(session_source.read_bytes()).hexdigest()
    if not (output / 'manifest.json').exists():
        save(output / 'manifest.json', metadata)
    shutil.copy2(__file__, output / ('runner_snapshot_' + datetime.now().strftime('%H%M%S') + '.py'))
    completed = []
    attempts = []
    summary = dict(status='RUNNING', started_at=utc(), completed_sections=completed, attempts=attempts)
    if (output / 'summary.json').exists():
        if not args.resume:
            raise RuntimeError('기존 시험 폴더는 --resume으로만 이어 실행할 수 있습니다.')
        summary['started_at'] = json.loads((output / 'summary.json').read_text())['started_at']
        for directory in sorted(output.glob('SEC*_attempt_*')):
            path = directory / 'result.json'
            result = json.loads(path.read_text()) if path.exists() else {}
            unfinished = result.get('status') not in ('SUCCESS', 'FAILED', 'STOPPED', 'INTERRUPTED')
            if unfinished or not (directory / 'artifacts.json').exists():
                # 감독자가 종료된 시도는 성공으로 간주하지 않는다. 남은 소유 프로세스를
                # 정확한 시도 경로로 식별하고 종료한 뒤 같은 SEC를 다시 실행한다.
                pids_path = directory / 'pids.json'
                pids = json.loads(pids_path.read_text()) if pids_path.exists() else {}
                for pid in pids.values():
                    proc = Path(f'/proc/{pid}/cmdline')
                    if proc.exists() and str(directory).encode() in proc.read_bytes():
                        os.killpg(pid, signal.SIGINT)
                        end = time.monotonic() + 45
                        while proc.exists() and time.monotonic() < end:
                            time.sleep(.5)
                        if proc.exists() and str(directory).encode() in proc.read_bytes():
                            os.killpg(pid, signal.SIGKILL)
                if unfinished:
                    result.update(status='INTERRUPTED', error='시험 감독 프로세스 중단; 시스템 실패와 별도 분류',
                                  finished_at=utc())
                    save(path, result)
            if not (directory / 'artifacts.json').exists():
                before_path = directory / 'artifact_before.json'
                archive(directory, json.loads(before_path.read_text()) if before_path.exists() else {})
            section, number = directory.name.split('_attempt_')
            attempts.append(dict(section=section, attempt=int(number), status=result['status'],
                                 phase=result.get('phase'), error=result.get('error'), directory=str(directory)))
            if result['status'] == 'SUCCESS' and section not in completed:
                completed.append(section)
    save(output / 'summary.json', summary)
    for section in args.sections:
        if section in completed:
            continue
        attempt = max([a['attempt'] for a in attempts if a['section'] == section], default=0)
        while not (output / 'STOP').exists():
            if shutil.disk_usage(output).free < 10 * 1024**3:
                summary.update(status='BLOCKED', error='로그 보존 공간 10GiB 미만')
                save(output / 'summary.json', summary)
                lock.close()
                return 2
            attempt += 1
            directory = output / f'{section}_attempt_{attempt:04d}'
            directory.mkdir()
            before = inventory()
            save(directory / 'artifact_before.json', before)
            launch_env = dict(env, ROS_LOG_DIR=str(directory / 'ros'))
            command = ['ros2', 'launch', 'farm_sim_runtime', 'all.launch.py',
                       f'project_root:={ROOT}', f'isaac_python:={args.isaac_python}',
                       f'vision_python:={args.vision_python}', 'harvest:=true', 'headless:=true',
                       'rviz:=false', 'tag_correction:=true',
                       f'performance_log:={directory / "performance.jsonl"}']
            save(directory / 'launch.json', dict(command=command, started_at=utc()))
            print(f'{utc()} START {directory.name}', flush=True)
            launch = worker = None
            try:
                with (directory / 'stack.log').open('w') as log, (directory / 'worker.log').open('w') as worker_log:
                    launch = subprocess.Popen(command, cwd=ROOT, env=launch_env,
                        stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
                    worker = subprocess.Popen([sys.executable, __file__, '--worker', str(directory),
                        '--sections', section], cwd=ROOT, env=launch_env, stdout=worker_log,
                        stderr=subprocess.STDOUT, start_new_session=True)
                    save(directory / 'pids.json', dict(launch=launch.pid, worker=worker.pid))
                    last_health = 0.
                    while worker.poll() is None:
                        if (output / 'STOP').exists() or launch.poll() is not None:
                            stop_group(worker)
                            break
                        if time.monotonic() - last_health >= 30:
                            with (directory / 'host_health.log').open('a') as health:
                                health.write(utc() + '\n'); health.flush()
                                for cmd in (['nvidia-smi', '--query-gpu=utilization.gpu,memory.used,temperature.gpu',
                                             '--format=csv,noheader'], ['ps', '-eo', 'pid,ppid,pcpu,pmem,rss,comm']):
                                    try:
                                        subprocess.run(cmd, stdout=health, stderr=subprocess.STDOUT, timeout=10)
                                    except subprocess.TimeoutExpired:
                                        health.write('health command timeout\n')
                            last_health = time.monotonic()
                        time.sleep(1)
            finally:
                # 실패 직후 공유 snapshot을 먼저 보존하고 프로세스를 완전히 종료한다.
                snapshot = RUNS / 'runtime/harvest_scene.json'
                if snapshot.exists():
                    shutil.copy2(snapshot, directory / 'final_scene.json')
                if worker is not None:
                    stop_group(worker)
                if launch is not None:
                    stop_group(launch)
                archive(directory, before)
            result_path = directory / 'result.json'
            result = json.loads(result_path.read_text()) if result_path.exists() else {}
            if result.get('status') not in ('SUCCESS', 'FAILED', 'STOPPED'):
                result.update(status='FAILED', phase=result.get('phase', 'startup'),
                              error='스택 또는 worker가 최종 결과 전에 종료됨', finished_at=utc())
                save(result_path, result)
            attempts.append(dict(section=section, attempt=attempt, status=result['status'],
                                 phase=result.get('phase'), error=result.get('error'), directory=str(directory)))
            print(f'{utc()} {result["status"]} {directory.name} {result.get("error", "")}', flush=True)
            if result['status'] == 'SUCCESS':
                completed.append(section)
            save(output / 'summary.json', summary)
            write_analysis(output, summary)
            if result['status'] == 'SUCCESS':
                break
        if (output / 'STOP').exists():
            summary.update(status='STOPPED', finished_at=utc())
            save(output / 'summary.json', summary)
            lock.close()
            return 130
    summary.update(status='COMPLETE', finished_at=utc())
    save(output / 'summary.json', summary)
    write_analysis(output, summary)
    lock.close()
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--worker', type=Path)
    parser.add_argument('--resume', action='store_true', help='보존한 시도/성공 SEC 이후부터 재개')
    parser.add_argument('--sections', nargs='+', default=[f'SEC{i:02d}' for i in range(1, 17)])
    parser.add_argument('--domain', type=int, default=13)
    parser.add_argument('--isaac-python', default='/home/ysy/isaac/env_isaaclab/bin/python')
    parser.add_argument('--vision-python', default='/home/ysy/venv/robot_venv/bin/python')
    args = parser.parse_args()
    if args.worker:
        return run_worker(args.worker.resolve(), args.sections[0])
    output = args.output or RUNS / ('section_campaign_' + datetime.now().strftime('%Y%m%d_%H%M%S'))
    return campaign(output.resolve(), args)


if __name__ == '__main__':
    raise SystemExit(main())
