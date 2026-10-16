"""60Hz r2 원본 계산에서 추출. 재생성: sim/tools/import_teacher60.py."""

SETTLE_S=2.

def prepare_actions(actions,elapsed,confirmed,release_intent):
    """Pull owns the arm; certified grip is maintained by its bounded controller.

    This masks policy proposals only. No joint/body state, contact flag or force
    is written. Explicit release intent retains opening priority. The policy's
    sixth action stays in the common interface but is not a pull control DOF.
    """
    result=actions.clone()
    scope=confirmed & ~release_intent
    result[scope & (elapsed < SETTLE_S-1e-7),:5]=0.
    result[scope,5]=0.
    return result
