"""공통 회전 어댑터의 비차체 확장 지점. 준비/물리 정지는 명시 서비스에 위임."""
from dataclasses import dataclass
from typing import Any
from .discharge_result import DischargeEvidence
from .transfer_devices import DeviceResult


@dataclass
class _Ticket:
    operation: str
    value: Any
    error: str = ''


class DischargeDevices:
    def __init__(self, devices: Any, client: Any) -> None:
        self.devices, self.client = devices, client
        self.evidence = None
        self._blocked = False

    def begin(self, transfer_id: str) -> None:
        """공통 통신 계층이 새 인계 실행 직전에 호출. 이전 성공 증거를 재사용하지 않는다."""
        if not self.ready(): raise RuntimeError('배출 장치 준비/종료 미확인')
        self.evidence = DischargeEvidence(transfer_id)

    def ready(self) -> bool:
        return not self._blocked and self.devices.ready() and self.client.ready()

    def start(self, operation: str) -> _Ticket:
        if operation == 'stop':
            self._blocked = True
            if self.evidence: self.evidence.invalidate()
            # Action 취소 실패가 실제 장치 정지 요청 자체를 생략하지 않게 한다.
            errors = []; value = None
            try: value = self.devices.start('stop')
            except Exception as error: errors.append(str(error))
            try: self.client.cancel()
            except Exception as error: errors.append(str(error))
            return _Ticket(operation, value, '; '.join(errors))
        if self._blocked or self.evidence is None: raise RuntimeError('활성 인계 없음 또는 복구 필요')
        if operation == 'prepare_arm': return _Ticket(operation, self.devices.start(operation))
        if operation == 'discharge': return _Ticket(operation, self.client.start(self.evidence))
        if operation == 'restore_devices': return _Ticket(operation, self.evidence.restore_check())
        raise ValueError('지원하지 않는 비차체 동작: ' + operation)

    def poll(self, ticket: _Ticket) -> DeviceResult:
        if ticket.operation == 'restore_devices': return ticket.value
        if ticket.operation == 'discharge': return self.client.poll(ticket.value)
        if ticket.value is None: return DeviceResult(True, False, ticket.error)
        result = self.devices.poll(ticket.value)
        if not result.completed: return result
        if ticket.error: return DeviceResult(True, False, ticket.error + '; ' + result.detail)
        return result

    def close(self, node: Any) -> None:
        self.client.close(); self.devices.close(node)
