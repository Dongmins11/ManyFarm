"""공통 정밀주행 결과를 운송 업무의 다음 단계로 연결한다."""
from .mission_state import MissionState
from ..mission_types import Outcome


class DockingState(MissionState):
    name = 'DOCKING'
    def enter(self) -> None:
        if not self.controller.docking.available():
            raise RuntimeError('도킹 장치 연결 없음')
        self.controller.mission.set_contact(True)
        self.controller.feedback('DOCKING' if self.controller.request.kind == 'return' else 'DOCKING_STARTED')
        c=self.controller
        approach=getattr(c,'sorter_approach',None)
        operation=(lambda:approach.dock(c.request)) if approach is not None and approach.applies(c.request) else (lambda:c.docking.dock(c.request))
        if c.request.kind == 'pickup' and c.pickup_workflow.get('enabled'):
            from ..pickup_workflow import stage_request
            operation = lambda:c.docking.dock(stage_request(c.request, c.pickup_workflow, 'dock'))
        c.run_async(self,operation,self._done)

    def _done(self, stable: bool) -> None:
        if not stable:
            raise RuntimeError('도킹 안정 조건 미충족')
        c = self.controller
        c.docked_request = c.request
        if c.request.kind == 'return':
            if c.request.profile_id in c.parking_profiles:
                # Precision DOCK succeeds only after the configured parking rotation.
                c.mission.set_contact(False)
                c.parked_request = c.request
                c.docked_request = None
            c.finish(Outcome('SUCCESS',arrived=True,docked=True))
        elif c.request.kind == 'pickup':
            from .transfer_states import WaitTransferState
            if c.pickup_workflow.get('enabled'):
                from .transfer_states import ReceiveLidState
                c.transition(ReceiveLidState(c, 'LID_OPEN'))
            else:
                c.transition(WaitTransferState(c))
        elif c.request.dock_only_trial:
            from .transfer_states import DockTrialHoldState
            c.transition(DockTrialHoldState(c))
        else:
            from .transfer_states import WaitUnloadState
            c.mission.record_stage(c.request, 'DOCKING_COMPLETED')
            c.transition(WaitUnloadState(c))
