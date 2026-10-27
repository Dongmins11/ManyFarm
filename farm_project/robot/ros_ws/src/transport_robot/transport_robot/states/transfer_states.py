"""운송 업무 단계. 센서 알고리즘은 공통 정밀주행/기구 포트에 위임한다."""
from dataclasses import replace
from .mission_state import MissionState
from ..mission_types import Outcome

class TaggingState(MissionState):
    name = 'DOCKING'
    def enter(self) -> None:
        c = self.controller
        if c.pickup_workflow.get('enabled'):
            from ..pickup_workflow import stage_request
            c.mission.set_contact(True)
            c.run_async(self, lambda:c.docking.dock(stage_request(c.request, c.pickup_workflow, 'approach')), self._done)
        else:
            c.run_async(self, lambda:c.docking.tag(c.request), self._done)
    def _done(self, ok: bool) -> None:
        if not ok: raise RuntimeError('대상 마커 확인 실패')
        self.controller.transition(WaitReadyState(self.controller))

class WaitReadyState(MissionState):
    name = 'WAIT_DOCK_READY'
    def enter(self) -> None:
        c = self.controller
        c.transfer.timeout = c.pickup_workflow.get('ready_timeout_s', 60.)
        c.transfer.stage('WAIT_READY')
        c.feedback('WAITING_FOR_TRANSFER')
        c.run_async(self, lambda:c.transfer.wait('DOCK_READY', c.check), self._done)
    def _done(self, unused) -> None:
        from .docking_state import DockingState
        self.controller.transition(DockingState(self.controller))

class WaitTransferState(MissionState):
    name = 'WAITING_TRANSFER'
    def enter(self) -> None:
        c = self.controller
        c.transfer.timeout = c.pickup_workflow.get('transfer_timeout_s', 60.)
        c.transfer.stage('WAIT_TRANSFER')
        c.feedback('DOCK_STABLE')
        c.run_async(self, lambda:c.transfer.wait('TRANSFER_COMPLETE',c.check), self._done)
    def _done(self, unused) -> None:
        if self.controller.pickup_workflow.get('enabled'):
            self.controller.transition(ReceiveLidState(self.controller, 'LID_CLOSE'))
        else:
            self.controller.transition(DeviceState(self.controller,'CONFIRM_RECEIPT'))

class DeviceState(MissionState):
    name = 'UNLOADING'
    def __init__(self, controller, operation: str) -> None:
        super().__init__(controller)
        self.operation = operation
        self.name = 'UNLOADING' if operation == 'UNLOAD' else 'WAITING_TRANSFER'
    def enter(self) -> None:
        c = self.controller
        if self.operation == 'UNLOAD':
            c.mission.record_stage(c.request, 'UNLOAD_REQUESTED')
            c.feedback('UNLOADING_STARTED')
        c.run_async(self,lambda:c.device.run(c.request,self.operation,c.check),self._done)
    def _done(self, result) -> None:
        c = self.controller
        if self.operation == 'UNLOAD':
            if not result.success:
                raise RuntimeError('하역 기구 시퀀스 실패')
            if hasattr(result, 'safe_to_clear') and (not result.safe_to_clear or not result.count_valid or result.loaded_count < 0):
                raise RuntimeError('기존 Action 장치의 완료/안전 이격/수량 검증 실패')
            c.mission.record_stage(c.request, 'UNLOAD_COMPLETED', getattr(result, 'message', ''))
            # Timed mechanism completion does not establish an observed fruit count.
            c.loaded_count = None
            if c.unload_workflows.get(c.request.station_id, {}).get('auto_clear', False):
                c.transition(ClearingState(c))
            else:
                c.finish(Outcome('SUCCESS', arrived=True, docked=True))
        else:
            if not result.success or not result.safe_to_clear or not result.count_valid or result.loaded_count < 0:
                raise RuntimeError('기구 완료/안전 이격/실수령량 확인 실패')
            c.loaded_count = result.loaded_count
            c.transition(ClearingState(c))

