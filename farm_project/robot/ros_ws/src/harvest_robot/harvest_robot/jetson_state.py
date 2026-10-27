"""Jetson 통신의 순수 판정. 시간 단위는 초/나노초, 속도는 m/s·rad/s다.

ROS 호출·동작·복구를 하지 않는다. 호출자가 같은 잠금 안에서 입력과 판정을 수행한다.
"""
from dataclasses import dataclass, asdict
import math
from typing import Any, Mapping


@dataclass(frozen=True)
class JetsonSettings:
    control_state_topic: str
    runtime_status_topic: str
    runtime_mode: str = 'depth_v11'
    odom_frame: str = 'odom'
    control_state_rate_hz: float = 10.0
    runtime_status_timeout_s: float = 2.5
    future_tolerance_s: float = .05

    @classmethod
    def from_config(cls, config: Mapping[str, Any]) -> 'JetsonSettings | None':
        """미설정은 기존 동작 유지. 명시적 활성 설정의 오타·비정상 수치는 거절한다."""
        if not isinstance(config, Mapping):
            raise ValueError('jetson_connection은 객체여야 합니다.')
        enabled = config.get('enabled', False)
        if type(enabled) is not bool:
            raise ValueError('jetson_connection.enabled는 bool이어야 합니다.')
        if not enabled:
            return None
        if set(config) - (set(cls.__dataclass_fields__) | {'enabled'}):
            raise ValueError('알 수 없는 jetson_connection 설정')
        values = {k: v for k, v in config.items() if k != 'enabled'}
        result = cls(**values)
        if not isinstance(result.runtime_mode, str) or not result.runtime_mode.strip():
            raise ValueError('runtime_mode는 회신의 실제 모드 문자열이어야 합니다.')
        if not isinstance(result.odom_frame, str) or not result.odom_frame or any(c.isspace() for c in result.odom_frame):
            raise ValueError('odom_frame 설정이 필요합니다.')
        for name in ('control_state_topic', 'runtime_status_topic'):
            topic = getattr(result, name)
            if (not isinstance(topic, str) or not topic.startswith('/') or topic == '/'
                    or any(c.isspace() for c in topic)):
                raise ValueError(name + ': 절대 ROS 토픽 이름이 필요합니다.')
        if len({result.control_state_topic, result.runtime_status_topic}) != 2:
            raise ValueError('통신 토픽은 서로 달라야 합니다.')
        for name in ('control_state_rate_hz', 'runtime_status_timeout_s', 'future_tolerance_s'):
            v = getattr(result, name)
            if type(v) not in (float, int) or not math.isfinite(v) or v <= 0:
                raise ValueError(name + ': 유한한 양수가 필요합니다.')
        return result


@dataclass(frozen=True)
class RuntimeSample:
    robot_id: str
    boot_id: str
    sequence: int
    stamp_ns: int
    mode: str
    ready: bool
    device_state_valid: bool
    arm_stowed: bool
    arm_stopped: bool
    box_stopped: bool
    box_state: str
    recovery_required: bool
    error_code: str
    task_id: str = ''
    window_id: str = ''
    transfer_id: str = ''
    state: str = ''
    phase: str = ''
    success_count: int = 0
    failed_count: int = 0
    error_message: str = ''


