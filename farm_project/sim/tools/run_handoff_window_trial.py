"""기존 SEC01 예찰 윈도우에서 실제 수확→관제 인계 진입을 시험한다.

초기 배치만 윈도우 앞에 두며 실행 중 위치/수확 결과를 주입하지 않는다.
기본은 DOCK_READY 이후 취소·정지, --pickup은 실제 인계·복원까지 검사한다.
"""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import signal
import subprocess
import time
import yaml

from prepare_harvest_handoff import ROOT, CONFIG, prepare


def prepare_trial(base: Path, scout_result: Path, *, servo_ki: float | None = None) -> Path:
    """성공 예찰 결과의 첫 윈도우와 원본 설정을 보존한 실행 복사본을 만든다."""
    source = json.loads(scout_result.read_text())['scout_result']
    data = source['result']
    if source['status'] != 4 or data['result_code'] != 'SUCCESS' or data['section_id'] != 'SEC01':
        raise ValueError('SEC01 성공 예찰 결과 필요')
    task = data['harvest_tasks'][0]
    if data['harvest_task_count'] != len(data['harvest_tasks']) or task['goal_pose']['frame_id'] != 'map':
        raise ValueError('예찰 결과 형식 불일치')
    base.mkdir(parents=True, exist_ok=False)
    runtime = base/'runtime'
    prepare(runtime)
    device = json.loads((runtime/'harvest.json').read_text())
    device['runtime']['diagnostic_period_s'] = .05
    servo_before = dict(device['base']['wheel_velocity_servo'])
    if servo_ki is not None:
        if not math.isfinite(servo_ki) or servo_ki <= 0:
            raise ValueError('시뮬 바퀴 적분 계수는 양의 유한한 값 필요')
        device['base']['wheel_velocity_servo']['ki'] = servo_ki
    (runtime/'harvest.json').write_text(json.dumps(device,ensure_ascii=False,indent=2)+'\n')
    pose = task['goal_pose']; yaw = pose['yaw']
    xy = [pose['position'][axis]-.15*component
          for axis, component in zip(('x', 'y'), (math.cos(yaw), math.sin(yaw)))]
    stations = json.loads((CONFIG/'station_spawn.json').read_text())
    stations['stations']['harvest_01'].update(xy_m=xy, yaw_rad=yaw)
    def write(path: Path, value: dict) -> None:
        path.write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n')
    write(runtime/'stations.json', stations)
    fleet = json.loads((runtime/'fleet.json').read_text())
    fleet['station_config'] = str((runtime/'stations.json').relative_to(ROOT))
    fleet['device_configs'] = [p for p in fleet['device_configs'] if not p.endswith('/scout_fleet.json')]
    write(runtime/'fleet.json', fleet)
    nav = yaml.safe_load((CONFIG/'nav2_harvest.yaml').read_text())
    nav['bindings']['initial_pose'] = dict(x=xy[0], y=xy[1], z=0., yaw=yaw)
    (runtime/'nav2_harvest.yaml').write_text(yaml.safe_dump(nav, sort_keys=False))
    profile = yaml.safe_load((runtime/'harvest_runtime.yaml').read_text())
    profile['nav_params'] = str((runtime/'nav2_harvest.yaml').relative_to(ROOT))
    (runtime/'harvest_runtime.yaml').write_text(yaml.safe_dump(profile, sort_keys=False))
    write(base/'window.json', task)
    write(base/'fixture.json', dict(
        scope='real HarvestTask + Frontend handoff worker + body entry; cancel after DOCK_READY',
        cached_scout_source=str(scout_result.relative_to(ROOT)),
        cached_scout_sha256=hashlib.sha256(scout_result.read_bytes()).hexdigest(),
        harvest_initial_xy=xy, harvest_initial_yaw=yaw,
        initial_pose_only=True, truth_injected_into_control=False,
        fresh_scout=False, full_section=False, traffic_enabled=False,
        domain=13, discovery='SUBNET', physics='cpu',
        localization=dict(tag_correction=True, amcl_package='farm_tag_amcl'),
        numeric_handoff_changes=json.loads((runtime/'source_adaptations.json').read_text())['numeric_handoff_changes'],
        sim_wheel_servo_before=servo_before, sim_wheel_servo_selected=device['base']['wheel_velocity_servo']))
    return runtime


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    parser.add_argument('--scout-result', type=Path, required=True)
    parser.add_argument('--servo-ki', type=float, help='시뮬 바퀴 적분 계수 비교용. 실물/공통 제어값은 불변')
    parser.add_argument('--pickup', action='store_true', help='실제 운송 인계와 차체 복원까지 검증')
    parser.add_argument('--post-handoff', action='store_true', help='인계 뒤 선별장 정밀주행·양쪽 스테이션 복귀 분리 검증')
    args = parser.parse_args(); base = args.output.resolve()
    if args.post_handoff and not args.pickup:parser.error('--post-handoff는 --pickup 필요')
    if not base.is_relative_to(ROOT/'sim/runs'):
        raise ValueError('sim/runs 아래 새 경로 필요')
    if os.environ.get('ROS_DOMAIN_ID') != '13' or os.environ.get('ROS_AUTOMATIC_DISCOVERY_RANGE') != 'SUBNET':
        raise ValueError('ROS Domain13/SUBNET 필요')
    runtime = prepare_trial(base, args.scout_result.resolve(), servo_ki=args.servo_ki)
    if args.pickup:
        from prepare_pickup_trial import prepare_pickup
        prepare_pickup(runtime, json.loads((base/'window.json').read_text()))
        fixture = json.loads((base/'fixture.json').read_text())
        fixture['scope'] = 'one actual window + Frontend worker + TransportPickup/DockTransfer through restore'
        fixture['temporary_marker_layout'] = str((runtime/'layout.json').relative_to(ROOT))
        (base/'fixture.json').write_text(json.dumps(fixture,ensure_ascii=False,indent=2)+'\n')
    if args.post_handoff:
        (base/'post_handoff.json').write_text(json.dumps(dict(enabled=True,
            sorter_internal_action_trial=True,unload_tested=False))+'\n')
    os.environ['HANDOFF_INPUT_TRACE'] = str(base/'input_trace')
    os.environ['ROS_LOG_DIR'] = str(base/'ros_logs')
    processes = []; streams = []
    def start(name: str, command: list[str]) -> subprocess.Popen:
        stream = (base/(name+'.log')).open('w'); streams.append(stream)
        process = subprocess.Popen(command, cwd=ROOT, stdout=stream,
                                   stderr=subprocess.STDOUT, start_new_session=True)
        processes.append((name, process)); return process
    try:
        start('harvest', ['ros2','launch','farm_sim_runtime','harvest.launch.py','mode:=sim',
            'project_root:='+str(ROOT),'environment_config:='+str(runtime/'harvest_runtime.yaml'),
            'initial_spawn_config:='+str(runtime/'stations.json'),
            'handoff_config:='+str(runtime/'handoff.json'),'tag_correction:=true'])
        start('transport_adapter', ['ros2','run','farm_sim_devices','ros_adapter','--ros-args',
            '-r','__ns:=/transport_01','-p','use_sim_time:=true',
            '-p','config_file:='+str((runtime if args.pickup else CONFIG)/'transport.json')])
        if args.pickup:
            os.environ['MOTION_GATE_TRACE'] = str(base/'gate_timing.jsonl')
            start('gate', ['/usr/bin/python3','sim/tools/trace_motion_gate.py','--ros-args',
                '-r','__ns:=/transport_01','-p','use_sim_time:=true'])
            os.environ['DOCKING_FRESHNESS_TRACE'] = str(base/'freshness_trace.jsonl')
            start('precision', ['/usr/bin/python3','sim/tools/trace_docking_freshness.py',
                '--ros-args','--params-file',str(runtime/'precision.yaml'),
                '-r','__ns:=/transport_01','-r','/cmd_vel:=motion/precision','-r','/odom:=odom',
                '-r','/dock/cmd:=precision_legacy_disabled','-r','/dock/state:=precision_legacy_state'])
            start('transport', ['ros2','launch','farm_sim_runtime','transport_navigation.launch.py',
                'project_root:='+str(ROOT),'environment_config:='+str(runtime/'transport_runtime.json'),
                'journal_dir:='+str(base/'transport_journal')])
        start('isaac', ['ros2','launch','farm_sim_runtime','isaac.launch.py','project_root:='+str(ROOT),
            'fleet_config:='+str(runtime/'fleet.json'),'headless:=true','physics_device:=cpu',
            'performance_log:='+str(base/'frame_performance.jsonl'),
            'duration_s:='+('2400' if args.post_handoff else '1200'),'isaac_python:=/home/ysy/isaac/env_isaaclab/bin/python'])
        probe = start('probe', ['/usr/bin/python3','sim/tools/probe_handoff_window.py',str(base)])
        deadline = time.monotonic()+(4000 if args.post_handoff else 2000)
        while probe.poll() is None:
            failed = [(n,p.returncode) for n,p in processes if n != 'probe' and p.poll() is not None]
            if failed: raise RuntimeError('시험 프로세스 종료: '+str(failed))
            if time.monotonic() >= deadline: raise TimeoutError('시험 watchdog (제품 제한시간과 별도)')
            time.sleep(1)
        if probe.returncode: raise RuntimeError('시험 실패; result.json 및 원시 로그 확인')
    finally:
        for _, process in reversed(processes):
            if process.poll() is None: os.killpg(process.pid, signal.SIGINT)
        deadline = time.monotonic()+45
        while any(p.poll() is None for _,p in processes) and time.monotonic()<deadline: time.sleep(.5)
        for _, process in processes:
            if process.poll() is None: os.killpg(process.pid, signal.SIGKILL); process.wait()
        (base/'process_exit.json').write_text(json.dumps({n:p.poll() for n,p in processes},indent=2)+'\n')
        for stream in streams: stream.close()


if __name__ == '__main__': main()
