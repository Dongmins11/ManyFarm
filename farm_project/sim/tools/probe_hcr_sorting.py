#!/usr/bin/env python3
"""원본 선별 서버와 실제 RGB/물리 시뮬을 연결하는 단독 ROS 시험.

모의 DONE/카메라 관측을 만들지 않는다. --cancel-on-busy는 팔이 수락한
동작의 완료·HOME 복귀 후 취소 결과에 완료 수량이 보존되는지 확인한다.
농장 운송/투입/Frontend 연쇄 실행기는 아니다.
"""
import argparse
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sim-output', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--cancel-on-busy', action='store_true')
    args = parser.parse_args()
    if os.environ.get('ROS_DOMAIN_ID') != '13' or os.environ.get('ROS_AUTOMATIC_DISCOVERY_RANGE') != 'SUBNET':
        parser.error('시험 통신은 ROS_DOMAIN_ID=13, ROS_AUTOMATIC_DISCOVERY_RANGE=SUBNET이어야 합니다.')
    args.output.mkdir(parents=True, exist_ok=False)

    import rclpy
    from rclpy.action import ActionClient
    from rclpy.executors import SingleThreadedExecutor
    from rclpy.node import Node
    from farm_interfaces.action import SortBatch
    from farm_interfaces.msg import SorterStatus
    from hcr_sorting.node import SorterNode

    def stamp() -> str:
        return datetime.now(timezone.utc).isoformat()

    log = (args.output / 'events.jsonl').open('w')

    def record(kind: str, **data: object) -> None:
        entry = {'timestamp': stamp(), 'event': kind, **data}
        log.write(json.dumps(entry, ensure_ascii=False) + '\n')
        log.flush()
        print(json.dumps(entry, ensure_ascii=False), flush=True)

    rclpy.init(args=['--ros-args', '-p', 'robot_id:=sorter_01',
        '-p', 'modbus_host:=127.0.0.1', '-p', 'modbus_peer:=127.0.0.1', '-p', 'modbus_port:=1502',
        '-p', f'camera_state:={args.sim_output.resolve() / "state.json"}',
        '-p', f'runtime_state:={args.output.resolve() / "runtime.json"}',
        '-p', f'journal:={args.output.resolve() / "journal.sqlite3"}'])
    server = SorterNode()
    node = Node('hcr_sorting_physics_probe')
    executor = SingleThreadedExecutor()
    executor.add_node(server)
    executor.add_node(node)
    action = ActionClient(node, SortBatch, '/sorter_01/sort_batch')
    observed = {'ready': False, 'busy_seen': False}

    def status(msg: SorterStatus) -> None:
        observed['ready'] = msg.ready
        record('status', state=msg.state, ready=msg.ready, error_code=msg.error_code)

    def feedback(message: object) -> None:
        value = message.feedback
        observed['busy_seen'] |= value.phase == 'BUSY'
        record('feedback', phase=value.phase, red_count=value.red_count, yellow_count=value.yellow_count)

    subscription = node.create_subscription(SorterStatus, '/sorter_01/status', status, 10)

    def until(predicate: Callable[[], bool], seconds: float) -> None:
        deadline = time.monotonic() + seconds
        while not predicate():
            if time.monotonic() >= deadline:
                raise TimeoutError('실제 상태/결과 수신 제한시간 초과')
            executor.spin_once(timeout_sec=.05)

    try:
        until(lambda: observed['ready'] and action.server_is_ready(), 180.)
        task = 'hcr_physics_' + str(time.time_ns())
        goal = SortBatch.Goal(robot_id='sorter_01', task_id=task,
                             batch_id=task, timestamp=stamp())
        sent = action.send_goal_async(goal, feedback_callback=feedback)
        until(sent.done, 10.)
        handle = sent.result()
        record('goal', task_id=task, accepted=handle.accepted)
        if not handle.accepted:
            raise RuntimeError('선별 Goal 거절')
        final = handle.get_result_async()
        if args.cancel_on_busy:
            until(lambda: observed['busy_seen'] or final.done(), 180.)
            if final.done():
                raise RuntimeError('BUSY 관측 전에 작업 종료')
            canceled = handle.cancel_goal_async()
            until(canceled.done, 10.)
            accepted = bool(canceled.result().goals_canceling)
            record('cancel', accepted=accepted)
            if not accepted:
                raise RuntimeError('취소 거절')
        until(final.done, 300.)
        value = final.result().result
        result = {key: getattr(value, key) for key in (
            'robot_id', 'task_id', 'batch_id', 'result_code', 'red_count',
            'yellow_count', 'error_code', 'error_message', 'timestamp')}
        (args.output / 'result.json').write_text(json.dumps(result, ensure_ascii=False, indent=2))
        record('result', **result)

        def saved() -> bool:
            try:
                json.loads((args.sim_output / 'report.json').read_text())
                return True
            except (OSError, ValueError):
                return False

        # 유한 스텝 시뮬이 물리 결과를 저장할 때까지 원본 heartbeat를 유지한다.
        until(saved, 180.)
        physical = json.loads((args.sim_output / 'report.json').read_text())
        expected = 'CANCELED' if args.cancel_on_busy else 'SUCCESS'
        if result['result_code'] != expected:
            raise AssertionError(result)
        if physical['counts'] != [result['red_count'], result['yellow_count']]:
            raise AssertionError('물리 확인 수량과 ROS 수량 불일치')
        if args.cancel_on_busy and sum(physical['counts']) != 1:
            raise AssertionError('진행 중 1회 완료 후 취소 수량이 1이 아님')
        record('verified', result_code=result['result_code'], counts=physical['counts'],
               actual_fruit_count=len(physical['fruits']),
               remaining_count=sum(not fruit['sorted'] for fruit in physical['fruits']))
    except Exception as exc:
        record('probe_error', reason=str(exc))
        raise
    finally:
        action.destroy()
        node.destroy_subscription(subscription)
        executor.remove_node(server)
        executor.remove_node(node)
        server.close()
        node.destroy_node()
        executor.shutdown()
        rclpy.shutdown()
        log.close()


if __name__ == '__main__':
    main()
