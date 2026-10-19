"""Explicit longer pull controller for the provisional60..80mm connector.

Original55mm controller remains frozen. This changes a waypoint budget only;
the fruit is never teleported, assisted, or attached to a gripper constraint.
"""
from dataclasses import asdict,dataclass
import math
from .bridge_pull_risk import RiskPullSpec


@dataclass(frozen=True)
class NativePullSpec(RiskPullSpec):
    travel_m: float=.09

    def __post_init__(self):
        if any(not math.isfinite(v) or v<=0 for k,v in asdict(self).items()
               if k not in ('hold_after_detach','axial')):
            raise ValueError('Finite positive native pull parameters')
        if not .08<=self.travel_m<=.10 or self.speed_m_s>.03 or self.joint_speed_rad_s>.3:
            raise ValueError('Native pull is bounded80..100mm,30mm/s and0.3rad/s')
        if not self.risk_axial_m<self.risk_lateral_m<self.risk_extension_m<.04:
            raise ValueError('Keep the original physical intervention gate')


def assert_opening_budget(path,connector):
    if path.travel_m<connector.axial_release_m+.01:
        raise ValueError('Pull waypoint budget needs at least10mm beyond provisional opening')
    return path
