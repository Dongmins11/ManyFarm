"""선택적 내부 수신 계측. 유한 큐와 별도 기록 스레드로 제어 callback의 파일 I/O를 피한다."""
import hashlib
import json
import marshal
import os
from pathlib import Path
import queue
import sys
import threading
import time
from functools import wraps
from typing import Any, Callable


def stamp_ns(msg: Any) -> int:
    return msg.header.stamp.sec*10**9+msg.header.stamp.nanosec


class InputTrace:
    def __init__(self, runtime: Any) -> None:
        self.runtime = runtime
        self.node = runtime.node
        self.enabled = bool(os.environ.get('HANDOFF_INPUT_TRACE'))
        self.local = threading.local()
        self.queue = queue.Queue(maxsize=4096)
        self.dropped = 0
        self.write_error = ''
        self.closed = threading.Event()
        self.previous_tick = None
        self.next_buffer = 0.
        self.subscription = None
        self.worker = None
        if not self.enabled:
            return
        folder = Path(os.environ['HANDOFF_INPUT_TRACE'])
        folder.mkdir(parents=True, exist_ok=True)
        self.path = folder/f'internal-{os.getpid()}-{time.time_ns()}.jsonl'
        self.stream = self.path.open('x')
        self.worker = threading.Thread(target=self._write, name='handoff_trace_writer', daemon=True)
        self.worker.start()
        from tf2_msgs.msg import TFMessage
        from rclpy.qos import qos_profile_sensor_data
        # 기존 TF listener callback을 교체하지 않는다. 이 tap은 내부 수신 비교용이다.
        self.subscription = self.node.create_subscription(TFMessage, 'tf', self.tf,
            qos_profile_sensor_data, callback_group=self.node.callbacks)
        modules = {}
        for name in ('harvest_robot.handoff_runtime', 'harvest_robot.handoff_body_trial',
                     'harvest_robot.handoff_planning', 'harvest_robot.handoff_navigation',
                     'farm_navigation.pose_provider', 'farm_common.action_handoff'):
            module = sys.modules.get(name)
            file = getattr(module, '__file__', None)
            if file:
                modules[name] = dict(path=file, sha256=hashlib.sha256(Path(file).read_bytes()).hexdigest())
        codes = {name:hashlib.sha256(marshal.dumps(getattr(type(runtime),name).__code__)).hexdigest()
                 for name in ('_receive','_read','_forward_control','build_body')}
        self.emit('startup', modules=modules, runtime_code_sha256=codes, mode='fixed_with_input_trace')
        self.node.get_logger().info('HANDOFF_INPUT_TRACE '+str(self.path))

    def emit(self, event: str, **values: Any) -> None:
        if not self.enabled:
            return
        row = dict(event=event, mono_ns=time.monotonic_ns(),
                   ros_ns=self.node.get_clock().now().nanoseconds,
                   thread=threading.get_native_id(), stage=getattr(self.local,'stage',''), **values)
        try:
            self.queue.put_nowait(row)
        except queue.Full:
            self.dropped += 1

    def _write(self) -> None:
        try:
            while not self.closed.is_set() or not self.queue.empty():
                try:
                    row = self.queue.get(timeout=.2)
                except queue.Empty:
                    self.stream.flush()
                    continue
                self.stream.write(json.dumps(row, ensure_ascii=False)+'\n')
            self.stream.write(json.dumps(dict(event='trace_end', dropped=self.dropped))+'\n')
            self.stream.flush()
        except Exception as error:
            self.write_error = str(error)
        finally:
            self.stream.close()

    def receive(self, event: str, key: str, msg: Any) -> None:
        if self.enabled:
            self.emit(event, key=key, stamp_ns=stamp_ns(msg))

    def tf(self, msg: Any) -> None:
        for value in msg.transforms:
            self.emit('tf_tap', parent=value.header.frame_id, child=value.child_frame_id,
                      stamp_ns=stamp_ns(value))

    def tick(self) -> None:
        if not self.enabled:
            return
        now = time.monotonic()
        gap = None if self.previous_tick is None else now-self.previous_tick
        self.previous_tick = now
        self.emit('watchdog_tick', gap_s=gap, dropped=self.dropped, writer_error=self.write_error)
        if now < self.next_buffer:
            return
        self.next_buffer = now+.2
        from rclpy.time import Time
        poses = self.node.poses
        for parent, child in ((self.runtime.settings.map_frame, 'odom'),
                              ('odom', self.runtime.settings.base_frame)):
            try:
                value = poses._buffer.lookup_transform(parent, child, Time())
                self.emit('tf_buffer', parent=parent, child=child, stamp_ns=stamp_ns(value))
            except Exception as error:
                self.emit('tf_buffer_error', parent=parent, child=child, error=str(error))

    def expired(self, key: str, received: float, msg: Any, limit: float,
                receive_age: float, header_age: float, snapshot: bool) -> str:
        values = dict(key=key, stamp_ns=stamp_ns(msg), received_mono_s=received,
                      receive_age_s=receive_age, header_age_s=header_age,
                      age_limit_s=limit, header_min_s=-.1, snapshot=snapshot,
                      receive_expired=receive_age>limit, header_invalid=not -.1<=header_age<=limit)
        self.emit('input_expired', **values)
        return '입력 시각 만료: '+key+' '+json.dumps(values, ensure_ascii=False)

    def close(self) -> None:
        if self.subscription is not None:
            self.node.destroy_subscription(self.subscription)
        self.closed.set()
        if self.worker is not None:
            self.worker.join(timeout=2.)
            if self.worker.is_alive() or self.write_error:
                self.node.get_logger().warning('HANDOFF_INPUT_TRACE 기록 종료 미확인: '+self.write_error)


def traced(function: Callable) -> Callable:
    """현재 worker의 단계 이름을 보존한다. 제어 호출·반환·예외를 그대로 전달한다."""
    @wraps(function)
    def call(self: Any, *args: Any, **kwargs: Any) -> Any:
        runtime = getattr(self, 'runtime', None) or getattr(self, '_inputs', None) or self
        probe = getattr(runtime, '_input_trace', None)
        if probe is None or not probe.enabled:
            return function(self, *args, **kwargs)
        previous = getattr(probe.local, 'stage', '')
        stage = function.__qualname__
        if args and isinstance(args[0], str):
            stage += ':'+args[0]
        probe.local.stage = stage
        start = time.monotonic_ns()
        probe.emit('stage_begin')
        try:
            return function(self, *args, **kwargs)
        except Exception as error:
            probe.emit('stage_error', error=str(error))
            raise
        finally:
            probe.emit('stage_end', elapsed_s=(time.monotonic_ns()-start)/1e9)
            probe.local.stage = previous
    return call
