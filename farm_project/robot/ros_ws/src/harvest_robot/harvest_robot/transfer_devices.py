"""인계 장치 경계. 미설정 장치를 성공으로 처리하지 않는다.

실물 담당 노드의 std_srvs/Trigger 서버에 비동기로 요청한다.
각 응답의 success는 명령 접수가 아니라 해당 물리 동작의 완료 확인이다.
prepare_arm: 팔 안전 자세 / rotate_to_transfer: 회전·정지·배출 준비
discharge: 게이트 개방·배출·센서의 적재 해소 확인
restore: 운송 이격 후 게이트 닫힘·장치·원래 자세 복구
stop: 진행 중 동작 중단·정지 확인(운송 이격이나 자세 복구를 뜻하지 않음)

서비스 이름·회전각·센서 조건을 임의로 정하지 않는다. 서비스 매핑이 없으면
인계 Goal을 거절한다. 기존 harvest_task와 주행 알고리즘은 변경하지 않는다.
"""
from dataclasses import dataclass
from typing import Any, Mapping


OPERATIONS = ('prepare_arm', 'rotate_to_transfer', 'discharge', 'restore', 'stop')


@dataclass(frozen=True)
class DeviceResult:
    completed: bool
    ok: bool = False
    detail: str = ''


class TriggerTransferDevices:
    """실물 서비스 연결용 어댑터. poll은 기다리지 않고 즉시 반환한다."""

    def __init__(self, node: Any, services: Mapping[str, str]) -> None:
        from std_srvs.srv import Trigger
        if not isinstance(services, dict):
            raise ValueError('transfer_device_services는 JSON 객체여야 합니다.')
        if services and (set(services) != set(OPERATIONS) or any(
                not isinstance(v, str) or not v.startswith('/') or v == '/'
                or any(c.isspace() for c in v) for v in services.values())):
            raise ValueError('5개 장치 동작에 절대 ROS 서비스 이름이 필요합니다.')
        if services and len(set(services.values())) != len(OPERATIONS):
            raise ValueError('동작마다 서로 다른 서비스가 필요합니다.')
        self._type = Trigger
        self._clients = {name: node.create_client(Trigger, endpoint,
                        callback_group=node.callbacks)
                         for name, endpoint in services.items()}

    def ready(self) -> bool:
        """전체 장치 서비스가 연결됐는지만 검사한다. 실제 조건은 장치가 확인한다."""
        return bool(self._clients) and all(c.service_is_ready() for c in self._clients.values())

    def start(self, operation: str) -> Any:
        """동작을 한 번만 요청한다. timeout 후 자동 재전송하지 않는다."""
        if operation not in self._clients or not self._clients[operation].service_is_ready():
            raise RuntimeError('장치 서비스 미연결: ' + operation)
        return self._clients[operation].call_async(self._type.Request())

    def poll(self, ticket: Any) -> DeviceResult:
        """ROS Future 완료와 물리 완료 응답을 구분한다."""
        if not ticket.done():
            return DeviceResult(False)
        try:
            reply = ticket.result()
            if reply is None:
                return DeviceResult(True, False, '빈 장치 응답')
            return DeviceResult(True, bool(reply.success), str(reply.message))
        except Exception as error:
            return DeviceResult(True, False, str(error))

    def close(self, node: Any) -> None:
        for client in self._clients.values():
            node.destroy_client(client)
