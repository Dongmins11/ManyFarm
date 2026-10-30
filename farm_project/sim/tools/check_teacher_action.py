#!/usr/bin/env python3
"""실제 ROS 팔 Action→UDP→Isaac Teacher를 검증한다. Nav2 이동 시험은 아니다.

공통 수확 미션이 호출하는 ArmActionClient와 실제 SimRosAdapter를 사용한다.
fixture는 초기 차체 배치만 바꾸며 과실/관절 teleport 또는 정책 대역은 없다.
ROS 환경을 source한 시스템 Python으로 실행한다.
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
import threading
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT/'sim/ros_ws/src/farm_sim_devices'),
               str(ROOT/'robot/ros_ws/src/harvest_robot')]
from harvest_test_ui import prepare_run, launch_environment
from check_teacher_harvest import evaluate_result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--policy', choices=('teacher', 'student_d435', 'student_u20'), default='teacher', help='검증할 실제 팔 실행기')
    parser.add_argument('--performance-log', type=Path, help='프레임 구간별 성능 기록 경로')
    parser.add_argument('--fixture', type=Path, default=ROOT/'sim/tests/fixtures/teacher60_two.json')
    parser.add_argument('--isaac-python', type=Path, default=Path.home()/'isaac/env_isaaclab/bin/python')
    parser.add_argument('--cancel-after-s', type=float, help='팔 시작 후 시뮬 초 기준 취소 시험')
    args = parser.parse_args()
    if args.cancel_after_s is not None and (not math.isfinite(args.cancel_after_s) or args.cancel_after_s <= 0):
        parser.error("cancel-after-s는 유한한 양수여야 합니다.")
    import rclpy
    from rclpy.executors import MultiThreadedExecutor
    from rclpy.node import Node
    from farm_interfaces.action import HarvestTask
    from farm_sim_devices.ros_adapter import SimRosAdapter
    from harvest_robot.arm_client import ArmActionClient, ArmActionSettings

    fixture = json.loads(args.fixture.read_text())
    fleet_path = prepare_run(ROOT)
    directory = fleet_path.parent
    fleet = json.loads(fleet_path.read_text())
    device_path = Path(fleet['device_configs'][0])
    device = json.loads(device_path.read_text())
    for camera in ('camera', 'tag_camera'):
        if camera in device:
            device[camera]['enabled'] = False
    device['runtime']['harvest_arm']['backend'] = args.policy
    if args.policy in ('student_d435', 'student_u20'):
        device['runtime']['harvest_arm']['execution_timeout_s'] = 1800.0
        student = json.loads((ROOT/'sim/ros_ws/src/farm_sim_config/config/student_policy.json').read_text())
        student['camera'] = args.policy.removeprefix('student_')
        student_path = directory/'student_policy.json'
        student_path.write_text(json.dumps(student, indent=2)+'\n')
        device['runtime']['harvest_arm']['student_profile'] = str(student_path)
    device_path.write_text(json.dumps(device, indent=2)+'\n')
    stations_path = Path(fleet['station_config'])
    stations = json.loads(stations_path.read_text())
    stations['stations'][fixture['robot_id']].update(xy_m=fixture['xy_m'], yaw_rad=fixture['yaw_rad'])
    stations_path.write_text(json.dumps(stations, indent=2)+'\n')
    command = [str(args.isaac_python), str(ROOT/'sim/ros_ws/src/farm_sim_runtime/farm_sim_runtime/run_fleet.py'),
        '--project-root', str(ROOT), '--fleet-config', str(fleet_path), '--headless',
        '--duration-s', '210', '--stop-after-arm-job', '--teacher-diagnostic-trace']
    if args.performance_log is not None:
        command += ['--performance-log', str(args.performance_log.resolve())]
    for module in ('sim/ros_ws/src/farm_sim_devices', 'sim/ros_ws/src/farm_sim_runtime',
                   'robot/ros_ws/src/farm_common', 'robot/ros_ws/src/farm_navigation'):
        command += ['--module-path', str(ROOT/module)]
    result = dict(scope='실제 내부 ROS Action/Teacher/국소 물리; Nav2 이동 미포함',
                  cancel_after_s=args.cancel_after_s,
                  fixture=fixture, command=command, states=[], received_packets=0, completed=False)
    latest = {}
    state_lock = threading.Lock()

    class RecordingAdapter(SimRosAdapter):
        """실제 publish를 수행하면서 검증용 수신 상태만 복사한다."""
        def publish_state(self, packet: dict) -> None:
            super().publish_state(packet)
            with state_lock:
                latest.clear(); latest.update(packet)
                result['received_packets'] += 1
                state = packet.get('arm')
                if state and (not result['states'] or any(state[k] != result['states'][-1][k]
                        for k in ('job_id','status','stage','event_seq'))):
                    row = dict(sim_time_s=packet['stamp_ns']/1e9, **state)
                    result['states'].append(row)
                    print(json.dumps(row), flush=True)

    namespace = '/teacher_action_check_'+str(os.getpid())
    rclpy.init(args=['--ros-args','-p','config_file:='+str(device_path), '-r','__ns:='+namespace])
    adapter, node = RecordingAdapter(), Node('teacher_action_client')
    settings = ArmActionSettings.from_mapping(json.loads((ROOT/'sim/ros_ws/src/farm_sim_config/config/harvest_task.json').read_text())['arm_action'])
    if args.policy in ('student_d435', 'student_u20'):
        from dataclasses import replace
        settings = replace(settings, execution_timeout_s=1860.0)
    client = ArmActionClient(node, settings)
    executor = MultiThreadedExecutor(num_threads=4)
    executor.add_node(adapter); executor.add_node(node)
    thread = threading.Thread(target=executor.spin, daemon=True); thread.start()
    feedback = []
    started = time.monotonic()
    canceled = False
    print('OUTPUT='+str(directory/'action_result.json'), flush=True)
    with (directory/'isaac.log').open('w') as log:
        process = subprocess.Popen(command, cwd=ROOT, env=launch_environment(args.isaac_python),
            stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        try:
            while not latest or latest.get('stamp_ns', 0) < 1_000_000_000:
                if process.poll() is not None or time.monotonic()-started > 150:
                    raise RuntimeError('Isaac 준비 실패')
                time.sleep(.05)
            goal = HarvestTask.Goal()
            goal.robot_id, goal.map_id = fixture['robot_id'], fixture['map_id']
            task = goal.harvest_task
            task.task_id, task.window_id = 'teacher60_ros_action', fixture['source']
            task.expected_count = len(fixture['expected_target_ids'])
            task.goal_pose.frame_id = 'map'
            task.goal_pose.position.x, task.goal_pose.position.y = fixture['xy_m']
            task.goal_pose.yaw = fixture['yaw_rad']
            begin_sim = latest['stamp_ns']/1e9
            class CancelRequested(Exception):
                pass
            def check() -> None:
                if process.poll() is not None:
                    raise RuntimeError('Action 결과 전 Isaac 종료')
                if args.cancel_after_s is not None and latest['stamp_ns']/1e9-begin_sim >= args.cancel_after_s:
                    raise CancelRequested()
            try:
                terminal = client.execute(goal, check, lambda a,b: feedback.append([a,b]))
            except CancelRequested:
                canceled = True
                terminal = client.cancel()
            result['ros_result'], result['ros_feedback'] = terminal, feedback
            result['completed'] = True
            process.wait(timeout=60)
        except Exception as error:
            result['exception'] = str(error)
            if client.has_goal:
                try:
                    result['cleanup_result'] = client.cancel()
                except Exception as cleanup:
                    result['cleanup_error'] = str(cleanup)
        finally:
            result['termination_method'] = 'process_exit'
            if process.poll() is None:
                result['termination_method'] = 'sigint'
                os.killpg(process.pid, signal.SIGINT)
                try:
                    process.wait(timeout=20)
                except subprocess.TimeoutExpired:
                    result['termination_method'] = 'sigkill'
                    os.killpg(process.pid, signal.SIGKILL); process.wait(timeout=5)
            adapter.arm_server.request_stop()
            executor.shutdown(); thread.join(timeout=5)
            client.close(); node.destroy_node(); adapter.close(); rclpy.shutdown()
    state = latest.get('arm', {})
    result.update(job_id=state.get('job_id',''), terminal=state,
        process_returncode=process.returncode, wall_elapsed_s=time.monotonic()-started)
    log_family = 'teacher' if args.policy == 'teacher' else 'student'
    logs = ROOT/f'sim/runs/robotarm/{log_family}'/latest.get('session','missing')/result['job_id']
    result['policy'] = args.policy
    result['teacher_log_dir'] = str(logs)
    result.update(evaluate_result(result, fixture, logs, require_harvest=not canceled,
                                  cancel_requested=canceled, place_hold_s=.6, expected_task_id='teacher60_ros_action'))
    checks = result['checks']
    ros = result.get('ros_result', {})
    checks['ros_terminal_matches_physics'] = (ros.get('result_code') == state.get('status')
        and ros.get('harvested_count') == state.get('success_count')
        and ros.get('failed_count') == state.get('failed_count'))
    checks['requested_action_outcome'] = state.get('status') == ('CANCELED' if canceled else 'SUCCESS')
    physics_path = ROOT/'sim/runs/robotarm/physics'/latest.get('session','missing')
    activity_file, summary_file = physics_path/'activity.jsonl', physics_path/'summary.json'
    rows = [json.loads(line) for line in activity_file.read_text().splitlines()] if activity_file.exists() else []
    summary = json.loads(summary_file.read_text()) if summary_file.exists() else {}
    result['physics_activity'] = rows
    result['physics_summary'] = summary
    counts = [row['active_fruit_count'] for row in rows]
    checks['idle_frozen_work_local'] = bool(counts) and counts[0] == 0 and 0 < max(counts) < 288
    checks['fixed_60hz'] = all(row['physics_hz'] == 60 for row in rows)
    result['passed'] = all(checks.values()) and not result.get('exception') and not result['verification_errors']
    (directory/'action_result.json').write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps(dict(passed=result['passed'],ros=ros,active_counts=counts),ensure_ascii=False),flush=True)
    return 0 if result['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
