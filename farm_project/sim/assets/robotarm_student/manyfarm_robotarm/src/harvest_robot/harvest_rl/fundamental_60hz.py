"""Explicit, inference-only component experiments; no implicit bank compatibility."""
from dataclasses import asdict, dataclass
import copy


@dataclass(frozen=True)
class FundamentalSpec:
    name: str
    arm_target: str = 'stored'
    solver_refine: bool = False
    fruit_collision_mode: str = 'legacy'


VARIANTS={
    'baseline':FundamentalSpec('baseline'),
    'measured_arm':FundamentalSpec('measured_arm',arm_target='measured'),
    'solver_refined':FundamentalSpec('solver_refined',solver_refine=True),
    'body_hull':FundamentalSpec('body_hull',fruit_collision_mode='body_hull_v1'),
}


def changed_task(task,spec):
    result=copy.deepcopy(task)
    result['contact_solver_refine']=spec.solver_refine
    result['fruit_collision_mode']=spec.fruit_collision_mode
    if result['physics_dt']!=1/60 or result['decimation']!=3 or result['mass']!=.009:
        raise ValueError('Only the existing9g/60Hz/20Hz component experiment is supported')
    return result


def experimental_bank_view(bank,task,spec):
    """Readonly reset view explicitly annotated by the experiment contract.

    Changed-collider/solver trials are NOT certified physical handoff banks.
    They reuse the same measured initial poses/velocities as counterfactual
    initial conditions. The original metadata, files and tensors stay untouched.
    """
    from .grasp_handoff_60hz import physical_signature
    original=bank.metadata['physical_signature']
    modified=physical_signature(task)
    allowed={'contact_solver_refine','fruit_collision_mode'}
    differences={k for k in original if original[k]!=modified.get(k)}
    if differences-allowed or set(original)!=set(modified):
        raise ValueError('Unexpected physical override in the component experiment')
    expected={k for k,v in changed_task(original,spec).items() if original[k]!=v}
    if differences!=expected:
        raise ValueError('Physical override does not match the declared experiment')
    view=copy.copy(bank)
    view.metadata=copy.deepcopy(bank.metadata)
    view.metadata['physical_signature']=modified
    return view


def physical_contract(spec):
    return dict(spec=asdict(spec),comparison_only=True,training_gate_eligible=False,
        bank_semantics='same measured reset initial conditions; changed physics is an explicit counterfactual, not a certified bank',
        physics_hz=60,policy_hz=20,hidden_substeps=0,learning=False,hardware_executed=False)
