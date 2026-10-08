#!/usr/bin/env python3
"""임시 시뮬 관제: Section 입력 → 예찰 성공 Result → 수확 작업 순차 요청."""
import argparse
from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
import signal
import time
import uuid

import rclpy
from rclpy.action import ActionClient
from rclpy.node import Node
from rclpy.signals import SignalHandlerOptions
from rosidl_runtime_py.convert import message_to_ordereddict
from farm_interfaces.action import ScoutArea, HarvestTask

ROOT = Path(__file__).resolve().parents[2]


def timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def dispatchable_tasks(status: int, result: ScoutArea.Result) -> list:
    """성공한 최종 결과만 등록하며 중복 ID/개수 불일치는 전송 전에 거절한다."""
    if status != 4 or result.result_code != 'SUCCESS':
        return []
    tasks = result.harvest_tasks
    if result.harvest_task_count != len(tasks):
        raise RuntimeError('예찰 Result의 harvest_task_count와 목록 길이가 다릅니다.')
    for field in ('task_id', 'window_id'):
        values = [getattr(task, field) for task in tasks]
        if any(not value for value in values) or len(set(values)) != len(values):
            raise RuntimeError(f'예찰 Result에 빈 값 또는 중복 {field}가 있습니다.')
    return list(tasks)


def harvest_goal(task: object, robot_id: str, map_id: str) -> HarvestTask.Goal:
    """예찰 작업의 ID/좌표/예상 수량을 수정하지 않고 외부 Goal에 담는다."""
    goal = HarvestTask.Goal()
    goal.robot_id, goal.map_id = robot_id, map_id
    goal.harvest_task = deepcopy(task)
    goal.timestamp = timestamp()
    return goal


