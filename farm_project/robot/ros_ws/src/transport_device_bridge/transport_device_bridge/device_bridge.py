"""운송로봇 바구니 기구(윗덮개·앞문·틸트) ROS 2 브리지 노드.

  운송 노드 ──std_srvs/Trigger──▶ device_bridge ──/dev/ttyS0──▶ OpenCR (oc_tb3_actuator)

서비스 (기본 robot_ns = transport_01)
  /transport_01/device/lid_open    lid open                           → DONE lid open
  /transport_01/device/lid_close   lid close                          → DONE lid close
  /transport_01/device/gate_open   gate open                          → DONE gate open
  /transport_01/device/gate_close  gate close                         → DONE gate close
  /transport_01/device/unload      gate open → tilt dump → gate close → 3개 모두 DONE
  /transport_01/device/stop        stop                               → OK stop all
토픽
  /transport_01/device/raw  (std_msgs/String)  OpenCR 회신 원문

- 서비스는 동작이 끝나야 응답한다 (덮개 약 4.0초, unload 약 23초) → 호출 쪽은 call_async 사용
- 동작 서비스는 한 번에 하나. 다른 동작 중이면 success=false 'busy'
- stop 은 언제든 받음. 진행 중인 동작은 success=false 로 끝남
- 실패(STOPPED / ERR / 시간 초과 / READY) 시 안전을 위해 stop 을 보내고 success=false
"""
import threading

import rclpy
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.executors import MultiThreadedExecutor
from rclpy.node import Node
from std_msgs.msg import String
from std_srvs.srv import Trigger

from .device_link import DeviceLink

# 서비스 이름 → [(펌웨어 명령, 이름, 동작, 제한 시간 파라미터), ...]
MOTIONS = {
    'lid_open':   [('lid open', 'lid', 'open', 'lid_timeout')],
    'lid_close':  [('lid close', 'lid', 'close', 'lid_timeout')],
    'gate_open':  [('gate open', 'gate', 'open', 'gate_timeout')],
    'gate_close': [('gate close', 'gate', 'close', 'gate_timeout')],
    'unload': [
        ('gate open', 'gate', 'open', 'gate_timeout'),
        ('tilt dump', 'tilt', 'dump', 'dump_timeout'),
        ('gate close', 'gate', 'close', 'gate_timeout'),
    ],
}


class DeviceBridge(Node):

    def __init__(self):
        super().__init__('device_bridge')
        self.declare_parameter('robot_ns', 'transport_01')
        self.declare_parameter('port', '/dev/ttyS0')
        self.declare_parameter('baud', 115200)
        self.declare_parameter('lid_timeout', 10.0)    # 실제 약 4.0초
        self.declare_parameter('gate_timeout', 5.0)    # 실제 약 1.2초
        self.declare_parameter('dump_timeout', 30.0)   # 실제 약 20초
        self.declare_parameter('stop_timeout', 1.0)
        self.declare_parameter('ping_timeout', 1.0)

        ns = self._p('robot_ns').strip('/')
        base = f'/{ns}/device' if ns else '/device'

        self._busy = threading.Lock()
        self._current = None
        self._abort = threading.Event()
        self._cb = ReentrantCallbackGroup()

        self._raw_pub = self.create_publisher(String, f'{base}/raw', 20)
        for key in MOTIONS:
            self.create_service(Trigger, f'{base}/{key}',
                                lambda req, res, k=key: self._on_motion(k, res),
                                callback_group=self._cb)
        self.create_service(Trigger, f'{base}/stop', self._on_stop, callback_group=self._cb)

        self.link = DeviceLink(self._p('port'), self._p('baud'),
                               on_line=self._on_line, on_ready=self._on_ready,
                               log=self.get_logger().info)
        self.link.start()
        threading.Thread(target=self._check_ping, daemon=True).start()
        self.get_logger().info(f'서비스 준비: {base}/{{{",".join(list(MOTIONS) + ["stop"])}}}')

    def _p(self, name):
        return self.get_parameter(name).value

    # ---------- 수신 ----------
    def _on_line(self, line):
        self._raw_pub.publish(String(data=line))
        if line.startswith(('DONE', 'STOPPED', 'ERR', 'READY')):
            self.get_logger().info(f'OpenCR: {line}')
        else:
            self.get_logger().debug(f'OpenCR: {line}')

    def _on_ready(self):
        self.get_logger().warn('OpenCR 재부팅 감지 (READY). 덮개·앞문은 닫힌 상태에서 다시 시작해야 함')

    def _check_ping(self):
        for _ in range(30):                      # UART 열릴 때까지 최대 3초 대기
            if self.link.connected:
                break
            threading.Event().wait(0.1)
        for i in range(5):
            ok, msg = self.link.request('ping', prefix='PONG', timeout=self._p('ping_timeout'))
            if ok:
                self.get_logger().info('OpenCR 연결 확인 (PONG)')
                return
            self.get_logger().warn(f'OpenCR ping 실패 {i + 1}/5: {msg}')
            threading.Event().wait(2.0)
        self.get_logger().error('OpenCR 응답 없음. 통합 펌웨어(oc_tb3_actuator)·UART 배선·포트 확인')

    # ---------- 서비스 ----------
    def _send_stop(self):
        return self.link.request('stop', prefix='OK stop', timeout=self._p('stop_timeout'))

    def _on_motion(self, key, res):
        if not self._busy.acquire(blocking=False):
            res.success = False
            res.message = f'busy: {self._current} 동작 중'
            self.get_logger().warn(f'{key} 거절 → {res.message}')
            return res
        try:
            self._current = key
            self._abort.clear()
            self.get_logger().info(f'{key} 시작')
            done = []
            for cmd, name, act, tkey in MOTIONS[key]:
                if self._abort.is_set():
                    ok, msg = False, 'stop 요청으로 중단'
                else:
                    ok, msg = self.link.request(cmd, name=name, act=act, timeout=self._p(tkey))
                if not ok:
                    if not self._abort.is_set():
                        self._send_stop()           # 안전: 실패하면 전체 정지
                    res.success = False
                    res.message = f'{cmd} 실패: {msg}' + (f' (완료: {", ".join(done)})' if done else '')
                    self.get_logger().warn(f'{key} → {res.message}')
                    return res
                done.append(cmd)
            res.success = True
            res.message = 'DONE ' + ' -> '.join(done)
            self.get_logger().info(f'{key} 완료')
            return res
        finally:
            self._current = None
            self._busy.release()

    def _on_stop(self, req, res):
        self._abort.set()
        ok, msg = self._send_stop()
        res.success, res.message = ok, msg
        self.get_logger().warn(f'stop 요청 → {msg}')
        return res

    def destroy_node(self):
        if self._current is not None:
            self._abort.set()
            self._send_stop()
        self.link.shutdown()
        super().destroy_node()


def main(args=None):
    rclpy.init(args=args)
    node = DeviceBridge()
    ex = MultiThreadedExecutor(num_threads=4)
    ex.add_node(node)
    try:
        ex.spin()
    except (KeyboardInterrupt, rclpy.executors.ExternalShutdownException):
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()
