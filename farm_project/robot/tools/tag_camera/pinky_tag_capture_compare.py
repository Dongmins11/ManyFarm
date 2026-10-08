#!/usr/bin/env python3
"""PCWEB400 / seven-tag connection capture. No navigation or correction commands.

Run on Vic Pinky after sourcing /opt/ros/jazzy/setup.bash. Uses the bundled
camera driver/calibration. This process and its children alone use
Domain 178 + loopback-only Cyclone DDS; the running fleet stays on 156.
Restores the 2026-09-28 receive-buffer setup. Stops camera first on Ctrl+C.
Records full published raw frames during the PC-owned recording window, plus detector metadata. No full-rate 30FPS recording.
Camera source stamps mean cap.read completion, NOT measured exposure times.
"""
import argparse
from collections import OrderedDict
from datetime import datetime
import fcntl
import hashlib
import json
import math
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time

IDS = tuple(range(100, 107))
WIDTH, HEIGHT = 1280, 720
DOMAIN = 178
BUFFER_MIN = 10 * 1024 * 1024
CYCLONE_XML = ('<CycloneDDS><Domain Id="178"><General><Interfaces>'
    '<NetworkInterface name="lo" multicast="false"/></Interfaces>'
    '<AllowMulticast>false</AllowMulticast></General><Discovery>'
    '<ParticipantIndex>auto</ParticipantIndex><Peers>'
    '<Peer Address="127.0.0.1"/></Peers></Discovery>'
    '<Internal><SocketReceiveBufferSize min="10MiB"/></Internal>'
    '</Domain></CycloneDDS>')
PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_CALIBRATION = PROJECT_ROOT / 'robot/config/cameras/pcweb400_720p_report.json'


def roi_bounds(fraction):
    # Use integer pixel boundaries to avoid floating-point edge ambiguity.
    x, y = round(WIDTH * (1 - fraction) / 2), round(HEIGHT * (1 - fraction) / 2)
    return x, y, WIDTH - x, HEIGHT - y


def inside(corners, fraction):
    if len(corners) != 4 or any(len(p) != 2 for p in corners):
        return False
    if not all(math.isfinite(v) for p in corners for v in p):
        return False
    x0, y0, x1, y1 = roi_bounds(fraction)
    return all(x0 <= x <= x1 and y0 <= y <= y1 for x, y in corners)


def stamp_key(header):
    return (int(header.stamp.sec) * 1_000_000_000 + int(header.stamp.nanosec), header.frame_id)


def detection_record(d):
    corners = [[float(p.x), float(p.y)] for p in d.corners]
    if type(d.id) is not int or not isinstance(d.family, str):
        raise ValueError('Unsupported AprilTag message type')
    if len(corners) != 4 or not all(math.isfinite(v) for p in corners for v in p):
        raise ValueError('Invalid detector corners; not recording them as valid')
    family = d.family if d.family.startswith('tag') else 'tag' + d.family
    target = family == 'tag36h11' and d.id in IDS
    margin = float(d.decision_margin)
    return dict(id=d.id, family=family, installed=target, hamming=int(d.hamming),
                decision_margin=margin if math.isfinite(margin) else None,
                corners_rectified=corners,
                roi={str(round(f*100)): inside(corners, f) for f in (.4, .6, .8)},
                roi60_candidate=bool(target and d.hamming == 0 and inside(corners, .6)))


def atomic_json(path, data):
    temp = path.with_name(path.name + '.tmp')
    temp.write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + '\n')
    os.replace(temp, path)


