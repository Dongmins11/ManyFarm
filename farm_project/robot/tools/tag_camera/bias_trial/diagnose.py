#!/usr/bin/env python3
"""실물 TF 장애 수집. 주행·재시작·파라미터 변경 없이 로봇에서 실행한다."""
import argparse
from collections import Counter
from datetime import datetime
import hashlib
import json
import os
import signal
import fcntl
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import time

ROOT = Path.home() / 'vmany/main/farm_project'
NAMES = ('sllidar', 'scan_to_scan', 'bringup', 'amcl', 'map_server',
         'controller_server', 'planner_server', 'lifecycle_manager', 'harvest_node',
         'camera', 'capture', 'apriltag', 'rectify', 'detector', 'monitor', 'ros2')


def read(path: Path) -> str:
    try:
        return path.read_text(errors='replace')
    except OSError as exc:
        return str(exc)


def command(args: list[str]) -> dict:
    try:
        result = subprocess.run(args, capture_output=True, text=True, timeout=2)
        return {'argv': args, 'code': result.returncode, 'out': result.stdout, 'err': result.stderr}
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {'argv': args, 'error': str(exc)}


def system_sample(threads: bool, proc_root: Path = Path('/proc')) -> dict:
    item = {'wall_ns': time.time_ns(), 'monotonic_ns': time.monotonic_ns()}
    for name in ('stat', 'meminfo', 'loadavg', 'net/dev', 'net/wireless',
                 'pressure/cpu', 'pressure/memory', 'pressure/io'):
        item[name] = read(proc_root / name)
    item['processes'] = []
    for proc in proc_root.glob('[0-9]*'):
        # 부하 원인을 빠뜨리지 않도록 모든 프로세스의 가벼운 카운터를 기록한다.
        record = {'pid': proc.name, 'comm': read(proc/'comm').strip(), 'stat': read(proc/'stat')}
        if threads:
            argv = read(proc/'cmdline').split('\0')
            if any(name in ' '.join(argv[:2]) for name in NAMES):
                record['cmd'] = ' '.join(argv)
                record['argv'] = argv
                record['io'] = read(proc/'io')
                record['thread_waits'] = dict(Counter(read(t/'wchan').strip()
                                                      for t in (proc/'task').glob('*')))
                allowed = ('ROS_DOMAIN_ID=', 'RMW_IMPLEMENTATION=', 'ROS_AUTOMATIC_DISCOVERY_RANGE=',
                           'RMW_FASTRTPS_PUBLICATION_MODE=', 'FASTRTPS_DEFAULT_PROFILES_FILE=',
                           'FASTDDS_DEFAULT_PROFILES_FILE=', 'ROS_LOCALHOST_ONLY=')
                record['ros_env'] = [x for x in read(proc/'environ').split('\0') if x.startswith(allowed)]
        item['processes'].append(record)
    return item


def collect_active_files(folder: Path, sample: dict, root: Path = ROOT) -> list[dict]:
    """현재 PID 인자에 연결된 설정과 로그를 저장한다. 최신 marker를 실행본으로 오인하지 않는다."""
    records = []
    for proc in sample['processes']:
        argv = proc.get('argv', [])
        paths = set()
        for index, arg in enumerate(argv):
            if arg.startswith('environment_config:='):
                config = Path(arg.split(':=', 1)[1])
                paths.update([config, config.parent/'launch.log'])
            elif arg.startswith(('config_file:=', 'capture_directory:=')):
                path = Path(arg.split(':=', 1)[1])
                if path.is_dir():
                    paths.update(path/n for n in ('settings.json', 'status.json', 'camera_io_status.json', 'process_exits.json'))
                    paths.update(path.parent/n for n in ('capture.log', 'correction.log', 'session.json'))
                else:
                    paths.add(path)
            elif arg == '--params-file' and index+1 < len(argv):
                paths.add(Path(argv[index+1]))
        for src in sorted(paths):
            resolved = src.resolve()
            if not (resolved.is_relative_to(root.resolve()) or resolved.is_relative_to(Path('/tmp'))):
                continue
            record = {'pid': proc['pid'], 'source': str(src)}
            try:
                limit = 512_000 if src.suffix == '.log' else 128_000
                size = src.stat().st_size
                if not src.is_file():
                    continue
                with src.open('rb') as inp:
                    inp.seek(max(0, size-limit))
                    data = inp.read(limit)
                name = hashlib.sha256(str(src).encode()).hexdigest()[:12]+'_'+src.name
                dst = folder/'active_files'/proc['pid']/name
                dst.parent.mkdir(parents=True, exist_ok=True)
                dst.write_bytes(data)
                record.update(saved=str(dst.relative_to(folder)), tail_only=size>limit)
            except OSError as exc:
                record['error'] = str(exc)
            records.append(record)
    return records


