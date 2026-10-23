"""AMCL TF를 유지하는 선택적 태그 보정. 구동 명령/TF 발행/주행 취소 기능 없음."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import fcntl
import json
import math
import os
import time
import uuid
import numpy as np
import rclpy
from rclpy.node import Node
from rclpy.time import Time
from rclpy.qos import qos_profile_sensor_data
from geometry_msgs.msg import PoseWithCovarianceStamped
from std_msgs.msg import String
from rcl_interfaces.srv import GetParameters
from tf2_ros import Buffer, TransformListener
from .runtime import load_observer, Lease, Journal, time_valid, resolve
from .pixel_bias import load_profile, compensate
from .tag_adapter import observe, transported, correction, OBSERVATION_ROI, approach_allowed, quality_gain


def stamp_ns(stamp: object) -> int:
    return int(stamp.sec) * 1_000_000_000 + int(stamp.nanosec)


def planar(transform: object) -> list[float]:
    p, r = transform.transform.translation, transform.transform.rotation
    return [p.x, p.y, math.atan2(2 * (r.w*r.z+r.x*r.y), 1-2*(r.y*r.y+r.z*r.z))]


class TagAdapter(Node):
    def __init__(self) -> None:
        super().__init__('tag_amcl_adapter')
        for key in ('project_root', 'config_file', 'capture_directory'):
            self.declare_parameter(key, '')
        self._session = uuid.uuid4().hex
        self._config, self._observer = load_observer(
            self.get_parameter('config_file').value,
            self.get_parameter('project_root').value, self._session)
        if self.get_namespace().strip('/') != self._config['robot_id']:
            raise ValueError('보정 노드 namespace와 robot_id 불일치')
        # 같은 프로젝트·로봇의 보정 중복 실행을 막는다. 실행 중 잠금 파일은 삭제하지 않는다.
        project_root = Path(self.get_parameter('project_root').value).expanduser().resolve()
        self._bias_profile = load_profile(self._config, project_root)
        lock_path = self._config.get('lock_directory', 'runs/locks')
        if not isinstance(lock_path, str) or not lock_path.strip():
            raise ValueError('lock_directory는 비어 있지 않은 경로여야 합니다.')
        lock_dir = resolve(project_root, lock_path)
        lock_dir.mkdir(parents=True, exist_ok=True)
        lock_name = self._config['robot_id'] + '_tag_correction.lock'
        self._lock = (lock_dir / lock_name).open('a')
        fcntl.flock(self._lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        folder = Path(self.get_parameter('capture_directory').value).expanduser().resolve()
        self._journal = Journal(folder, self._observer.context.calibration_version)
        self._events = None
        try:
            output = folder / ('amcl_tag_' + self._session)
            output.mkdir()
            self._events = (output / 'events.jsonl').open('w', buffering=1)
        except OSError as exc:
            self.get_logger().warning('보정 기록 저장 불가: ' + str(exc))
        self._lease = Lease(self._config['robot_id'], self._config['map_id'])
        self._buffer = Buffer()
        self._listener = TransformListener(self._buffer, self)
        self._scan_sync = self._config.get('correction_transport', 'initialpose') == 'scan_sync'
        self._publisher = self.create_publisher(
            String if self._scan_sync else PoseWithCovarianceStamped,
            'tag_localization/correction' if self._scan_sync else 'initialpose', 10)
        self._receiver_events = self.create_subscription(
            String, 'tag_localization/events', self._on_receiver_event, 100) if self._scan_sync else None
        self._control = self.create_subscription(String, 'tag_localization/control', self._on_control, 10)
        self._amcl = self.create_subscription(PoseWithCovarianceStamped, 'amcl_pose', self._on_amcl, qos_profile_sensor_data)
        self._amcl_parameters = self.create_client(GetParameters, 'amcl/get_parameters')
        self._parameter_future = None
        self._owner_checked = 0.0
        self._amcl_owns_tf = False
        self._pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix='tag_geometry')
        self._future = None
        self._last_stamp = -1
        self._last_send = -math.inf
        self._count = 0
        self._last_multi_applied = None
        self._timer = self.create_timer(.02, self._tick)
        self._owner_timer = self.create_timer(1.0, self._poll_owner)
        self._log('start', tf_owner='AMCL', method='bounded_tag_scan_sync' if self._scan_sync else 'bounded_tag_initialpose',
            observation_roi=list(OBSERVATION_ROI), physical_accuracy_validated=False,
            pixel_bias_model=self._bias_profile['model_id'] if self._bias_profile else 'OFF')
        self.get_logger().info('TAG_ADAPTER_RUNNING: 작업 신호 대기. AMCL TF 유지; 태그 누락은 주행을 취소하지 않습니다.')

    def _log(self, kind: str, **fields: object) -> None:
        if self._events is None:
            return
        try:
            self._events.write(json.dumps(dict(kind=kind, wall_ns=time.time_ns(), **fields), allow_nan=False) + '\n')
        except (OSError, ValueError) as exc:
            self.get_logger().warning('보정 진단 기록 실패: ' + str(exc))

    def _on_control(self, message: String) -> None:
        try:
            self._lease.update(json.loads(message.data), self.get_clock().now().nanoseconds, time.monotonic())
        except (KeyError, ValueError, TypeError):
            self._log('skip', reason='invalid_task_control')

    def _on_receiver_event(self, message: String) -> None:
        """발행과 실제 AMCL 적용을 구분하여 같은 세션에 기록한다."""
        try:
            event = json.loads(message.data)
            if (event.get('robot_id') != self._config['robot_id'] or
                    event.get('map_id') != self._config['map_id']):
                return
            if event.get('producer_session') not in (None, self._session):
                return
            kind = event.pop('kind')
            self._log(kind, **event)
            if (kind == 'tag_correction_applied' and event.get('observation_kind') == 'multi_tag'
                    and event.get('token') == self._lease.token
                    and self._lease.accepts(event['token'], event['source_stamp_ns'], time.monotonic())):
                self._last_multi_applied = dict(token=event['token'],
                    scan_stamp_ns=event['scan_stamp_ns'], odom_anchor=event['odom_anchor'])
            if kind == 'tag_correction_applied':
                self.get_logger().info(f"TAG_CORRECTION_APPLIED: {event['sequence']}")
        except (ValueError, KeyError, TypeError):
            self._log('skip', reason='invalid_receiver_event')

    def _on_amcl(self, message: PoseWithCovarianceStamped) -> None:
        if not self._count:
            return
        p = message.pose.pose
        self._log('amcl_after_request', stamp_ns=stamp_ns(message.header.stamp), request_count=self._count,
            x=p.position.x, y=p.position.y, z=p.orientation.z, w=p.orientation.w,
            covariance=list(message.pose.covariance))

    def _poll_owner(self) -> None:
        if self._parameter_future is not None:
            if not self._parameter_future.done():
                if time.monotonic() - self._query_started > 2.0:
                    self._amcl_parameters.remove_pending_request(self._parameter_future)
                    self._parameter_future = None
                    self._amcl_owns_tf = False
                return
            try:
                values = self._parameter_future.result().values
                sync = self._config.get('correction_transport', 'initialpose') == 'scan_sync'
                self._amcl_owns_tf = (len(values) == (4 if sync else 1) and
                    values[0].type == 1 and values[0].bool_value)
                if sync and self._amcl_owns_tf:
                    expected = ('scan_sync_v1', self._config['robot_id'], self._config['map_id'])
                    self._amcl_owns_tf = all(v.type == 4 and v.string_value == e
                                             for v, e in zip(values[1:], expected))
                self._owner_checked = time.monotonic()
            except Exception:
                self._amcl_owns_tf = False
            self._parameter_future = None
        if self._amcl_parameters.service_is_ready():
            self._query_started = time.monotonic()
            names = ['tf_broadcast']
            if self._config.get('correction_transport', 'initialpose') == 'scan_sync':
                names += ['tag_correction_protocol', 'tag_robot_id', 'tag_map_id']
            self._parameter_future = self._amcl_parameters.call_async(GetParameters.Request(names=names))

    def _solve(self, record: dict) -> tuple:
        begin = time.monotonic()
        candidate, result = observe(self._observer, record)
        if candidate is not None and result['selected'].get('observation_kind') != 'multi_tag':
            candidate = dict(candidate, _bias_tag=result['selected']['tag'],
                _bias_corners=result['selected']['detection']['corners'])
        return candidate, result, time.monotonic() - begin

    def _tick(self) -> None:
        try:
            if self._future is not None and self._future.done():
                future, self._future = self._future, None
                candidate, result, compute_s = future.result()
                self._log('observation', source_stamp_ns=self._pending_record['source_stamp_ns'], result=result)
                if candidate is not None:
                    self._send(candidate, self._pending_record, self._pending_token, compute_s)
            record = self._journal.latest()
            if record is None:
                return
            stamp = int(record['source_stamp_ns'])
            if stamp <= self._last_stamp:
                return
            self._last_stamp = stamp
            now = self.get_clock().now().nanoseconds
            if (self._future is not None or not record['detections'] or
                    not self._lease.accepts(self._lease.token, stamp, time.monotonic()) or
                    time.monotonic() - self._last_send < 1.0):
                return
            if not 0 <= now - stamp <= 1_000_000_000:
                self._log('skip', reason='old_image_skip_only', source_stamp_ns=stamp)
                return
            gate = self._lease.approach_pose
            if gate is not None:
                current = self._buffer.lookup_transform(self._config['map_frame'], self._config['base_frame'], Time())
                if (not self._observer.multi_model_id or
                        not 0 <= now-stamp_ns(current.header.stamp) <= 500_000_000 or
                        not approach_allowed(gate, planar(current))):
                    return
            # 카메라 기록이 아닌 현재 작업 신호가 반복 ID의 구간을 결정한다.
            record = dict(record, section_id=self._lease.section_id)
            self._pending_record, self._pending_token = record, self._lease.token
            # 기하 계산을 별도 스레드로 실행하여 TF/작업 콜백 수신을 계속한다.
            self._future = self._pool.submit(self._solve, record)
        except Exception as exc:
            self._log('skip', reason=str(exc))

    def _send(self, candidate: dict, record: dict, token: str, compute_s: float) -> None:
        mono = time.monotonic()
        if (not self._lease.accepts(token, record['source_stamp_ns'], mono) or
                record.get('section_id') != self._lease.section_id or
                not self._amcl_owns_tf or mono - self._owner_checked > 3.0):
            return
        if (getattr(self._lease, 'approach_pose', None) is not None and
                candidate.get('observation_kind') != 'multi_tag'):
            self._log('quality_skip', reason='approach_requires_multi_tag', source_stamp_ns=record['source_stamp_ns'])
            return
        c = self._config
        stamp = int(record['source_stamp_ns'])
        old = self._buffer.lookup_transform(c['odom_frame'], c['base_frame'], Time(nanoseconds=stamp))
        new = self._buffer.lookup_transform(c['odom_frame'], c['base_frame'], Time())
        pose_ns = stamp_ns(new.header.stamp)
        current = self._buffer.lookup_transform(c['map_frame'], c['base_frame'], Time(nanoseconds=pose_ns))
        if not approach_allowed(getattr(self._lease, 'approach_pose', None), planar(current)):
            return
        try:
            observed, bias_audit = compensate(candidate, getattr(self, '_bias_profile', None))
        except (ValueError, KeyError, TypeError) as exc:
            self._log('pixel_bias_skip', source_stamp_ns=stamp, reason=str(exc))
            return  # 이 관측의 보정만 생략한다. 주행 상태는 변경하지 않는다.
        tag = transported(observed, planar(old), planar(new))
        gain = quality_gain(candidate, getattr(self, '_last_multi_applied', None), token, pose_ns, planar(new))
        target, delta = correction(planar(current), tag, gain=gain)
        message = PoseWithCovarianceStamped()
        message.header.frame_id, message.header.stamp = c['map_frame'], new.header.stamp
        message.pose.pose.position.x, message.pose.pose.position.y = float(target[0]), float(target[1])
        message.pose.pose.orientation.z, message.pose.pose.orientation.w = math.sin(target[2]/2), math.cos(target[2]/2)
        bound = float(np.linalg.eigvalsh(np.asarray(candidate['p'], float)).max())
        if not math.isfinite(bound) or bound < 0:
            raise ValueError('invalid_tag_covariance')
        cov = [0.] * 36
        cov[0] = cov[7] = max(.05**2, bound)
        cov[35] = max(math.radians(5)**2, bound)
        message.pose.covariance = cov
        now = self.get_clock().now().nanoseconds
        if not time_valid(stamp, pose_ns, now):
            self._log('timing_skip', reason='expired_before_send', compute_s=compute_s,
                image_age_s=(now-stamp)/1e9, pose_age_s=(now-pose_ns)/1e9)
            return
        if not self._lease.accepts(token, stamp, time.monotonic()) or self._publisher.get_subscription_count() == 0:
            return
        if c.get('correction_transport', 'initialpose') == 'scan_sync':
            # 기하 계산은 보존하고 수신 측에서 작업과 시각을 다시 검사할 정보를 전달한다.
            payload = dict(protocol=1, robot_id=c['robot_id'], map_id=c['map_id'],
                token=token, producer_session=self._session, sequence=self._count + 1,
                source_stamp_ns=stamp, pose_stamp_ns=pose_ns, sent_stamp_ns=now,
                frame_id=c['map_frame'], pose=target.tolist(), covariance=cov,
                observation_kind=candidate.get('observation_kind', 'single_tag'))
            if self._lease.section_id is not None:
                payload['section_id'] = self._lease.section_id
            message = String()
            message.data = json.dumps(payload, allow_nan=False)
        self._publisher.publish(message)
        self._last_send = time.monotonic()
        self._count += 1
        self._log('tag_correction_requested', number=self._count, task_token=token, source_stamp_ns=stamp,
            section_id=self._lease.section_id,
            output_stamp_ns=pose_ns, send_ros_ns=now, compute_s=compute_s,
            image_age_at_send_s=(now-stamp)/1e9, pose_age_at_send_s=(now-pose_ns)/1e9,
            tag=[d['id'] for d in record['detections']], before=planar(current), tag_current=tag.tolist(),
            requested=target.tolist(), residual=delta.tolist(), covariance=cov, pixel_bias=bias_audit, correction_gain=gain,
            observation_kind=candidate.get('observation_kind', 'single_tag'))
        self.get_logger().info(f'TAG_CORRECTION_SENT: {self._count}')

    def close(self) -> None:
        self._timer.cancel()
        self._pool.shutdown(wait=True, cancel_futures=True)
        self._log('closed', correction_requests=self._count, tf_owner='AMCL')
        self._journal.close()
        self._listener.unregister()
        if self._events:
            self._events.close()
        self._lock.close()


def main(args: list[str] | None = None) -> None:
    rclpy.init(args=args)
    node = None
    try:
        node = TagAdapter()
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        if node is not None:
            node.close()
            node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()

