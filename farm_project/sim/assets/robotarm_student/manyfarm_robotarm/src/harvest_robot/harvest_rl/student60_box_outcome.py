"""Box settlement adjudication, independent of a prescribed grasp history."""
import torch


SAFETY_FAILURES=('failure_high_force','failure_dropped','failure_stray',
    'failure_arm_collision','failure_unwanted_finger','failure_other_detach','failure_green_detach')


def box_settlement_step(previous,diagnostic,attached,dt):
    if dt<=0:raise ValueError('Positive physical observation interval required')
    safety=torch.zeros_like(attached,dtype=torch.bool)
    for name in SAFETY_FAILURES:
        value=diagnostic.get(name)
        if value is not None:safety |= value.bool()
    eligible=(diagnostic['deposit_mesh_inside'].bool()
        & diagnostic['deposit_both_jaws_clear'].bool() & ~attached.bool() & ~safety)
    return torch.where(eligible,previous+dt,0.),eligible,safety
