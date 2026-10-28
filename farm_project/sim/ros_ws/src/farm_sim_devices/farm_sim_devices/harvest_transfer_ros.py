"""실측 팔 준비와 승인된 바구니 정렬로 공통 인계 장치 계약을 연결한다.

배출은 가상 상태 전이이며 과실 수량·USD 형상을 바꾸지 않는다.
팔은 기존 수확 작업에서 접힌 뒤에만 준비 응답한다. 접힘을 추정하지 않는다.
"""
import threading
import time
from typing import Any


class TransferObservation:
    """세션·실제시간·시뮬시간이 모두 유효한 장치 증거만 사용한다."""
    def __init__(self) -> None:
        self.session = None
        self.arm = self.proof = None
        self.received = self.stamp = float('-inf')

    def observe(self, session: str, arm: Any, proof: Any, stamp: float) -> None:
        self.session, self.arm, self.proof = session, arm, proof
        self.received, self.stamp = time.monotonic(), stamp

    def fresh(self, now: float) -> bool:
        return (self.session is not None and 0 <= time.monotonic()-self.received <= .5
                and 0 <= now-self.stamp <= .5)

    def stopped(self, now: float) -> bool:
        return (self.fresh(now) and isinstance(self.arm, dict)
                and self.arm.get('busy') is False and self.arm.get('safe_stopped') is True
                and self.arm.get('status') in ('IDLE', 'SUCCESS', 'FAILED', 'CANCELED'))

    def prepared(self, now: float) -> bool:
        return (self.stopped(now) and self.arm.get('travel_ready') is True
                and self.arm.get('travel_ready_measured') is True)

    def aligned(self, now: float) -> bool:
        return (self.prepared(now) and isinstance(self.proof, dict)
                and self.proof.get('hold_pass') is True
                and type(self.proof.get('sim_time_s')) in (int, float)
                and 0 <= now-self.proof['sim_time_s'] <= .5)


class HarvestTransferServer:
    def __init__(self, node: Any) -> None:
        from rclpy.action import ActionServer, GoalResponse, CancelResponse
        from rclpy.callback_groups import ReentrantCallbackGroup
        from farm_interfaces.action import Discharge
        from std_srvs.srv import Trigger
        self.node = node
        self.observation = TransferObservation()
        self.lock = threading.RLock()
        self.busy = self.stopping = False
        self.completed = set()
        self.group = ReentrantCallbackGroup()
        self.action = Discharge
        self.goal_response = GoalResponse
        self.services = [node.create_service(Trigger, 'sim/transfer/'+name, callback,
                         callback_group=self.group) for name, callback in
                         [('prepare_arm', self.prepare), ('stop', self.stop)]]
        self.server = ActionServer(node, Discharge, 'sim/discharge', self.execute,
            goal_callback=self.goal, cancel_callback=lambda _: CancelResponse.ACCEPT,
            callback_group=self.group)

    def now(self) -> float:
        return self.node.get_clock().now().nanoseconds/1e9

    def observe(self, session: str, arm: Any, proof: Any, stamp: float) -> None:
        with self.lock:
            self.observation.observe(session, arm, proof, stamp)

    def prepare(self, request: Any, response: Any) -> Any:
        with self.lock:
            response.success = (not self.busy and not self.stopping
                                and self.observation.prepared(self.now()))
            response.message = ('실측 팔 접힘·정지 확인' if response.success
                                else '팔 접힘/정지/센서 최신성 미확인 또는 복구 필요')
            return response

    def stop(self, request: Any, response: Any) -> Any:
        with self.lock:
            self.stopping = True
            # 배출은 기구 구동 없는 추상 상태다. 팔은 실제 정지 증거가 있어야 응답한다.
            response.success = self.observation.stopped(self.now())
            response.message = ('가상 배출 중단 및 팔 정지 확인' if response.success
                                else '팔 정지 미확인; 기존 팔 취소/복구 필요')
            return response

    def goal(self, request: Any) -> Any:
        with self.lock:
            if (self.busy or self.stopping or not request.transfer_id
                    or request.transfer_id in self.completed or len(self.completed) >= 10000
                    or not self.observation.aligned(self.now())):
                return self.goal_response.REJECT
            self.busy = True
            self.goal_session = self.observation.session
            return self.goal_response.ACCEPT

    def execute(self, handle: Any) -> Any:
        result = self.action.Result(transfer_id=handle.request.transfer_id)
        try:
            for phase in ('OPENING', 'DISCHARGING', 'CLOSING'):
                with self.lock:
                    if handle.is_cancel_requested:
                        handle.canceled();result.error_codes = ['DISCHARGE_FAILED']
                        result.error_message = '가상 배출 취소';return result
                    if (self.stopping or self.goal_session != self.observation.session
                            or not self.observation.aligned(self.now())):
                        handle.abort();result.error_codes = ['DISCHARGE_FAILED']
                        result.error_message = '팔 준비/바구니 정렬 증거 만료 또는 중단';return result
                    handle.publish_feedback(self.action.Feedback(phase=phase))
            with self.lock:
                # 완료 확정 시에도 취소와 증거를 다시 확인한다.
                if handle.is_cancel_requested:
                    handle.canceled();result.error_codes = ['DISCHARGE_FAILED'];return result
                if (self.stopping or self.goal_session != self.observation.session
                        or not self.observation.aligned(self.now())):
                    handle.abort();result.error_codes = ['DISCHARGE_FAILED'];return result
                self.completed.add(handle.request.transfer_id)
                result.error_message = 'SIM_ALIGNMENT_ONLY: 실제 전달 수량 미측정'
                handle.succeed()
                self.node.get_logger().info('SIM_VIRTUAL_DISCHARGE '+handle.request.transfer_id
                    +' alignment_hold=true count_valid=false')
                return result
        finally:
            with self.lock:
                self.busy = False

    def close(self) -> None:
        with self.lock:
            self.stopping = True
        self.server.destroy()
        for service in self.services:
            self.node.destroy_service(service)
