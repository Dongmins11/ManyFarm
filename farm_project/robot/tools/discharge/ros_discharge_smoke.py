#!/usr/bin/env python3
"""PC 전용 실제 ROS Action 송수신 시험. 모터/주행/관제 Action을 호출하지 않는다.

고유한 /test_only 주소에서 시험 서버를 함께 실행한다. 결과는 모의값이며
실물 배출·정지 검증을 의미하지 않는다. 임의 endpoint 인자는 받지 않는다.
"""
from pathlib import Path
import sys
import threading
import time
import uuid
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'ros_ws/src/harvest_robot'))
import rclpy
from rclpy.action import ActionServer, GoalResponse, CancelResponse
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.executors import MultiThreadedExecutor
from rclpy.node import Node
from farm_interfaces.action import Discharge
from harvest_robot.discharge_client import DischargeClient
from harvest_robot.discharge_result import DischargeEvidence


def main() -> None:
    rclpy.init()
    suffix = uuid.uuid4().hex[:12]
    endpoint = '/test_only/discharge_' + suffix
    server_node = Node('discharge_mock_' + suffix)
    client_node = Node('discharge_probe_' + suffix)
    counts = {}; phases = []
    def execute(handle: object) -> Discharge.Result:
        identity = handle.request.transfer_id
        counts[identity] = counts.get(identity, 0) + 1
        result = Discharge.Result(); result.transfer_id = identity
        for phase in ('OPENING', 'DISCHARGING', 'CLOSING'):
            feedback = Discharge.Feedback(); feedback.phase = phase
            handle.publish_feedback(feedback)
            time.sleep(.03)
        if identity == 'mock-cancel':
            deadline = time.monotonic() + 3.
            while not handle.is_cancel_requested and time.monotonic() < deadline:
                time.sleep(.01)
            if handle.is_cancel_requested:
                handle.canceled(); return result
            result.error_codes = ['INTERNAL_ERROR']; result.error_message = 'mock cancel timeout'
            handle.abort(); return result
        if identity == 'mock-errors':
            result.error_codes = ['DISCHARGE_FAILED', 'CLOSE_FAILED']
            result.error_message = '시험용 복수 오류'
            handle.abort()
        else:
            result.error_codes = []; handle.succeed()
        return result
    server = ActionServer(server_node, Discharge, endpoint, execute_callback=execute,
        goal_callback=lambda goal: GoalResponse.REJECT if goal.transfer_id == 'mock-reject' else GoalResponse.ACCEPT,
        cancel_callback=lambda goal: CancelResponse.ACCEPT,
        callback_group=ReentrantCallbackGroup())
    client = DischargeClient(client_node, endpoint, 3., 4., ReentrantCallbackGroup(), feedback=phases.append)
    executor = MultiThreadedExecutor(num_threads=4)
    executor.add_node(server_node); executor.add_node(client_node)
    worker = threading.Thread(target=executor.spin, daemon=True); worker.start()
    try:
        deadline = time.monotonic() + 5.
        while not client.ready() and time.monotonic() < deadline: time.sleep(.02)
        if not client.ready(): raise RuntimeError('PC 시험 서버 discovery 실패')
        for identity, expected in (('mock-success', True), ('mock-errors', False), ('mock-reject', False)):
            evidence = DischargeEvidence(identity); ticket = client.start(evidence)
            deadline = time.monotonic() + 5.
            while True:
                reply = client.poll(ticket)
                if reply.completed: break
                if time.monotonic() >= deadline: raise TimeoutError(identity)
                time.sleep(.01)
            assert reply.ok is expected, (identity, reply)
            assert evidence.restore_check().ok is expected
            if identity == 'mock-errors':
                assert all(code in reply.detail for code in ('DISCHARGE_FAILED','CLOSE_FAILED'))
            print(identity, 'PASS', flush=True)
        evidence = DischargeEvidence('mock-cancel'); client.start(evidence)
        client.cancel()
        assert not evidence.restore_check().ok and not client.has_goal
        assert counts.get('mock-success') == 1 and counts.get('mock-errors') == 1
        assert 'mock-reject' not in counts
        assert set(phases) == {'OPENING', 'DISCHARGING', 'CLOSING'}
        print('mock-cancel PASS; 실제 ROS 송수신 4개 시나리오 PASS, 물리 장치는 모의', flush=True)
    finally:
        if client.has_goal:
            try: client.cancel()
            except Exception as error: print('시험 Goal 종료 미확인:', error, file=sys.stderr)
        executor.shutdown(timeout_sec=5.); worker.join(5.)
        client.close(); server.destroy(); client_node.destroy_node(); server_node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__': main()