class ClearingState(MissionState):
    name = 'CLEARING'
    def __init__(self, controller, departure: bool = False) -> None:
        super().__init__(controller)
        self.departure = departure
    def enter(self) -> None:
        c = self.controller
        request = c.docked_request if self.departure else c.request
        if request is None: raise RuntimeError('도킹 세션 없는 이격 금지')
        if request.kind == 'unload':
            workflow = c.unload_workflows.get(request.station_id, {})
            if workflow.get('clearance_profile'):
                request = replace(request, profile_id=workflow['clearance_profile'],
                    target_marker_id=workflow['marker_id'], docking_marker_id=workflow['marker_id'])
            if not self.departure:
                c.mission.record_stage(c.request, 'CLEARING_STARTED')
        if request.kind == 'pickup' and c.pickup_workflow.get('enabled'):
            from ..pickup_workflow import stage_request
            request = stage_request(request, c.pickup_workflow, 'clearance')
        if not self.departure: c.feedback('CLEARING_STARTED')
        c.run_async(self,lambda:c.docking.clear(request),self._done)
    def _done(self, ok: bool) -> None:
        c = self.controller
        if not ok: raise RuntimeError('지정 이격점 도달 실패')
        c.mission.set_contact(False)
        c.docked_request = None
        if self.departure:
            from .navigation_move_state import NavigationMoveState
            c.transition(NavigationMoveState(c))
        else:
            if c.request.kind == 'pickup': c.feedback('TRANSPORT_CLEAR')
            if c.request.kind == 'unload': c.mission.record_stage(c.request, 'CLEARANCE_COMPLETED')
            c.finish(Outcome('SUCCESS',arrived=True))


class WaitUnloadState(MissionState):
    # Docked and stationary; WAITING_FOR_UNLOAD feedback distinguishes the wait.
    name = 'DOCKING'
    def enter(self) -> None:
        c = self.controller
        if c.docked_request is not c.request:
            raise RuntimeError('선별장 도킹 완료 전 준비 대기 금지')
        workflow = c.unload_workflows.get(c.request.station_id, {})
        c.unload.timeout = float(workflow.get('ready_timeout_s', 60.0))
        if not 0 < c.unload.timeout <= 3600:
            raise ValueError('UNLOAD_READY timeout must be 0..3600 seconds')
        c.unload.stage('WAIT_READY')
        c.mission.record_stage(c.request, 'WAITING_FOR_UNLOAD')
        c.feedback('WAITING_FOR_UNLOAD')
        if c.request.dock_only_trial or c.unload_workflows.get(c.request.station_id, {}).get('assume_unload_ready', False):
            c.check()
            self._done(None)
        else:
            c.run_async(self,lambda:c.unload.wait(c.check),self._done)

    def _done(self, unused: None) -> None:
        c = self.controller
        assumed = c.request.dock_only_trial or c.unload_workflows.get(c.request.station_id, {}).get('assume_unload_ready', False)
        c.mission.record_stage(c.request, 'UNLOAD_READY_ASSUMED' if assumed else 'UNLOAD_READY_RECEIVED')
        self.controller.unload.stage('UNLOADING')
        self.controller.transition(DeviceState(self.controller, 'UNLOAD'))


class DockTrialHoldState(MissionState):
    """실제 하역 성공을 만들지 않고 도킹 후 취소까지 정지 대기한다."""
    name = 'DOCKING'
    def enter(self) -> None:
        import time
        c = self.controller
        def wait_cancel() -> None:
            while True:
                c.check()
                time.sleep(0.05)
        c.run_async(self, wait_cancel, lambda unused: None)


class ReceiveLidState(MissionState):
    """Device DONE and peer TRANSFER_COMPLETE are distinct; no invented count."""
    name = 'WAITING_TRANSFER'
    def __init__(self, controller, operation):
        super().__init__(controller)
        self.operation = operation
    def enter(self):
        c = self.controller
        c.mission.record_stage(c.request, self.operation + '_REQUESTED')
        c.run_async(self, lambda: c.device.run(c.request, self.operation, c.check), self._done)
    def _done(self, result):
        c = self.controller
        if not result.success:
            raise RuntimeError(self.operation + ' failed')
        c.mission.record_stage(c.request, self.operation + '_COMPLETED', getattr(result, 'message', ''))
        if self.operation == 'LID_OPEN':
            c.transition(WaitTransferState(c))
        else:
            c.loaded_count = None
            c.transition(ClearingState(c))