class TemporaryControl(Node):
    def __init__(self, config: dict, harvest_robot: str, timeout: float) -> None:
        super().__init__('temporary_sim_control_' + uuid.uuid4().hex[:8])
        self.config, self.harvest_robot, self.timeout = config, harvest_robot, timeout
        self.scout = ActionClient(self, ScoutArea, f"/{config['robot_id']}/scout_area")
        self.harvest = ActionClient(self, HarvestTask, f'/{harvest_robot}/harvest_task')
        self.interrupted = False
        self.blocked = False
        self.path = ROOT / 'sim/runs/temporary_control' / (datetime.now().strftime('%Y%m%d_%H%M%S_') + uuid.uuid4().hex[:8] + '.jsonl')
        self.path.parent.mkdir(parents=True, exist_ok=True)
        print(f'로그: {self.path}', flush=True)

    def log(self, kind: str, data: object) -> None:
        record = dict(time=timestamp(), kind=kind, data=data)
        with self.path.open('a', encoding='utf-8') as stream:
            stream.write(json.dumps(record, ensure_ascii=False) + '\n')

    def wait(self, future: object, timeout: float, interruptible: bool = True) -> object:
        deadline = time.monotonic() + timeout
        while not future.done():
            if interruptible and self.interrupted:
                raise KeyboardInterrupt
            if time.monotonic() >= deadline:
                raise TimeoutError('Action 응답 대기 시간 초과')
            rclpy.spin_once(self, timeout_sec=0.1)
        return future.result()

    def feedback(self, label: str, message: object) -> None:
        value = message.feedback
        self.log(label + '_feedback', dict(message_to_ordereddict(value)))
        if label == 'scout':
            print(f'[예찰] {value.phase} {value.section_id}/{value.segment_id} 완료 segment={value.completed_segment_count}', flush=True)
        else:
            print(f'[수확] {value.task_id} 누적 적재={value.success_count}, 실패={value.failed_count}', flush=True)

    def execute(self, client: ActionClient, goal: object, label: str) -> object:
        if not client.wait_for_server(timeout_sec=10.0):
            raise RuntimeError(f'{label} 서버가 없습니다. launch와 ROS_DOMAIN_ID를 확인하세요.')
        if self.interrupted:
            raise KeyboardInterrupt
        self.log(label + '_goal', dict(message_to_ordereddict(goal)))
        pending = client.send_goal_async(goal, feedback_callback=lambda msg: self.feedback(label, msg))
        handle = None
        result_future = None
        try:
            handle = self.wait(pending, 15.0)
            if not handle.accepted:
                raise RuntimeError(f'{label} Goal이 거절됐습니다. 서버 준비/기존 작업을 확인하세요.')
            result_future = handle.get_result_async()
            response = self.wait(result_future, self.timeout)
            self.record_result(label, response)
            return response
        except (KeyboardInterrupt, Exception):
            # 전송 후 늦게 수락된 자기 Goal도 회수한다. 확인 실패 시 다음 작업을 막는다.
            try:
                handle = handle or self.wait(pending, 15.0, False)
                if handle.accepted:
                    result_future = result_future or handle.get_result_async()
                    if not result_future.done():
                        ack = self.wait(handle.cancel_goal_async(), 15.0, False)
                        accepted = any(bytes(item.goal_id.uuid) == bytes(handle.goal_id.uuid)
                                       for item in ack.goals_canceling)
                        self.log(label + '_cancel_ack', {'own_goal_accepted': accepted})
                    terminal = self.wait(result_future, 60.0, False)
                    self.record_result(label, terminal)
                    if terminal.status not in (4, 5, 6) or terminal.result.error_code == 'CANCEL_UNCONFIRMED':
                        raise RuntimeError('정지 확인을 받지 못했습니다.')
            except Exception as error:
                self.blocked = True
                self.log('stop_unconfirmed', {'error': str(error)})
                print(f'정지 확인 실패: {error}. 새 작업을 보내지 않습니다.', flush=True)
            raise

    def record_result(self, label: str, response: object) -> None:
        self.log(label + '_result', dict(ros_status=response.status,
                 result=dict(message_to_ordereddict(response.result))))
        value = response.result
        print(f'[{label} 결과] {value.result_code} {value.error_code}: {value.error_message}', flush=True)
        if label == 'harvest':
            print(f'  예상={value.expected_count}, 실제 적재={value.harvested_count}, 실패={value.failed_count}', flush=True)

    def cycle(self, section: str) -> None:
        if self.blocked:
            raise RuntimeError('정지 미확인 상태입니다. 서버 상태를 먼저 확인하세요.')
        goal = ScoutArea.Goal()
        goal.robot_id, goal.map_id = self.config['robot_id'], self.config['map_id']
        goal.task_id = 'SIM_CONTROL_' + uuid.uuid4().hex
        goal.section_id, goal.frame_id = section, 'map'
        goal.crop_type, goal.target_ripeness = 'PAPRIKA', 'RIPE'
        goal.timestamp = timestamp()
        response = self.execute(self.scout, goal, 'scout')
        result = response.result
        if (result.robot_id, result.task_id, result.section_id) != (goal.robot_id, goal.task_id, section):
            raise RuntimeError('예찰 Result의 요청 식별자가 다릅니다.')
        tasks = dispatchable_tasks(response.status, result)
        if response.status != 4 or result.result_code != 'SUCCESS':
            print('예찰 실패/취소: 부분 목록은 수확으로 보내지 않습니다.')
            return
        print(f'예찰 완료: 수확 작업 {len(tasks)}개를 순차 요청합니다.', flush=True)
        harvested, failed = 0, 0
        for index, task in enumerate(tasks, 1):
            print(f'[수확 {index}/{len(tasks)}] {task.window_id}, 예상={task.expected_count}', flush=True)
            response = self.execute(self.harvest, harvest_goal(task, self.harvest_robot, goal.map_id), 'harvest')
            value = response.result
            if (value.robot_id, value.task_id, value.window_id) != (self.harvest_robot, task.task_id, task.window_id):
                raise RuntimeError('수확 Result의 요청 식별자가 다릅니다.')
            harvested += value.harvested_count
            failed += value.failed_count
            if response.status != 4 or value.result_code != 'SUCCESS':
                if value.error_code == 'CANCEL_UNCONFIRMED':
                    self.blocked = True
                print('수확 작업 실패/취소: 남은 큐 전송을 중단합니다.', flush=True)
                return
        print(f'사이클 완료: 작업={len(tasks)}, 실제 적재={harvested}, 실패={failed}. SUCCESS는 적재 성공 보장이 아닙니다.', flush=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--section', help='지정하면 해당 Section 한 사이클 후 종료. 생략하면 대화형 입력')
    parser.add_argument('--timeout', type=float, default=14400.0, help='Action별 실제 시간 제한(초)')
    args = parser.parse_args()
    if not 0 < args.timeout < float('inf'):
        parser.error('--timeout은 양의 유한한 초 값이어야 합니다.')
    config_dir = ROOT / 'sim/ros_ws/src/farm_sim_config/config'
    config = json.loads((config_dir / 'scout_survey.json').read_text())
    harvest = json.loads((config_dir / 'harvest_task.json').read_text())
    if config['map_id'] != harvest['map_id']:
        parser.error('예찰/수확 map_id 설정이 다릅니다.')
    sections = list(config['sections'])
    if args.section and args.section not in sections:
        parser.error(f'지원 Section: {", ".join(sections)}')
    rclpy.init(signal_handler_options=SignalHandlerOptions.NO)
    node = TemporaryControl(config, harvest['robot_id'], args.timeout)
    def interrupt(signum: int, frame: object) -> None:
        if not node.interrupted:
            node.interrupted = True
            raise KeyboardInterrupt
    signal.signal(signal.SIGINT, interrupt)
    signal.signal(signal.SIGTERM, interrupt)
    try:
        print('Section: ' + ', '.join(sections) + '\n종료: q / 진행 중 Ctrl+C: 현재 작업 취소 후 프로그램 종료')
        while not node.blocked:
            section = args.section or input('Section> ').strip()
            if section.lower() in ('q', 'quit', 'exit'):
                break
            if section not in sections:
                print('설정에 있는 Section을 입력하세요.')
                continue
            node.cycle(section)
            if args.section:
                break
        return 1 if node.blocked else 0
    except (KeyboardInterrupt, EOFError):
        print('\n임시 관제를 종료합니다.')
        return 1 if node.blocked else 130
    except Exception as error:
        node.log('error', {'error': str(error)})
        print(f'중단: {error}', flush=True)
        return 1
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    raise SystemExit(main())
