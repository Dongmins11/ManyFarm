"""측정 속도 감시. 명령 제한·충돌 검사를 대신하지 않으며 ROS에 의존하지 않는다."""
from dataclasses import dataclass
import math

@dataclass(frozen=True)
class MeasuredVelocityLimits:
    linear_abs_mps: float
    forward_mps: float
    angular_soft_rps: float
    angular_hard_rps: float
    angular_persistence_s: float
    sample_gap_s: float

    def __post_init__(self) -> None:
        if not all(math.isfinite(x) and x>0 for x in self.__dict__.values()):
            raise ValueError('감시 제한은 양의 유한한 값 필요')
        if not self.angular_soft_rps < self.angular_hard_rps:
            raise ValueError('순간 상한은 지속 상한보다 커야 함')
        if self.forward_mps>self.linear_abs_mps:
            raise ValueError('전진 상한 오류')

class MeasuredVelocityGuard:
    def __init__(self, limits: MeasuredVelocityLimits) -> None:
        self.limits=limits
        self.last_stamp=None
        self.excess_since=None
        self.error=''
        self.events=[]

    def observe(self, stamp_ns: int, linear: float, angular: float) -> None:
        """수신 표본마다 호출. 오류는 래치되어 이후 정상 표본으로 사라지지 않는다."""
        if self.error:raise RuntimeError(self.error)
        reason=''
        if not all(math.isfinite(x) for x in (linear,angular)):
            reason='비유한 측정 속도'
        elif stamp_ns<=0 or (self.last_stamp is not None and stamp_ns<=self.last_stamp):
            reason='odom 시각 중복/역행'
        elif self.last_stamp is not None and (stamp_ns-self.last_stamp)/1e9>self.limits.sample_gap_s:
            reason='odom 표본 간격 초과'
        elif linear>self.limits.forward_mps or abs(linear)>self.limits.linear_abs_mps:
            reason='측정 선속도 범위 이탈'
        elif abs(angular)>self.limits.angular_hard_rps:
            reason='측정 각속도 순간 상한 초과'
        elif abs(angular)>self.limits.angular_soft_rps:
            if self.excess_since is None:
                self.excess_since=stamp_ns
                self.events.append({'kind':'angular_excursion','stamp_ns':stamp_ns,'linear':linear,'angular':angular})
            if (stamp_ns-self.excess_since)/1e9>=self.limits.angular_persistence_s:
                reason='측정 각속도 지속 상한 초과'
        else:
            self.excess_since=None
        self.last_stamp=stamp_ns
        if reason:
            self.error=f'{reason}: v={linear:.9g}, w={angular:.9g}, stamp_ns={stamp_ns}'
            self.events.append({'kind':'blocked','reason':self.error})
            raise RuntimeError(self.error)
