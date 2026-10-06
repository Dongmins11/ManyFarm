"""이동 구간의 선택적 태그 보정 신호. 응답 대기/주행 허가 판정은 하지 않는다."""
import json
import threading
import uuid
from std_msgs.msg import String


class TagControl:
    def __init__(self, node: object, robot_id: str, map_id: str) -> None:
        self._node, self._robot_id, self._map_id = node, robot_id, map_id
        self._lock = threading.Lock()
        self._token = ''
        self._sequence = 0
        self._begin_ns = 0
        self._enabled = False
        self._publisher = node.create_publisher(String, 'tag_localization/control', 10)
        self._timer = node.create_timer(.5, self._heartbeat)

    def _publish(self) -> None:
        self._sequence += 1
        try:
            message = String()
            message.data = json.dumps(dict(robot_id=self._robot_id, map_id=self._map_id,
                token=self._token, sequence=self._sequence, begin_ns=self._begin_ns,
                stamp_ns=self._node.get_clock().now().nanoseconds, enabled=self._enabled))
            self._publisher.publish(message)
        except Exception as exc:
            # 종료 시 DDS context 무효/보정 노드 부재도 기존 주행 결과를 바꾸지 않는다.
            self._node.get_logger().warning('태그 보정 사용 신호 전송 실패: ' + str(exc))

    def begin(self) -> None:
        with self._lock:
            self._token = uuid.uuid4().hex
            self._sequence = 0
            self._begin_ns = self._node.get_clock().now().nanoseconds
            self._enabled = True
            self._publish()

    def end(self) -> None:
        with self._lock:
            self._enabled = False
            if self._token:
                self._publish()

    def _heartbeat(self) -> None:
        with self._lock:
            if self._enabled:
                self._publish()