class RuntimeTracker:
    """해당 로봇의 최신 수신 상태를 보관한다. 준비/모드/박스/재시작 판정을 강제하지 않는다."""
    def __init__(self, robot_id: str, settings: JetsonSettings) -> None:
        self._robot_id, self._settings = robot_id, settings
        self._sample: RuntimeSample | None = None
        self._received_s = 0.0
        self._retired_boots: set[str] = set()

    def receive(self, sample: RuntimeSample, now_s: float) -> bool:
        """같은 boot의 증가 sequence만 갱신한다. 새 boot는 허용하고 이전 boot 재전송은 제외한다."""
        if sample.robot_id != self._robot_id or not sample.boot_id or sample.boot_id in self._retired_boots:
            return False
        previous = self._sample
        if previous is not None:
            if sample.boot_id == previous.boot_id:
                if sample.sequence <= previous.sequence:
                    return False
            else:
                self._retired_boots.add(previous.boot_id)
        self._sample, self._received_s = sample, now_s
        return True

    def snapshot(self, now_s: float) -> dict:
        """수신 만료는 조회 정보이며 미션 오류나 자동 중단을 발생시키지 않는다."""
        age = None if self._sample is None else max(0., now_s-self._received_s)
        return {'status': None if self._sample is None else asdict(self._sample),
                'age_s': age,
                'stale': age is None or age > self._settings.runtime_status_timeout_s}

    def ready_to_send(self, now_ns: int, now_s: float) -> bool:
        """회신의 mode/최신 TTL/ready만 검사한다. 박스·팔 자세·업무 ID 조건은 추가하지 않는다."""
        sample = self._sample
        return bool(sample is not None and not self.snapshot(now_s)['stale']
                    and (now_ns-sample.stamp_ns)/1e9 <= self._settings.runtime_status_timeout_s
                    and sample.mode == self._settings.runtime_mode and sample.ready)


class ControlTracker:
    """실제 odom의 시각 진행과 지속 정지로 발행 값을 만든다."""
    def __init__(self, *, odom_age_s: float, settle_s: float, linear_mps: float,
                 angular_rps: float, future_s: float) -> None:
        self._odom_age_s, self._settle_s = odom_age_s, settle_s
        self._linear_mps, self._angular_rps = linear_mps, angular_rps
        self._future_s = future_s
        self._stamp_ns = 0
        self._received_s = 0.0
        self._first_stopped_ns: int | None = None

    def odom(self, stamp_ns: int, vx: float, vy: float, wz: float,
             now_ns: int, now_s: float, valid_frame: bool) -> None:
        """같은 stamp 재수신은 수신 최신성과 정지 지속시간을 갱신하지 않는다."""
        if (not valid_frame or stamp_ns <= 0 or not all(math.isfinite(v) for v in (vx, vy, wz))
                or not -self._future_s <= (now_ns-stamp_ns)/1e9 <= self._odom_age_s):
            self._first_stopped_ns = None
            return
        if stamp_ns < self._stamp_ns:
            self._first_stopped_ns = None
            self._stamp_ns = 0
        if stamp_ns == self._stamp_ns:
            return
        if (now_s-self._received_s > self._odom_age_s or
                (self._stamp_ns and (stamp_ns-self._stamp_ns)/1e9 > self._odom_age_s)):
            self._first_stopped_ns = None
        self._stamp_ns, self._received_s = stamp_ns, now_s
        if math.hypot(vx, vy) < self._linear_mps and abs(wz) < self._angular_rps:
            if self._first_stopped_ns is None:
                self._first_stopped_ns = stamp_ns
        else:
            self._first_stopped_ns = None

    def observation_fresh(self, now_ns: int, now_s: float) -> bool:
        """V3 발행 기준: 실제 관측의 수신·측정 나이가 0.2초 이내인지 확인한다."""
        return (self._stamp_ns > 0 and 0 <= now_s-self._received_s <= .2
                and -self._future_s <= (now_ns-self._stamp_ns)/1e9 <= .2)

    def values(self, now_ns: int, now_s: float, *, motion_idle: bool) -> tuple[int, bool]:
        """반환: 원본 측정 stamp(ns), 차체 정지. 발행 유효성은 별도로 확인한다."""
        fresh = (self._stamp_ns > 0 and 0 <= now_s-self._received_s <= self._odom_age_s
                 and -self._future_s <= (now_ns-self._stamp_ns)/1e9 <= self._odom_age_s)
        stopped = (fresh and motion_idle and self._first_stopped_ns is not None
                   and self._stamp_ns-self._first_stopped_ns >= int(self._settle_s*1e9))
        # 입력 부족 때도 송신 시각으로 오래된 관측을 새 표본처럼 만들지 않는다.
        stamp = self._stamp_ns
        return stamp, bool(stopped)
