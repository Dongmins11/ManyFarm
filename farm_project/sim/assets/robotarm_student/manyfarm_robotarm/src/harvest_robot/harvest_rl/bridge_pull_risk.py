"""Gate the Cartesian adapter by physical directional-break risk, never IDs."""
from dataclasses import dataclass
from .bridge_pull_path import PullPathSpec
import torch


@dataclass(frozen=True)
class RiskPullSpec(PullPathSpec):
    risk_extension_m: float = .028
    risk_lateral_m: float = .025
    risk_axial_m: float = .008

    def __post_init__(self):
        super().__post_init__()
        if not self.risk_axial_m < self.risk_lateral_m < self.risk_extension_m < .04:
            raise ValueError('Risk intervention must precede the original40mm overtravel limit')


def directional_risk(displacement,axis,active,attached,qualified,release,spec):
    a=torch.as_tensor(axis,device=displacement.device,dtype=displacement.dtype)
    if a.shape!=(3,) or not torch.isfinite(a).all() or a.norm()<1e-9:
        raise ValueError('Finite nonzero physical pull axis required')
    a=a/a.norm();axial=(displacement*a).sum(-1)
    lateral=(displacement-axial[:,None]*a).norm(dim=-1)
    return (active & attached & qualified & ~release &
            (displacement.norm(dim=-1)>=spec.risk_extension_m) &
            (lateral>=spec.risk_lateral_m) & (axial<=spec.risk_axial_m))
