"""60Hz r2 원본 계산에서 추출. 재생성: sim/tools/import_teacher60.py."""

from dataclasses import dataclass

@dataclass(frozen=True)

class FollowupSpec:
    bridge_velocity_cap: float=1.5
    bridge_rate_deg_s: float=6.
    transport_mode: str='baseline'

    def validate(self):
        if self.bridge_velocity_cap not in (1.5,.3,.15):raise ValueError('Only original/0.3/0.15rad/s comparison')
        if self.bridge_rate_deg_s not in (6.,3.):raise ValueError('Only original6 or gentler3deg/s')
        if self.transport_mode not in ('baseline','early_position'):raise ValueError('Unknown transport comparison')
        return self

def early_escape(scope,clear,error,blocked,qualified):
    # Do not wait until every proposed joint command becomes zero. A single
    # active-set limit with >20mm remaining goal error is evidence of constraint.
    return scope & clear & qualified & (error>.02) & (blocked>=1)
