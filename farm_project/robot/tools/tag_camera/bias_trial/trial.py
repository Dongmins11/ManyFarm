#!/usr/bin/env python3
"""태그 편향 비교 시험 준비·기록. goal 명령에서만 실제 이동을 요청한다."""
import argparse
from collections import Counter
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import tarfile
import time
import yaml

ROOT = Path(__file__).resolve().parents[4]
MARKER = Path('/tmp/harvest_bias_trial_path')


def run_folder() -> Path:
    """이 도구로 시작한 시험만 선택한다. 최신 폴더를 추측하지 않는다."""
    p = Path(MARKER.read_text().strip()).resolve()
    if not p.is_relative_to(ROOT/'runs/tag_bias_trial') or not p.is_dir():
        raise ValueError('시험 폴더 식별자 불일치')
    return p


def prepare(mode: str) -> Path:
    """현행 환경을 복사해 선택 옵션만 추가한다. 기존 설정은 쓰지 않는다."""
    root = ROOT
    env = yaml.safe_load((root/'robot/config/environments/harvest_real.yaml').read_text())
    cfg = yaml.safe_load((root/env['tag_localization_config']).read_text())
    if cfg.get('correction_transport') != 'scan_sync':
        raise ValueError('이번 비교는 기존 scan_sync 연결이 필요합니다.')
    if env['robot_id'] != 'harvest_01' or env['mode'] != 'real':
        raise ValueError('수확 실물 환경만 지원합니다.')
    cfg.pop('pixel_bias_profile', None)
    if mode == 'on':
        cfg['pixel_bias_profile'] = 'robot/config/localization/bias_trial_20261010/profile.json'
    from farm_tag_localization.pixel_bias import load_profile
    profile = load_profile(cfg, root)
    folder = root/'runs/tag_bias_trial'/(datetime.now().strftime('%Y%m%d_%H%M%S_%f')+'_'+mode)
    folder.mkdir(parents=True)
    (folder/'localization.yaml').write_text(yaml.safe_dump(cfg, sort_keys=False))
    env['tag_localization_config'] = str(folder/'localization.yaml')
    (folder/'environment.yaml').write_text(yaml.safe_dump(env, sort_keys=False))
    manifest = dict(mode=mode, model=profile, created_at=datetime.now().isoformat(), files={})
    paths = ['robot/config/environments/harvest_real.yaml', 'robot/config/robots/vicpinky/nav2.yaml',
        'robot/ros_ws/src/farm_tag_localization/farm_tag_localization/node.py',
        'robot/ros_ws/src/farm_tag_localization/farm_tag_localization/pixel_bias.py',
        cfg['assets_file'], cfg['model_file'], env['route_graph'], env['nav_params'], env['harvest_config']]
    for rel in set(paths):
        p = root/rel
        manifest['files'][rel] = hashlib.sha256(p.read_bytes()).hexdigest()
        dest = folder/'inputs'/rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(p.read_bytes())
    (folder/'manifest.json').write_text(json.dumps(manifest, indent=2))
    MARKER.write_text(str(folder)+'\n')
    return folder


def ready() -> None:
    """Goal 전 기존 서비스·TF·프로토콜만 확인한다. 주행 중 감시/취소 조건을 추가하지 않는다."""
    import rclpy
    from lifecycle_msgs.srv import GetState
    from rcl_interfaces.srv import GetParameters
    from rclpy.time import Time
    from tf2_ros import Buffer, TransformListener
    rclpy.init()
    node = rclpy.create_node('tag_bias_trial_ready', cli_args=['--ros-args',
        '-r', '/tf:=/harvest_01/tf', '-r', '/tf_static:=/harvest_01/tf_static'])
    try:
        for name in ('amcl', 'controller_server', 'planner_server', 'bt_navigator', 'velocity_smoother'):
            client = node.create_client(GetState, '/harvest_01/'+name+'/get_state')
            if not client.wait_for_service(timeout_sec=10.): raise RuntimeError(name+' 서비스 없음')
            future = client.call_async(GetState.Request())
            rclpy.spin_until_future_complete(node, future, timeout_sec=10.)
            if not future.done() or future.result().current_state.id != 3:
                raise RuntimeError(name+'가 active가 아닙니다. 초기 위치/실행 로그를 확인하세요.')
        client = node.create_client(GetParameters, '/harvest_01/amcl/get_parameters')
        if not client.wait_for_service(timeout_sec=5.): raise RuntimeError('AMCL 파라미터 서비스 없음')
        future = client.call_async(GetParameters.Request(names=['tag_correction_protocol']))
        rclpy.spin_until_future_complete(node, future, timeout_sec=5.)
        if not future.done() or future.result().values[0].string_value != 'scan_sync_v1':
            raise RuntimeError('scan_sync_v1이 아닙니다.')
        buffer = Buffer(); listener = TransformListener(buffer, node)
        deadline = time.monotonic()+10
        while time.monotonic() < deadline:
            rclpy.spin_once(node, timeout_sec=.1)
            if all(buffer.can_transform(a, b, Time()) for a, b in [('map', 'base_footprint'), ('odom', 'base_footprint')]):
                transform = buffer.lookup_transform('odom', 'base_footprint', Time())
                stamp = transform.header.stamp
                age = (node.get_clock().now().nanoseconds-stamp.sec*10**9-stamp.nanosec)/1e9
                if 0 <= age < .5:
                    print('준비 확인: Nav2 active / scan_sync_v1 / 현재 odom·map TF', flush=True)
                    return
        raise RuntimeError('현재 odom/map TF가 없습니다. 모터 전원과 2D Pose를 확인하세요.')
    finally:
        node.destroy_node(); rclpy.shutdown()