def supervise(commands, output, environment, *, stop_requested=None,
              grace_s=4.0, settle_s=1.0):
    """Own only these children; preserve explicit signal crashes, including -11."""
    stopping = [False]
    received_signal = [None]
    owned, records = {}, {}
    unexpected = []
    failure = None
    old_handlers = {}

    def request_stop(signum, _frame):
        stopping[0] = True
        received_signal[0] = signum

    def terminate(name):
        proc = owned.get(name)
        if proc is None:
            return
        sent = []
        if proc.poll() is None:
            print('STOPPING: ' + name, flush=True)
            for sig, seconds in ((signal.SIGINT, max(grace_s,25.) if name == 'camera' else grace_s),
                                 (signal.SIGTERM, 2.0), (signal.SIGKILL, 2.0)):
                if proc.poll() is not None:
                    break
                try:
                    os.killpg(proc.pid, sig)
                    sent.append(sig.name)
                except ProcessLookupError:
                    break
                try:
                    proc.wait(timeout=seconds)
                    break
                except subprocess.TimeoutExpired:
                    pass
        rc = proc.poll()
        records[name] = dict(pid=proc.pid, returncode=rc, signals_sent=sent)
        print('EXIT: ' + name + ' code=' + str(rc), flush=True)

    try:
        for sig in (signal.SIGINT, signal.SIGTERM):
            old_handlers[sig] = signal.signal(sig, request_stop)
        for name in ('monitor', 'rectify', 'detector', 'camera'):
            if stopping[0]:
                break
            owned[name] = subprocess.Popen(commands[name], env=environment,
                                          start_new_session=True)
            print('STARTED: ' + name + ' pid=' + str(owned[name].pid), flush=True)
        while not stopping[0]:
            if stop_requested is not None and stop_requested():
                stopping[0] = True
                break
            exited = [name for name, proc in owned.items() if proc.poll() is not None]
            if exited:
                unexpected.extend(exited)
                break
            time.sleep(.1)
    except Exception as exc:
        failure = str(exc)
    finally:
        # Fresh image input ends before the C++ image subscribers are torn down.
        terminate('camera')
        if settle_s > 0 and ('detector' in owned or 'rectify' in owned):
            time.sleep(settle_s)
        for name in ('detector', 'rectify', 'monitor'):
            terminate(name)
        for sig, handler in old_handlers.items():
            signal.signal(sig, handler)
        clean_codes = (0, -signal.SIGINT, 128 + signal.SIGINT)
        clean = not unexpected and failure is None and all(
            r['returncode'] in clean_codes and
            not any(s in r['signals_sent'] for s in ('SIGTERM', 'SIGKILL'))
            for r in records.values())
        atomic_json(output/'process_exits.json', dict(clean_shutdown=clean,
            received_signal=received_signal[0], unexpected_exits=unexpected,
            startup_error=failure, children=records))
    if not clean:
        print('CAPTURE_EXIT_ERROR: review process_exits.json; nonzero exits are retained',
              file=sys.stderr, flush=True)
    if failure:
        print('CAPTURE_ERROR: ' + failure, file=sys.stderr, flush=True)
    return 0 if clean else 1


