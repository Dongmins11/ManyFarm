"""공통 인계 회전 어댑터. 차체 Spin과 비차체 장치 동작을 조합한다."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
import math
import threading
import time
from typing import Any, Mapping
from .transfer_devices import DeviceResult


ROTATION_DEVICE_OPERATIONS = ('prepare_arm', 'discharge', 'restore_devices', 'stop')


@dataclass(frozen=True)
class RotationSettings:
    endpoint: str
    angle_rad: float
    time_allowance_s: float
    position_tolerance_m: float
    yaw_tolerance_rad: float

    @classmethod
    def from_mapping(cls, values: Mapping) -> 'RotationSettings':
        if not isinstance(values, Mapping):
            raise ValueError('transfer.rotation 객체가 필요합니다.')
        if set(values) != set(cls.__dataclass_fields__):
            raise ValueError('회전 연결/각도/시간/위치·방향 허용값을 모두 명시해야 합니다.')
        result = cls(**values)
        if not isinstance(result.endpoint, str) or not result.endpoint or any(c.isspace() for c in result.endpoint):
            raise ValueError('회전 endpoint가 비어 있거나 공백을 포함합니다.')
        for key in ('angle_rad', 'time_allowance_s', 'position_tolerance_m', 'yaw_tolerance_rad'):
            value = getattr(result, key)
            if type(value) not in (int, float) or not math.isfinite(value) or value <= 0:
                raise ValueError(key + '는 유한한 양수여야 합니다.')
        if result.angle_rad > math.pi or result.yaw_tolerance_rad >= result.angle_rad:
            raise ValueError('회전각은 pi 이하, 방향 허용값은 회전각 미만이어야 합니다.')
        if result.time_allowance_s >= 2147483647:
            raise ValueError('회전 제한시간 범위 초과')
        return result


def rotation_parameters(config: Mapping) -> dict:
    """기존 전체 서비스 방식을 기본으로 보존한다. 새 방식은 명시 선택한다."""
    mode = config.get('rotation_mode', 'device_services')
    if mode not in ('device_services', 'nav2_spin', 'components'):
        raise ValueError('알 수 없는 transfer.rotation_mode')
    values = config.get('rotation', {})
    if mode == 'nav2_spin':
        RotationSettings.from_mapping(values)
    elif mode == 'components':
        if values:
            raise ValueError('components 방식은 rotation 설정을 사용하지 않습니다.')
    elif values:
        raise ValueError('rotation 설정은 nav2_spin 방식에서만 사용합니다.')
    return {'rotation_mode': mode, 'rotation': values}


class RotatingTransferDevices:
    """단일 작업 스레드가 장치 요청을 순차 실행. ROS 콜백은 executor에서 진행한다."""
    def __init__(self, devices: Any, spin: Any, poses: Any, motion: Any,
                 settings: RotationSettings, timeout_s: float, stop_timeout_s: float, *, clock=time.monotonic) -> None:
        self.clock = clock
        self.devices, self.spin, self.poses, self.motion = devices, spin, poses, motion
        self.settings, self.timeout_s, self.stop_timeout_s = settings, timeout_s, stop_timeout_s
        self._pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix='transfer_rotation')
        self._cancel = threading.Event()
        self._ticket = None
        self._origin = None
        self._rotated = False

    def ready(self) -> bool:
        return self.devices.ready() and self.spin.ready() and not self.spin.has_goal and (
            self._ticket is None or self._ticket.done()) and not self._cancel.is_set()

    def start(self, operation: str) -> Any:
        if operation == 'stop':
            # 진행 중 대기를 중단시킨 뒤 같은 작업 스레드에서 자신의 Goal을 정지한다.
            self._cancel.set()
            self._ticket = self._pool.submit(self._stop)
        else:
            if self._ticket is not None and not self._ticket.done():
                raise RuntimeError('이전 인계 장치 작업 진행 중')
            if self._cancel.is_set():
                raise RuntimeError('인계 중단 후 현장 복구 확인 필요')
            self._ticket = self._pool.submit(self._run, operation)
        return self._ticket

    def poll(self, ticket: Any) -> DeviceResult:
        if not ticket.done():
            return DeviceResult(False)
        try:
            ticket.result()
            return DeviceResult(True, True)
        except Exception as error:
            return DeviceResult(True, False, str(error))

    def _check(self, deadline: float, *, stopping: bool = False) -> None:
        if not stopping and self._cancel.is_set():
            raise RuntimeError('인계 회전 중단 요청')
        if self.clock() >= deadline:
            raise TimeoutError('인계 장치/회전 제한시간 초과')

    def _device(self, operation: str, check: Any) -> None:
        check()
        ticket = self.devices.start(operation)
        while True:
            check()
            result = self.devices.poll(ticket)
            if result.completed:
                if not result.ok:
                    raise RuntimeError(operation + ': ' + result.detail)
                return
            time.sleep(.01)

    def _pose(self, check: Any) -> tuple[float, float, float]:
        matrix = self.poses.current(check)
        return float(matrix[0,3]), float(matrix[1,3]), math.atan2(matrix[1,0], matrix[0,0])

    def _verify(self, target: float, check: Any, *, heading: bool = True) -> None:
        x,y,yaw = self._pose(check)
        ox,oy,_ = self._origin
        if math.hypot(x-ox,y-oy) > self.settings.position_tolerance_m:
            raise RuntimeError('제자리 회전 위치 이탈; 자동 이동 보정 없음')
        error = abs(math.atan2(math.sin(yaw-target), math.cos(yaw-target)))
        if heading and error > self.settings.yaw_tolerance_rad:
            raise RuntimeError('회전 방향 오차 초과; 추가 회전 보정 없음')

    def _turn(self, angle: float, target: float, check: Any) -> None:
        def bounded() -> None:
            check()
            self._verify(target, check, heading=False)
        bounded()
        self.spin.execute(angle, self.settings.time_allowance_s, bounded)
        self.motion.wait_stopped(bounded)
        self._verify(target, check)

    def _run(self, operation: str) -> None:
        deadline = self.clock() + self.timeout_s
        check = lambda: self._check(deadline)
        check()
        if operation == 'prepare_arm':
            self._origin = None
            self._rotated = False
            self._device(operation, check)
        elif operation == 'rotate_to_transfer':
            self.motion.wait_stopped(check)
            self._origin = self._pose(check)
            self._turn(self.settings.angle_rad, self._origin[2]+self.settings.angle_rad, check)
            self._rotated = True
        elif operation == 'discharge':
            if not self._rotated:
                raise RuntimeError('회전 완료 전 배출 금지')
            self._device(operation, check)
        elif operation == 'restore':
            if not self._rotated or self._origin is None:
                raise RuntimeError('복원 기준 없음')
            # 게이트 닫힘/팔·장치 복원 완료 후에만 차체를 반대 각도로 돌린다.
            self._device('restore_devices', check)
            self.motion.wait_stopped(check)
            self._turn(-self.settings.angle_rad, self._origin[2], check)
            self._rotated = False
        else:
            raise ValueError('지원하지 않는 인계 동작: '+operation)

    def _stop(self) -> None:
        deadline = self.clock() + self.stop_timeout_s
        check = lambda: self._check(deadline, stopping=True)
        # 두 정지를 모두 시도한다. 한쪽 실패로 다른 장치의 정리를 생략하지 않는다.
        errors = []
        try:
            ticket = self.devices.start('stop')
        except Exception as error:
            errors.append(str(error)); ticket = None
        try:
            self.spin.cancel()
        except Exception as error:
            errors.append(str(error))
        try:
            self.motion.wait_stopped(check)
        except Exception as error:
            errors.append(str(error))
        if ticket is not None:
            try:
                while True:
                    check()
                    result = self.devices.poll(ticket)
                    if result.completed:
                        if not result.ok:
                            raise RuntimeError(result.detail)
                        break
                    time.sleep(.01)
            except Exception as error:
                errors.append(str(error))
        if errors:
            raise RuntimeError('; '.join(errors))

    def close(self, node: Any) -> None:
        self._cancel.set()
        self._pool.shutdown(wait=True)
        self.spin.close()
        self.devices.close(node)