def finish_worker(worker: subprocess.Popen, grace: float = 2.0) -> dict:
    """이번 수집기가 만든 자식만 종료한다. ROS 종료 지연을 별도로 표시한다."""
    result = {'forced': False}
    try:
        worker.wait(timeout=grace)
    except subprocess.TimeoutExpired:
        result['forced'] = True
        worker.terminate()
        try:
            worker.wait(timeout=grace)
        except subprocess.TimeoutExpired:
            worker.kill()
            try:
                worker.wait(timeout=grace)
            except subprocess.TimeoutExpired:
                result['unreaped'] = True
    result['exit_code'] = worker.poll()
    return result


def ros_worker(folder: Path, seconds: int) -> None:
    import rclpy
    from rclpy.qos import QoSProfile, ReliabilityPolicy, DurabilityPolicy
    from sensor_msgs.msg import LaserScan
    from nav_msgs.msg import Odometry
    from tf2_msgs.msg import TFMessage
    def stage(name: str) -> None:
        (folder/'ros_stage.json').write_text(json.dumps({'stage': name, 'wall_ns': time.time_ns()}))
    stage('init')
    rclpy.init()
    node = rclpy.create_node('harvest_tf_diagnosis_' + str(os.getpid()), enable_rosout=False)
    # best effort는 수집기가 reliable ACK 대기를 추가하지 않도록 한다.
    qos = QoSProfile(depth=5, reliability=ReliabilityPolicy.BEST_EFFORT,
                     durability=DurabilityPolicy.VOLATILE)
    topics = {'/scan': LaserScan, '/scan_filtered': LaserScan,
              '/harvest_01/scan': LaserScan, '/harvest_01/scan_filtered': LaserScan,
              '/harvest_01/odom': Odometry, '/harvest_01/tf': TFMessage}
    stage('subscribe')
    subs, batch = [], {}
    last_seen = {}
    def observe(msg, topic: str) -> None:
        wall, mono = time.time(), time.monotonic()
        entries = [(topic + ' ' + t.header.frame_id + ' -> ' + t.child_frame_id, t.header)
                   for t in msg.transforms] if hasattr(msg, 'transforms') else [(topic, msg.header)]
        for key, header in entries:
            stamp = header.stamp.sec + header.stamp.nanosec / 1e9
            rec = batch.setdefault(key, {'count': 0, 'max_gap_s': 0., 'max_age_s': -1e30})
            rec['count'] += 1
            rec['max_gap_s'] = max(rec['max_gap_s'], mono-last_seen.get(key, mono))
            rec['max_age_s'] = max(rec['max_age_s'], wall-stamp)
            rec['last_stamp'] = stamp
            last_seen[key] = mono
    for topic, kind in topics.items():
        subs.append(node.create_subscription(kind, topic, lambda m, t=topic: observe(m, t), qos))
    stage('receive')
    started, report = time.monotonic(), time.monotonic()
    graph_done = False
    with (folder/'topics.jsonl').open('w') as out:
        while time.monotonic()-started < seconds:
            rclpy.spin_once(node, timeout_sec=.1)
            now = time.monotonic()
            if now-report >= 1:
                out.write(json.dumps({'wall_ns': time.time_ns(), 'topics': batch,
                    'silence_s': {k: now-v for k,v in last_seen.items()}})+'\n')
                out.flush()
                batch, report = {}, now
            if not graph_done and now-started >= 5:
                stage('graph')
                graph = {'nodes': node.get_node_names_and_namespaces(), 'topics': {}}
                for topic in topics:
                    graph['topics'][topic] = [
                        {'node': ep.node_name, 'namespace': ep.node_namespace,
                         'qos': str(ep.qos_profile)} for ep in node.get_publishers_info_by_topic(topic)]
                (folder/'ros_graph.json').write_text(json.dumps(graph, indent=2))
                graph_done = True
                stage('receive')
    stage('destroy_node')
    node.destroy_node()
    stage('shutdown')
    rclpy.shutdown()
    stage('done')


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--seconds', type=int, default=30)
    parser.add_argument('--ros', action='store_true', help='명시한 경우에만 ROS 구독 프로세스 추가')
    parser.add_argument('--ros-worker', type=Path)
    args = parser.parse_args()
    if not 1 <= args.seconds <= 300:
        parser.error('--seconds는 1~300초')
    if args.ros_worker:
        ros_worker(args.ros_worker, args.seconds)
        return
    lockdir = Path.home()/'.cache/manyfarm'
    lockdir.mkdir(parents=True, exist_ok=True)
    lock = (lockdir/'diagnose.lock').open('a')
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        raise SystemExit('이미 진단 수집 중입니다. 중복 수집하지 않습니다.')
    folder = Path('/tmp') / ('harvest_tf_diagnosis_' + datetime.now().strftime('%Y%m%d_%H%M%S') + '_' + str(os.getpid()))
    folder.mkdir()
    interrupted = False
    def stop(signum: int, frame: object) -> None:
        nonlocal interrupted
        interrupted = True
    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)
    print(f'{args.seconds}초 수집 / ROS 구독 {"ON" if args.ros else "OFF"} / 저장: {folder}', flush=True)
    worker = None
    worker_result = {'enabled': args.ros}
    log = (folder/'ros_worker.log').open('w')
    if args.ros:
        shell = '''source /opt/ros/jazzy/setup.bash || exit
source "$HOME/vicpinky_ws/install/setup.bash" || exit
if [ -f "$HOME/vmany/main/farm_project/robot/ros_ws/install/setup.bash" ]; then
  source "$HOME/vmany/main/farm_project/robot/ros_ws/install/setup.bash"
fi
export ROS_DOMAIN_ID=77 ROS_AUTOMATIC_DISCOVERY_RANGE=SUBNET RMW_IMPLEMENTATION=rmw_fastrtps_cpp
unset ROS_LOCALHOST_ONLY ROS_DISCOVERY_SERVER ROS_STATIC_PEERS
exec /usr/bin/python3 "$1" --ros-worker "$2" --seconds "$3"
'''
        worker = subprocess.Popen(['bash', '-c', shell, 'diagnose', str(Path(__file__).resolve()),
                                   str(folder), str(args.seconds)], stdout=log, stderr=subprocess.STDOUT)
    started = time.monotonic()
    deadline = started + args.seconds
    index = 0
    active = []
    with (folder/'system.jsonl').open('w') as out:
        while not interrupted and time.monotonic() < deadline:
            before = time.monotonic()
            sample = system_sample(index % 10 == 0)
            out.write(json.dumps(sample)+'\n')
            out.flush()
            if index % 10 == 0:
                active.extend(collect_active_files(folder, sample))
                print(f'수집 {time.monotonic()-started:.0f}/{args.seconds}초, 프로세스 {len(sample["processes"])}개', flush=True)
            index += 1
            time.sleep(max(0, min(1-(time.monotonic()-before), deadline-time.monotonic())))
    if worker is not None:
        worker_result.update(finish_worker(worker))
    log.close()
    print('수집 종료, 설정·로그를 정리합니다.', flush=True)
    commands = [['ip', '-s', 'link'], ['ip', 'route'], ['df', '-h', '/tmp'],
                ['journalctl', '-k', '--since', '-20min', '--no-pager', '-n', '150'],
                ['timedatectl', 'show', '-p', 'NTPSynchronized'],
                ['vcgencmd', 'get_throttled'], ['vcgencmd', 'measure_temp']]
    (folder/'system_commands.json').write_text(json.dumps([command(c) for c in commands], indent=2))
    # 현재 설정은 실행 당시 설정과 분리한다.
    config = ROOT/'robot/config/environments/harvest_real.yaml'
    if config.is_file():
        (folder/'current_environment.yaml').write_bytes(config.read_bytes())
    (folder/'active_files.json').write_text(json.dumps(active, indent=2))
    (folder/'manifest.json').write_text(json.dumps({'version': 2, 'interrupted': interrupted,
        'samples': index, 'clock_ticks': os.sysconf('SC_CLK_TCK'), 'ros_worker': worker_result,
        'domain_requested': 77 if args.ros else None,
        'note': 'PID별 active_files가 실행본이다. current_environment는 현재 디스크 설정이다.'}, indent=2))
    archive = Path(str(folder)+'.tar.gz')
    with tarfile.open(archive, 'w:gz', compresslevel=1) as tar:
        tar.add(folder, arcname=folder.name)
    latest = Path('/tmp/harvest_tf_diagnosis_latest.tar.gz')
    temporary = latest.with_suffix('.tmp')
    shutil.copy2(archive, temporary)
    temporary.replace(latest)
    print(f'수집 완료: {latest}\nROS 수집: {worker_result}', flush=True)


if __name__ == '__main__':
    main()