def monitor(output):
    import cv2
    import numpy as np
    import rclpy
    from rclpy.node import Node
    from rclpy.qos import qos_profile_sensor_data
    from rclpy.signals import SignalHandlerOptions
    from apriltag_msgs.msg import AprilTagDetectionArray
    from sensor_msgs.msg import Image, CameraInfo

    class Monitor(Node):
        def __init__(self):
            super().__init__('pinky_tag_capture_monitor', enable_rosout=False)
            self.raw, self.rect, self.pending = OrderedDict(), OrderedDict(), OrderedDict()
            self.last_received = {'raw': None, 'rect': None, 'detections': None}
            self.counts = {k: 0 for k in self.last_received}
            self.previous = self.counts.copy()
            self.previous_time = time.monotonic()
            self.latest_ids, self.latest_roi = [], []
            self.seen, self.saved = set(), set()
            self.unmatched = 0
            self.preview_at = 0.0
            self.log = (output / 'detections.jsonl').open('x', buffering=1)
            self.subscriptions_owned = [
                self.create_subscription(Image, '/apriltag_camera/image_raw',
                                         lambda m: self.on_image('raw', m), qos_profile_sensor_data),
                self.create_subscription(Image, '/apriltag_camera/image_rect',
                                         lambda m: self.on_image('rect', m), qos_profile_sensor_data),
                self.create_subscription(CameraInfo, '/apriltag_camera/camera_info',
                                         self.on_info, qos_profile_sensor_data),
                self.create_subscription(AprilTagDetectionArray, '/apriltag_camera/detections',
                                         self.on_detection, qos_profile_sensor_data)]
            self.timer = self.create_timer(2.0, self.report)
            print('MONITOR_READY: full-frame detection; ROI40/60/80 recorded separately', flush=True)

        def on_info(self, msg):
            if msg.width != WIDTH or msg.height != HEIGHT:
                raise ValueError('CameraInfo resolution differs from 1280x720')
            path = output / 'camera_info.json'
            if not path.exists():
                atomic_json(path, dict(width=msg.width, height=msg.height,
                    frame=msg.header.frame_id, k=list(msg.k), d=list(msg.d),
                    r=list(msg.r), p=list(msg.p), distortion_model=msg.distortion_model))

        def on_image(self, kind, msg):
            if (msg.width, msg.height) != (WIDTH, HEIGHT) or msg.encoding not in ('bgr8', 'rgb8'):
                raise ValueError('Unsupported camera image shape/encoding: ' + msg.encoding)
            self.counts[kind] += 1
            self.last_received[kind] = time.monotonic()
            rows = np.frombuffer(msg.data, dtype=np.uint8).reshape(msg.height, msg.step)
            frame = rows[:, :msg.width*3].reshape(msg.height, msg.width, 3).copy()
            if msg.encoding == 'rgb8':
                frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
            key = stamp_key(msg.header)
            cache = self.raw if kind == 'raw' else self.rect
            cache[key] = frame
            while len(cache) > 12:
                cache.popitem(last=False)
            self.try_save(key)

        def on_detection(self, msg):
            self.counts['detections'] += 1
            now = time.monotonic()
            self.last_received['detections'] = now
            key = stamp_key(msg.header)
            records = [detection_record(d) for d in msg.detections]
            received_ns = self.get_clock().now().nanoseconds
            packet = dict(source_stamp_ns=key[0], frame_id=key[1], received_stamp_ns=received_ns,
                          receipt_minus_source_ms=(received_ns-key[0])/1e6,
                          timestamp_basis='camera cap.read completion; not exposure',
                          detections=records)
            self.log.write(json.dumps(packet, allow_nan=False) + '\n')
            self.latest_ids = sorted({d['id'] for d in records if d['installed']})
            self.latest_roi = sorted({d['id'] for d in records if d['roi60_candidate']})
            self.seen.update(self.latest_ids)
            self.pending[key] = packet
            while len(self.pending) > 12:
                self.pending.popitem(last=False)
                self.unmatched += 1
            self.try_save(key)

        def write_jpg(self, path, frame):
            temp = path.with_name(path.stem + '.tmp.jpg')
            if not cv2.imwrite(str(temp), frame, [cv2.IMWRITE_JPEG_QUALITY, 90]):
                raise RuntimeError('Image save failed: ' + str(path))
            os.replace(temp, path)

        def try_save(self, key):
            if key not in self.raw or key not in self.rect or key not in self.pending:
                return
            packet = self.pending.pop(key)
            raw, rect = self.raw.pop(key), self.rect.pop(key)
            new = []
            for d in packet['detections']:
                if d['installed']:
                    for label, flag in [('seen', True), ('roi60', d['roi60_candidate'])]:
                        token = (d['id'], label)
                        if flag and token not in self.saved:
                            new.append(token)
            now = time.monotonic()
            if not new and now - self.preview_at < 2.0:
                return
            annotated = rect.copy()
            x0,y0,x1,y1 = roi_bounds(.6)
            cv2.rectangle(annotated, (x0,y0), (x1,y1), (0,255,255), 2)
            cv2.putText(annotated, 'ROI 60% (candidate) | source ns ' + str(key[0]),
                        (12,26), cv2.FONT_HERSHEY_SIMPLEX, .55, (0,255,255), 1)
            for d in packet['detections']:
                pts = np.array(d['corners_rectified'], dtype=np.int32)
                color = (0,220,0) if d['roi60_candidate'] else (0,130,255)
                cv2.polylines(annotated, [pts], True, color, 2)
                cv2.putText(annotated, str(d['id']), tuple(pts[0]),
                            cv2.FONT_HERSHEY_SIMPLEX, .65, color, 2)
            for tag_id, label in new:
                prefix = output / ('tag_' + str(tag_id) + '_first_' + label)
                self.write_jpg(prefix.with_name(prefix.name + '_raw.jpg'), raw)
                self.write_jpg(prefix.with_name(prefix.name + '_rectified.jpg'), annotated)
                atomic_json(prefix.with_suffix('.json'), packet)
                self.saved.add((tag_id,label))
            if now - self.preview_at >= 2.0:
                self.write_jpg(output / 'latest_raw.jpg', raw)
                self.write_jpg(output / 'latest_roi.jpg', annotated)
                atomic_json(output / 'latest_frame.json', packet)
                self.preview_at = now

        def report(self):
            now = time.monotonic()
            dt = now-self.previous_time
            rates = {k: round((v-self.previous[k])/dt, 1) for k,v in self.counts.items()}
            ages = {k: None if t is None else round(now-t, 2) for k,t in self.last_received.items()}
            fresh = ages['detections'] is not None and ages['detections'] < 1.0
            print('STATUS raw={raw}Hz rect={rect}Hz detect={detections}Hz'.format(**rates)
                  + ' visible=' + str(self.latest_ids if fresh else 'STALE/WAIT')
                  + ' roi60=' + str(self.latest_roi if fresh else 'STALE/WAIT')
                  + ' seen=' + str(sorted(self.seen)) + ' ages_s=' + str(ages), flush=True)
            atomic_json(output / 'status.json', dict(counts=self.counts, rates_hz=rates,
                age_since_receipt_s=ages, visible=self.latest_ids if fresh else None,
                roi60=self.latest_roi if fresh else None, seen=sorted(self.seen),
                unmatched_still_frames=self.unmatched, note='ROI candidates, not accuracy qualification'))
            self.previous, self.previous_time = self.counts.copy(), now

    rclpy.init(args=[], signal_handler_options=SignalHandlerOptions.NO)
    node = None
    try:
        node = Monitor()
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        if node is not None:
            node.report()
            node.log.close()
            node.destroy_node()
        rclpy.try_shutdown()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    # 이전 수동 명령은 명시적인 --workspace로만 지원한다. 기본값은 저장소 내부다.
    calibration_source = parser.add_mutually_exclusive_group()
    calibration_source.add_argument('--calibration', type=Path)
    calibration_source.add_argument('--workspace', type=Path)
    parser.add_argument('--device', default='/dev/video0')
    parser.add_argument('--output-root', type=Path,
                        default=PROJECT_ROOT/'runs/harvest_tag')
    parser.add_argument("--trial-label",choices=["auto","manual_2ms"])
    parser.add_argument('--plan', action='store_true', help='Print setup only; no ROS/camera started')
    parser.add_argument('--monitor', type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.monitor:
        monitor(args.monitor)
        return 0
    if args.trial_label is None:parser.error("--trial-label is required")
    if args.workspace is not None:
        calibration = args.workspace.expanduser().resolve() / 'src/tag_localization_bringup/config/robot_connection/pcweb400_720p_report.json'
    else:
        calibration = (args.calibration or DEFAULT_CALIBRATION).expanduser().resolve()
    driver = Path(__file__).resolve().parent/'opencv_camera_compare.py'
    for path in (driver, calibration):
        if not path.is_file():
            raise FileNotFoundError('Required capture file: ' + str(path))
    if hashlib.sha256(calibration.read_bytes()).hexdigest() != '7f0512b9f466fb12e36cc424331af727f516670cb9e179dd2c25d7ead8f10e31':
        raise ValueError('Calibration differs from the previously verified capture')
    cal = json.loads(calibration.read_text())
    if (cal['width'], cal['height']) != (WIDTH,HEIGHT):
        raise ValueError('Expected existing 1280x720 calibration')
    settings = dict(version='3-exposure-comparison-lossless',
        comparison_schema='pinky-exposure-ab-v1',trial_label=args.trial_label,
        requested_exposure_s=.002 if args.trial_label=='manual_2ms' else None,
        actual_exposure_metadata_available=False,frame_recording='PC request lease, lossless decoded raw PNG, published frames only',
        purpose='exposure-policy comparison, not localization accuracy trial',
        ids=IDS, black_edge_m=.05, resolution=[WIDTH,HEIGHT], publication_cap_hz=10,
        camera_capture_request_hz=30, roi_fractions=[.4,.6,.8], roi60_bounds=roi_bounds(.6),
        roi_pixel_space='rectified image', device=args.device,
        camera_script=str(driver), calibration=str(calibration),
        calibration_sha256=hashlib.sha256(calibration.read_bytes()).hexdigest(),
        camera_script_sha256=hashlib.sha256(driver.read_bytes()).hexdigest(),
        trial_io_sha256=hashlib.sha256(driver.with_name('trial_io.py').read_bytes()).hexdigest(),
        capture_script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        ros_domain_id=DOMAIN, discovery='LOCALHOST', ros_static_peers='',
        rmw='rmw_cyclonedds_cpp', cyclone_xml=CYCLONE_XML,
        transport_interface='lo', cyclone_peer='127.0.0.1', socket_receive_min_bytes=BUFFER_MIN,
        original_images='lossless decoded raw PNG sequence at published rate while PC recording request is active',
        nav2_initialization=False, localization_correction=False, motion_commands=False)
    if args.plan:
        print(json.dumps(settings, indent=2))
        return 0
    if os.environ.get('ROS_DISTRO') != 'jazzy':
        raise RuntimeError('First run: source /opt/ros/jazzy/setup.bash')
    profiles = [k for k in ('CYCLONEDDS_URI','FASTRTPS_DEFAULT_PROFILES_FILE',
        'FASTDDS_DEFAULT_PROFILES_FILE','ROS_DISCOVERY_SERVER') if os.environ.get(k)]
    if profiles:
        raise RuntimeError('Custom DDS configuration present; preserve it and report these names: ' + ', '.join(profiles))
    rmem = int(Path('/proc/sys/net/core/rmem_max').read_text())
    if rmem < BUFFER_MIN:
        raise RuntimeError('Receive-buffer limit is ' + str(rmem) +
            ' bytes. Restore the earlier robot setting, then rerun: '
            'sudo sysctl -w net.core.rmem_max=16777216')
    settings['kernel_rmem_max'] = rmem
    os.environ['ROS_DOMAIN_ID'] = str(DOMAIN)
    os.environ['ROS_AUTOMATIC_DISCOVERY_RANGE'] = 'LOCALHOST'
    os.environ['ROS_STATIC_PEERS'] = ''
    os.environ['RMW_IMPLEMENTATION'] = 'rmw_cyclonedds_cpp'
    os.environ['CYCLONEDDS_URI'] = CYCLONE_XML
    os.environ.pop('ROS_LOCALHOST_ONLY', None)
    # The parent shell and existing Nav2/driver processes are unaffected.
    import cv2
    import rclpy
    from apriltag_msgs.msg import AprilTagDetectionArray
    from ament_index_python.packages import get_package_prefix
    import yaml
    get_package_prefix('rmw_cyclonedds_cpp')
    binaries = {}
    for package, executable in [('apriltag_ros','apriltag_node'),('image_proc','rectify_node')]:
        binary = Path(get_package_prefix(package))/'lib'/package/executable
        if not binary.is_file():
            raise RuntimeError('Missing executable: ' + package + '/' + executable)
        binaries[package] = str(binary)
    if not Path(args.device).exists():
        raise FileNotFoundError(args.device)
    args.output_root.mkdir(parents=True, exist_ok=True)
    lock = (args.output_root/'capture.lock').open('a')
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        raise RuntimeError('Another copy of this capture is running; use its terminal')
    try:
        busy = subprocess.run(['fuser',args.device], capture_output=True, text=True, timeout=3)
        if busy.returncode == 0:
            raise RuntimeError('Camera already in use, PIDs: ' + busy.stdout.strip())
    except FileNotFoundError:
        pass  # Driver also reports open/read failure; no process is stopped here.
    output = Path(tempfile.mkdtemp(prefix=datetime.now().strftime('%Y%m%d_%H%M%S_'),
                                  dir=args.output_root)).resolve()
    atomic_json(output/'settings.json', settings)
    camera = ['/usr/bin/python3','-u',str(driver),
        '--device',args.device,'--calibration',str(calibration),'--fps','30',
        '--reliability','reliable','--frame-id','apriltag_camera_optical_frame',
        '--trial-label',args.trial_label,'--trial-output',str(output)]
    rectify_parameters = {'use_sim_time':False,'image_transport':'raw','queue_size':5}
    detector_parameters = {'use_sim_time':False,'image_transport':'raw','family':'36h11',
            'size':.05,'tag.ids':list(IDS),'tag.frames':['field_tag_'+str(i) for i in IDS],
            'tag.sizes':[.05]*len(IDS),'pose_estimation_method':'pnp',
            'detector.threads':2,'detector.decimate':2.0,'max_hamming':0}
    for name, parameters in [('rectify',rectify_parameters),('detector',detector_parameters)]:
        (output/(name+'.yaml')).write_text(yaml.safe_dump({'/**':{'ros__parameters':parameters}}))
    rectify = [binaries['image_proc'],'--ros-args','-r','__node:=field_rectify',
        '-r','__ns:=/apriltag_camera','--params-file',str(output/'rectify.yaml'),
        '-r','image:=image_raw']
    detector = [binaries['apriltag_ros'],'--ros-args','-r','__node:=field_apriltag',
        '-r','__ns:=/apriltag_camera','--params-file',str(output/'detector.yaml'),
        '-r','/tf:=/apriltag_camera/diagnostic_tf',
        '-r','/tf_static:=/apriltag_camera/diagnostic_tf_static']
    watcher = ['/usr/bin/python3','-u',str(Path(__file__).resolve()),'--monitor',str(output)]
    commands = dict(monitor=watcher,rectify=rectify,detector=detector,camera=camera)
    atomic_json(output/'commands.json',commands)
    print('OUTPUT: ' + str(output), flush=True)
    print('EXPOSURE_TRIAL:',args.trial_label,'| local lossless published-frame recording | motion OFF until PC command',flush=True)
    print('IDS=100..106 | black edge=50mm | image publication <=10Hz | ROI60 provisional', flush=True)
    print('Capture only: Domain 178 / LOCALHOST / loopback peer. Fleet 156 is unchanged.', flush=True)
    print('Ctrl+C: camera stop -> input drain -> detector -> rectify -> monitor.', flush=True)
    return supervise(commands, output, dict(os.environ))


if __name__ == '__main__':
    try:
        sys.exit(main())
    except Exception as exc:
        print('CAPTURE_ERROR: ' + str(exc), file=sys.stderr, flush=True)
        sys.exit(1)
