"""락 범위 비교용 계측. 제어 조건을 변경하지 않으며 HANDOFF_TIMING=1에서만 기록한다."""
import json
import os
import threading
import time
from contextlib import contextmanager

class TimingProbe:
    def __init__(self, node):
        self.node = node
        self.enabled = os.environ.get('HANDOFF_TIMING') == '1'
        self.lock = threading.Lock()
        self.values = {}
        self.last_emit = 0.

    def add(self, name, value):
        if not self.enabled:
            return
        with self.lock:
            row = self.values.setdefault(name, {'count': 0, 'max': value, 'last': value})
            row['count'] += 1
            row['max'] = max(row['max'], value)
            row['last'] = value

    @contextmanager
    def measure(self, name):
        start = time.monotonic()
        try:
            yield
        finally:
            self.add(name, time.monotonic()-start)

    def emit(self):
        if not self.enabled:
            return
        now = time.monotonic()
        with self.lock:
            if now-self.last_emit < 5:
                return
            self.last_emit = now
            values, self.values = self.values, {}
        # 현재 버퍼의 시각만 읽는다. TF 수신 콜백의 실행 대기를 직접 측정한 값은 아니다.
        try:
            from rclpy.time import Time
            poses = self.node.poses
            tf = poses._buffer.lookup_transform(poses._settings.map_frame,
                                                poses._settings.base_frame, Time())
            ns = tf.header.stamp.sec*10**9+tf.header.stamp.nanosec
            values['tf_buffer_age_s'] = (self.node.get_clock().now().nanoseconds-ns)/1e9
        except Exception as exc:
            values['tf_buffer_error'] = str(exc)
        self.node.get_logger().info('HANDOFF_TIMING '+json.dumps(values, ensure_ascii=False))

class TimedRLock:
    def __init__(self, probe):
        self.inner = threading.RLock()
        self.local = threading.local()
        self.probe = probe

    def __enter__(self):
        start = time.monotonic()
        self.inner.acquire()
        acquired = time.monotonic()
        stack = getattr(self.local, 'stack', [])
        stack.append((acquired, acquired-start))
        self.local.stack = stack
        return self

    def __exit__(self, *args):
        acquired, waited = self.local.stack.pop()
        held = time.monotonic()-acquired
        self.inner.release()
        self.probe.add('runtime_lock_wait_s', waited)
        self.probe.add('runtime_lock_hold_s', held)