def session(folder: Path) -> Path:
    """해당 launch가 출력한 세션만 반환한다."""
    matches = re.findall(r'TAG_SESSION:\s+(\S+)', (folder/'launch.log').read_text(errors='replace'))
    if not matches: raise RuntimeError('이 시험의 TAG_SESSION을 찾지 못했습니다.')
    path = Path(matches[-1]).resolve()
    if not path.is_relative_to(ROOT/'runs/harvest_tag') or not path.is_dir():
        raise RuntimeError('세션 경로 불일치')
    return path


def goal() -> None:
    """기록을 시작한 뒤 기존 생성기로 14번 Goal을 전송한다."""
    folder = run_folder()
    ready()
    capture = session(folder)
    starts = []
    for path in capture.glob('*/amcl_tag_*/events.jsonl'):
        for line in path.read_text().splitlines():
            try: row = json.loads(line)
            except ValueError: continue
            if row.get('kind') == 'start': starts.append(row)
    expected = json.loads((folder/'manifest.json').read_text())['model']
    model_id = expected['model_id'] if expected else 'OFF'
    if len(starts) != 1 or starts[0].get('pixel_bias_model') != model_id:
        raise RuntimeError('어댑터에 선택한 보상 모델이 적용되지 않았습니다. Goal 미전송.')
    if (folder/'bag').exists(): raise RuntimeError('한 시험 폴더에 한 번만 주행합니다. 덮어쓰지 않습니다.')
    topics = ['/harvest_01/'+x for x in ('tf', 'tf_static', 'odom', 'scan_filtered', 'amcl_pose',
        'cmd_vel', 'cmd_vel_nav', 'received_global_plan', 'task_events',
        'tag_localization/control', 'tag_localization/correction', 'tag_localization/events')]+['/rosout']
    with (folder/'bag.log').open('w') as log:
        recorder = subprocess.Popen(['ros2', 'bag', 'record', '-s', 'mcap', '-o', str(folder/'bag'), *topics],
            stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        try:
            time.sleep(3.)
            if recorder.poll() is not None: raise RuntimeError('rosbag 기록 시작 실패. bag.log 확인')
            data = subprocess.check_output([sys.executable, str(ROOT/'robot/tools/tag_camera/harvest_graph_goal.py'),
                '--node', '14', '--heading-from', '13', '--section', 'SEC_01'], text=True)
            (folder/'goal.json').write_text(data)
            print('실제 이동 시작: 14번 / 보상 모델 '+model_id, flush=True)
            with (folder/'goal.log').open('w') as output:
                proc = subprocess.Popen(['ros2', 'action', 'send_goal', '/harvest_01/harvest_task',
                    'farm_interfaces/action/HarvestTask', data, '--feedback'], stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT, text=True)
                for line in proc.stdout:
                    print(line, end='', flush=True); output.write(line); output.flush()
                code = proc.wait()
                if code: raise RuntimeError('Goal CLI 종료 코드 '+str(code))
            time.sleep(2.)
        finally:
            if recorder.poll() is None:
                os.killpg(recorder.pid, signal.SIGINT)
                try: recorder.wait(timeout=20)
                except subprocess.TimeoutExpired:
                    os.killpg(recorder.pid, signal.SIGTERM); recorder.wait(timeout=10)
    print('주행 기록:', folder, flush=True)


def collect() -> None:
    """PC로 가져갈 단일 압축 파일과 적용 수 요약을 만든다."""
    folder = run_folder(); capture = session(folder); counts = Counter(); audits = []
    for path in capture.glob('*/amcl_tag_*/events.jsonl'):
        for line in path.read_text().splitlines():
            try: row = json.loads(line)
            except ValueError: continue
            counts[row.get('kind')] += 1
            if row.get('kind') == 'tag_correction_requested': audits.append(row.get('pixel_bias', {}))
    summary = dict(events=dict(counts), bias_requests=audits,
        note='적용 수는 물리적 정확도를 의미하지 않습니다. 라이다·실측 간격과 비교합니다.')
    (folder/'summary.json').write_text(json.dumps(summary, indent=2, ensure_ascii=False))
    destination = Path('/tmp/harvest_tag_bias_latest.tar.gz')
    with tarfile.open(destination, 'w:gz') as archive:
        for path in (folder, capture): archive.add(path, arcname=str(path.relative_to(ROOT)))
    print(json.dumps(dict(counts), indent=2)); print('PC로 복사할 파일:', destination)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['prepare', 'ready', 'goal', 'collect'])
    parser.add_argument('--mode', choices=['on', 'off'], default='on')
    args = parser.parse_args()
    if args.command == 'prepare': print(prepare(args.mode))
    elif args.command == 'ready': ready()
    elif args.command == 'goal': goal()
    else: collect()


if __name__ == '__main__': main()
